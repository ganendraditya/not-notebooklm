import os
import uuid
import json
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
import shutil
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document, ChatMessage
from helpers import UPLOAD_DIR
import models
import rag

router = APIRouter(tags=["chats"])
logger = logging.getLogger("uvicorn.error")

CHAT_MEDIA_DIR = os.path.join(UPLOAD_DIR, "chat_media")
os.makedirs(CHAT_MEDIA_DIR, exist_ok=True)

@router.post("/chats", response_model=models.ChatSessionResponse)
def create_chat(chat: models.ChatSessionCreate, db: Session = Depends(get_db)):
    chat_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db_chat = ChatSession(id=chat_id, title=chat.title, created_at=now, updated_at=now)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

@router.get("/chats", response_model=List[models.ChatSessionResponse])
def get_chats(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc()).all()

@router.get("/chats/{chat_id}", response_model=models.ChatSessionDetailResponse)
def get_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    sorted_docs = sorted(chat.documents, key=lambda d: d.id)
    doc_responses = []
    from helpers import get_doc_file_path
    import pdf_exporter
    
    for idx, d in enumerate(sorted_docs, start=1):
        fp = get_doc_file_path(chat_id, d.filename)
        has_pdf = False
        if os.path.exists(fp) and os.path.getsize(fp) >= 35000:
            try:
                with open(fp, "rb") as f:
                    fb = f.read(2048)
                    if fb.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in fb and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in fb:
                        has_pdf = True
            except Exception:
                has_pdf = False
                
        doc_responses.append(models.DocumentResponse(
            id=d.id,
            filename=d.filename,
            title=d.title or d.filename.replace(".pdf", "").replace("_", " ").strip(),
            created_at=d.created_at,
            index=idx,
            has_full_pdf=has_pdf,
            is_oa=d.is_oa if d.is_oa is not None else True
        ))
        
    sorted_msgs = sorted(chat.messages, key=lambda m: m.created_at)
    msg_responses = []
    for msg in sorted_msgs:
        attachments = None
        if hasattr(msg, 'attachments_json') and msg.attachments_json:
            try:
                attachments = json.loads(msg.attachments_json)
            except:
                pass
        variants = None
        if hasattr(msg, 'variants_json') and msg.variants_json:
            try:
                variants = json.loads(msg.variants_json)
            except:
                pass
        if not variants and msg.content:
            variants = [msg.content]
            
        active_var_idx = getattr(msg, 'active_variant_index', 0) or 0
        if active_var_idx < 0 or active_var_idx >= len(variants):
            active_var_idx = len(variants) - 1
            
        # Display current active variant content
        curr_content = variants[active_var_idx] if variants else msg.content

        msg_responses.append(models.ChatMessageResponse(
            role=msg.role,
            content=curr_content,
            created_at=msg.created_at,
            attachments=attachments,
            variants=variants,
            active_variant_index=active_var_idx
        ))
        
    return models.ChatSessionDetailResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        is_pinned=chat.is_pinned,
        documents=doc_responses,
        messages=msg_responses
    )

@router.put("/chats/{chat_id}", response_model=models.ChatSessionResponse)
@router.patch("/chats/{chat_id}", response_model=models.ChatSessionResponse)
def update_chat(chat_id: str, update: models.ChatSessionUpdate, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = update.title
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(chat)
    return chat

@router.patch("/chats/{chat_id}/pin", response_model=models.ChatSessionResponse)
def toggle_pin_chat(chat_id: str, payload: models.PinChatRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.is_pinned = payload.is_pinned
    db.commit()
    db.refresh(chat)
    return chat

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    # 1. Clean physical files from disk in uploads directory
    from helpers import UPLOAD_DIR
    try:
        if os.path.exists(UPLOAD_DIR):
            for fname in os.listdir(UPLOAD_DIR):
                if fname.startswith(f"{chat_id}_"):
                    fp = os.path.join(UPLOAD_DIR, fname)
                    try:
                        if os.path.isfile(fp):
                            os.remove(fp)
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"[Delete Chat File Cleanup Warning]: {e}")

    # 2. Clean vectors from Qdrant
    try:
        rag.delete_qdrant_vectors(chat_id)
    except Exception as e:
        logger.debug(f"[Qdrant Vector Clean Warning]: {e}")

    # 3. Delete all related documents and chat messages explicitly
    db.query(Document).filter(Document.chat_id == chat_id).delete(synchronize_session=False)
    db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete(synchronize_session=False)
    
    # 4. Delete chat session record
    db.delete(chat)
    db.commit()
    return {"status": "success", "message": "Chat deleted"}

@router.post("/chats/bulk-delete")
def bulk_delete_chats(payload: models.BulkDeleteChatsRequest, db: Session = Depends(get_db)):
    deleted_count = 0
    from helpers import UPLOAD_DIR
    
    for chat_id in payload.chat_ids:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            continue
            
        # Clean physical files
        try:
            if os.path.exists(UPLOAD_DIR):
                for fname in os.listdir(UPLOAD_DIR):
                    if fname.startswith(f"{chat_id}_"):
                        fp = os.path.join(UPLOAD_DIR, fname)
                        if os.path.isfile(fp):
                            os.remove(fp)
        except Exception:
            pass

        # Clean vectors
        try:
            rag.delete_qdrant_vectors(chat_id)
        except Exception:
            pass

        # Delete database records
        db.query(Document).filter(Document.chat_id == chat_id).delete(synchronize_session=False)
        db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete(synchronize_session=False)
        db.delete(chat)
        deleted_count += 1

    db.commit()
    return {"status": "success", "deleted_count": deleted_count}

@router.post("/chats/{chat_id}/upload_chat_media")
async def upload_chat_media(chat_id: str, file: UploadFile = File(...)):
    """Uploads an image/media attachment for a chat session."""
    # Check current storage usage against 10GB limit
    total_bytes_limit = 10 * 1024 * 1024 * 1024
    used_bytes = 0
    if os.path.exists(UPLOAD_DIR):
        for root, _, files in os.walk(UPLOAD_DIR):
            for f in files:
                try:
                    used_bytes += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
                    
    is_storage_full = used_bytes >= total_bytes_limit

    # Save file
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    safe_filename = f"{chat_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(CHAT_MEDIA_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # Return attachment metadata with storage limit awareness
    return {
        "status": "success",
        "storage_full": is_storage_full,
        "attachment": {
            "type": "image" if file_ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"] else "file",
            "filename": file.filename,
            "size": file_size,
            "url": f"/uploads/chat_media/{safe_filename}",
            "chat_only": is_storage_full
        }
    }
async def send_message(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    attachments_str = None
    if query.attachments:
        attachments_str = json.dumps([a.dict() for a in query.attachments])

    user_msg = ChatMessage(
        chat_id=chat_id, 
        role="user", 
        content=query.message,
        attachments_json=attachments_str
    )
    db.add(user_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    chat_history = []
    for msg in chat.messages:
        item = {"role": msg.role, "content": msg.content}
        if hasattr(msg, 'attachments_json') and msg.attachments_json:
            try:
                atts = json.loads(msg.attachments_json)
                if atts:
                    item["attachments"] = atts
            except:
                pass
        chat_history.append(item)
    
    try:
        response_text = await rag.query_chat(chat_id, query.message, chat_history=chat_history)
    except Exception as e:
        logger.error(f"[Chat Query Error]: {e}")
        response_text = f"Sorry, an error occurred: {str(e)}"
        
    asst_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(asst_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asst_msg)
    
    return models.ChatMessageResponse(
        role=asst_msg.role,
        content=asst_msg.content,
        created_at=asst_msg.created_at,
        attachments=None
    )

@router.post("/chats/{chat_id}/message/stream")
@router.post("/chats/{chat_id}/message_stream")
async def send_message_stream(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    attachments_str = None
    if query.attachments:
        attachments_str = json.dumps([a.dict() for a in query.attachments])

    user_msg = ChatMessage(
        chat_id=chat_id, 
        role="user", 
        content=query.message,
        attachments_json=attachments_str
    )
    db.add(user_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    chat_history = []
    for msg in all_msgs:
        item = {"role": msg.role, "content": msg.content}
        if hasattr(msg, 'attachments_json') and msg.attachments_json:
            try:
                atts = json.loads(msg.attachments_json)
                if atts:
                    item["attachments"] = atts
            except:
                pass
        chat_history.append(item)
    
    # Check if chat is still using default/raw initial title and needs smart AI naming
    is_initial_chat_state = len(all_msgs) <= 1 or chat.title in ("New Chat", "New Research", "") or (chat.title and chat.title.endswith("..."))
    
    async def event_generator():
        import asyncio
        queue = asyncio.Queue()
        
        async def status_callback(status_text: str):
            await queue.put({"type": "status", "text": status_text, "data": status_text})
            
        async def worker():
            try:
                # 1. Background smart title generation if new chat
                if is_initial_chat_state:
                    try:
                        ai_title = await rag.generate_chat_title(query.message)
                        if ai_title:
                            from database import SessionLocal
                            t_db = SessionLocal()
                            try:
                                t_chat = t_db.query(ChatSession).filter(ChatSession.id == chat_id).first()
                                if t_chat:
                                    t_chat.title = ai_title
                                    t_db.commit()
                            finally:
                                t_db.close()
                            await queue.put({"type": "title_update", "title": ai_title, "chat_id": chat_id})
                    except Exception as title_err:
                        logger.debug(f"[Title Update Error]: {title_err}")

                # 2. Main response generation
                resp_text = await rag.query_chat(
                    chat_id, 
                    query.message, 
                    chat_history=chat_history, 
                    status_callback=status_callback
                )
                from database import SessionLocal
                bg_db = SessionLocal()
                try:
                    asst_msg = ChatMessage(
                        chat_id=chat_id, 
                        role="assistant", 
                        content=resp_text,
                        variants_json=json.dumps([resp_text]),
                        active_variant_index=0
                    )
                    bg_db.add(asst_msg)
                    bg_chat = bg_db.query(ChatSession).filter(ChatSession.id == chat_id).first()
                    if bg_chat:
                        bg_chat.updated_at = datetime.utcnow()
                    bg_db.commit()
                finally:
                    bg_db.close()
                await queue.put({
                    "type": "done",
                    "data": resp_text,
                    "message": {
                        "role": "assistant",
                        "content": resp_text,
                        "created_at": datetime.utcnow().isoformat(),
                        "variants": [resp_text],
                        "active_variant_index": 0
                    }
                })
            except Exception as e:
                logger.error(f"[Chat Stream Worker Error]: {e}")
                await queue.put({"type": "error", "data": str(e), "message": {"role": "assistant", "content": f"Sorry, an error occurred: {str(e)}", "created_at": datetime.utcnow().isoformat()}})
            finally:
                await queue.put(None)
                
        asyncio.create_task(worker())
        
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.put("/chats/{chat_id}/edit_message", response_model=models.ChatMessageResponse)
async def edit_message(chat_id: str, req: models.EditMessageRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    if req.message_index < 0 or req.message_index >= len(all_msgs):
        raise HTTPException(status_code=400, detail="Invalid message index")
        
    target_msg = all_msgs[req.message_index]
    if target_msg.role != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be edited")
        
    target_msg.content = req.message
    for msg_to_del in all_msgs[req.message_index + 1:]:
        db.delete(msg_to_del)
        
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    truncated_history = [{"role": msg.role, "content": msg.content} for msg in all_msgs[:req.message_index + 1]]
    
    try:
        response_text = await rag.query_chat(chat_id, req.message, chat_history=truncated_history)
    except Exception as e:
        logger.error(f"[Chat Edit Error]: {e}")
        response_text = f"Sorry, an error occurred: {str(e)}"
        
    asst_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(asst_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asst_msg)
    
    return asst_msg

@router.put("/chats/{chat_id}/edit_message/stream")
@router.put("/chats/{chat_id}/edit_message_stream")
@router.post("/chats/{chat_id}/edit_message_stream")
async def edit_message_stream(chat_id: str, req: models.EditMessageRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    if req.message_index < 0 or req.message_index >= len(all_msgs):
        raise HTTPException(status_code=400, detail="Invalid message index")
        
    target_msg = all_msgs[req.message_index]
    if target_msg.role != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be edited")
        
    target_msg.content = req.message
    for msg_to_del in all_msgs[req.message_index + 1:]:
        db.delete(msg_to_del)
        
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    truncated_history = [{"role": msg.role, "content": msg.content} for msg in all_msgs[:req.message_index + 1]]
    
    async def event_generator():
        import asyncio
        queue = asyncio.Queue()
        
        async def status_callback(status_text: str):
            await queue.put({"type": "status", "text": status_text, "data": status_text})
            
        async def worker():
            try:
                resp_text = await rag.query_chat(
                    chat_id, 
                    req.message, 
                    chat_history=truncated_history, 
                    status_callback=status_callback
                )
                from database import SessionLocal
                bg_db = SessionLocal()
                try:
                    asst_msg = ChatMessage(
                        chat_id=chat_id, 
                        role="assistant", 
                        content=resp_text,
                        variants_json=json.dumps([resp_text]),
                        active_variant_index=0
                    )
                    bg_db.add(asst_msg)
                    bg_chat = bg_db.query(ChatSession).filter(ChatSession.id == chat_id).first()
                    if bg_chat:
                        bg_chat.updated_at = datetime.utcnow()
                    bg_db.commit()
                finally:
                    bg_db.close()
                await queue.put({
                    "type": "done",
                    "data": resp_text,
                    "message": {
                        "role": "assistant",
                        "content": resp_text,
                        "created_at": datetime.utcnow().isoformat(),
                        "variants": [resp_text],
                        "active_variant_index": 0
                    }
                })
            except Exception as e:
                logger.error(f"[Chat Edit Stream Worker Error]: {e}")
                await queue.put({"type": "error", "data": str(e), "message": {"role": "assistant", "content": f"Sorry, an error occurred: {str(e)}", "created_at": datetime.utcnow().isoformat()}})
            finally:
                await queue.put(None)
                
        asyncio.create_task(worker())
        
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chats/{chat_id}/regenerate_stream")
async def regenerate_message_stream(chat_id: str, req: models.RegenerateMessageRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    if req.message_index < 0 or req.message_index >= len(all_msgs):
        raise HTTPException(status_code=400, detail="Invalid message index")
        
    target_msg = all_msgs[req.message_index]
    if target_msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Only assistant messages can be regenerated")
        
    # Find the preceding user message
    user_prompt = ""
    for m in reversed(all_msgs[:req.message_index]):
        if m.role == "user":
            user_prompt = m.content
            break
            
    if not user_prompt:
        raise HTTPException(status_code=400, detail="No preceding user message found")
        
    # History up to the user message
    truncated_history = [{"role": msg.role, "content": msg.content} for msg in all_msgs[:req.message_index]]
    target_msg_id = target_msg.id
    
    async def event_generator():
        import asyncio
        queue = asyncio.Queue()
        
        async def status_callback(status_text: str):
            await queue.put({"type": "status", "text": status_text, "data": status_text})
            
        async def worker():
            try:
                resp_text = await rag.query_chat(
                    chat_id, 
                    user_prompt, 
                    chat_history=truncated_history, 
                    status_callback=status_callback
                )
                from database import SessionLocal
                bg_db = SessionLocal()
                try:
                    db_msg = bg_db.query(ChatMessage).filter(ChatMessage.id == target_msg_id).first()
                    if db_msg:
                        existing_variants = []
                        if db_msg.variants_json:
                            try:
                                existing_variants = json.loads(db_msg.variants_json)
                            except:
                                pass
                        if not existing_variants and db_msg.content:
                            existing_variants = [db_msg.content]
                            
                        existing_variants.append(resp_text)
                        new_active_idx = len(existing_variants) - 1
                        
                        db_msg.content = resp_text
                        db_msg.variants_json = json.dumps(existing_variants)
                        db_msg.active_variant_index = new_active_idx
                        
                        bg_chat = bg_db.query(ChatSession).filter(ChatSession.id == chat_id).first()
                        if bg_chat:
                            bg_chat.updated_at = datetime.utcnow()
                        bg_db.commit()
                        
                        await queue.put({
                            "type": "done",
                            "data": resp_text,
                            "message_index": req.message_index,
                            "variants": existing_variants,
                            "active_variant_index": new_active_idx,
                            "message": {
                                "role": "assistant",
                                "content": resp_text,
                                "created_at": db_msg.created_at.isoformat() if hasattr(db_msg, 'created_at') else datetime.utcnow().isoformat(),
                                "variants": existing_variants,
                                "active_variant_index": new_active_idx
                            }
                        })
                finally:
                    bg_db.close()
            except Exception as e:
                logger.error(f"[Chat Regenerate Stream Worker Error]: {e}")
                await queue.put({"type": "error", "data": str(e)})
            finally:
                await queue.put(None)
                
        asyncio.create_task(worker())
        
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.put("/chats/{chat_id}/select_variant")
def select_message_variant(chat_id: str, req: models.SelectVariantRequest, db: Session = Depends(get_db)):
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    if req.message_index < 0 or req.message_index >= len(all_msgs):
        raise HTTPException(status_code=400, detail="Invalid message index")
        
    target_msg = all_msgs[req.message_index]
    if target_msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Only assistant messages have variants")
        
    variants = []
    if target_msg.variants_json:
        try:
            variants = json.loads(target_msg.variants_json)
        except:
            pass
    if not variants and target_msg.content:
        variants = [target_msg.content]
        
    if req.variant_index < 0 or req.variant_index >= len(variants):
        raise HTTPException(status_code=400, detail="Invalid variant index")
        
    target_msg.active_variant_index = req.variant_index
    target_msg.content = variants[req.variant_index]
    db.commit()
    return {
        "status": "success", 
        "active_variant_index": req.variant_index, 
        "content": target_msg.content
    }
