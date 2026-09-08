import os
import uuid
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
import shutil
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document, ChatMessage, commit_with_retry
from helpers import UPLOAD_DIR
from utils.streaming import create_sse_stream_response, SSEStreamEmitter
import models
import rag

router = APIRouter(tags=["chats"])
logger = logging.getLogger("uvicorn.error")

def get_utc_now():
    return datetime.now(timezone.utc)

def extract_chat_history_from_db_messages(messages: List[ChatMessage]) -> List[dict]:
    """Single Source of Truth: Converts ORM ChatMessage instances to standard history dicts."""
    history = []
    for msg in messages:
        item = {"role": msg.role, "content": msg.content or ""}
        if getattr(msg, "attachments_json", None):
            try:
                atts = json.loads(msg.attachments_json)
                if atts:
                    item["attachments"] = atts
            except Exception:
                pass
        history.append(item)
    return history

def format_chat_message_responses(messages: List[ChatMessage]) -> List[models.ChatMessageResponse]:
    """Single Source of Truth: Formats ORM ChatMessage instances with variant support."""
    msg_responses = []
    for msg in messages:
        attachments = None
        if getattr(msg, "attachments_json", None):
            try:
                attachments = json.loads(msg.attachments_json)
            except Exception:
                attachments = None

        variants = None
        if getattr(msg, "variants_json", None):
            try:
                variants = json.loads(msg.variants_json)
            except Exception:
                variants = None
        if not variants and msg.content:
            variants = [msg.content]

        active_idx = getattr(msg, "active_variant_index", 0) or 0
        if variants:
            if active_idx < 0 or active_idx >= len(variants):
                active_idx = len(variants) - 1
            curr_content = variants[active_idx]
        else:
            active_idx = 0
            curr_content = msg.content or ""

        msg_responses.append(models.ChatMessageResponse(
            role=msg.role,
            content=curr_content,
            created_at=msg.created_at,
            attachments=attachments,
            variants=variants,
            active_variant_index=active_idx
        ))
    return msg_responses

def save_stream_assistant_response(chat_id: str, resp_text: str) -> None:
    """Single Source of Truth: Persists newly streamed assistant response with default variant."""
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
            bg_chat.updated_at = get_utc_now()
        commit_with_retry(bg_db)
    finally:
        bg_db.close()

CHAT_MEDIA_DIR = os.path.join(UPLOAD_DIR, "chat_media")
os.makedirs(CHAT_MEDIA_DIR, exist_ok=True)

@router.post("/chats", response_model=models.ChatSessionResponse)
def create_chat(chat: models.ChatSessionCreate, db: Session = Depends(get_db)):
    chat_id = str(uuid.uuid4())
    now = get_utc_now()
    db_chat = ChatSession(id=chat_id, title=chat.title, created_at=now, updated_at=now)
    db.add(db_chat)
    commit_with_retry(db)
    db.refresh(db_chat)
    return db_chat

@router.get("/chats", response_model=List[models.ChatSessionResponse])
def get_chats(
    limit: int = Query(50, ge=1, le=200, description="Max number of chat sessions to return"),
    offset: int = Query(0, ge=0, description="Offset index for pagination"),
    db: Session = Depends(get_db)
):
    return (
        db.query(ChatSession)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

@router.get("/chats/{chat_id}", response_model=models.ChatSessionDetailResponse)
def get_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    sorted_docs = sorted(chat.documents, key=lambda d: d.id)
    doc_responses = []
    from services.document.content_service import inspect_document_file_status
    
    for idx, d in enumerate(sorted_docs, start=1):
        has_pdf = inspect_document_file_status(chat_id, d.filename)
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
    msg_responses = format_chat_message_responses(sorted_msgs)
        
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
    chat.updated_at = get_utc_now()
    commit_with_retry(db)
    db.refresh(chat)
    return chat

@router.patch("/chats/{chat_id}/pin", response_model=models.ChatSessionResponse)
def toggle_pin_chat(chat_id: str, payload: models.PinChatRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.is_pinned = payload.is_pinned
    commit_with_retry(db)
    db.refresh(chat)
    return chat

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    from services.storage_service import delete_chat_session_cascade
    success = delete_chat_session_cascade(db, chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "success", "message": "Chat deleted"}

@router.post("/chats/bulk-delete")
def bulk_delete_chats(payload: models.BulkDeleteChatsRequest, db: Session = Depends(get_db)):
    from services.storage_service import delete_chat_session_cascade
    deleted_count = 0
    for chat_id in payload.chat_ids:
        if delete_chat_session_cascade(db, chat_id):
            deleted_count += 1
    return {"status": "success", "deleted_count": deleted_count}

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".tsv", ".bib", ".bibtex", ".ris",
    ".jpg", ".jpeg", ".png", ".webp", ".gif"
}
MAX_ATTACHMENT_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB per file

@router.post("/chats/{chat_id}/upload_chat_media")
async def upload_chat_media(chat_id: str, file: UploadFile = File(...)):
    """Uploads an image/media attachment for a chat session with validation."""
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if file_ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}"
        )

    # Check file size limit (25MB)
    file_content = await file.read()
    if len(file_content) > MAX_ATTACHMENT_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' exceeds maximum allowable size of 25MB."
        )

    # Check current storage usage against 10GB limit
    from services.storage_service import get_directory_total_size
    total_bytes_limit = 10 * 1024 * 1024 * 1024
    used_bytes = get_directory_total_size(UPLOAD_DIR)
    is_storage_full = used_bytes >= total_bytes_limit

    # Save file
    safe_filename = f"{chat_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(CHAT_MEDIA_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
        
    file_size = len(file_content)

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
    chat.updated_at = get_utc_now()
    commit_with_retry(db)
    
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    chat_history = extract_chat_history_from_db_messages(all_msgs)
    
    # Check if chat is still using default/raw initial title and needs smart AI naming
    is_initial_chat_state = len(all_msgs) <= 1 or chat.title in ("New Chat", "New Research", "") or (chat.title and chat.title.endswith("..."))
    
    async def stream_worker(emitter: SSEStreamEmitter):
        # 1. Background smart title generation if new chat (non-blocking)
        title_task = None
        if is_initial_chat_state:
            async def run_smart_title_gen():
                try:
                    ai_title = await rag.generate_chat_title(query.message)
                    if ai_title:
                        from database import SessionLocal
                        t_db = SessionLocal()
                        try:
                            t_chat = t_db.query(ChatSession).filter(ChatSession.id == chat_id).first()
                            if t_chat:
                                t_chat.title = ai_title
                                commit_with_retry(t_db)
                        finally:
                            t_db.close()
                        await emitter.emit_event({"type": "title_update", "title": ai_title, "chat_id": chat_id})
                except Exception as title_err:
                    logger.debug(f"[Title Update Error]: {title_err}")

            title_task = asyncio.create_task(run_smart_title_gen())

        # 2. Main response generation
        resp_text = await rag.query_chat(
            chat_id, 
            query.message, 
            chat_history=chat_history, 
            status_callback=emitter.emit_status,
            delta_callback=emitter.emit_delta
        )

        if title_task and not title_task.done():
            try:
                await asyncio.wait_for(title_task, timeout=5.0)
            except Exception:
                pass

        save_stream_assistant_response(chat_id, resp_text)

        await emitter.emit_done(
            final_text=resp_text,
            message_payload={
                "role": "assistant",
                "content": resp_text,
                "created_at": get_utc_now().isoformat(),
                "variants": [resp_text],
                "active_variant_index": 0
            }
        )

    return create_sse_stream_response(stream_worker)

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
        
    chat.updated_at = get_utc_now()
    commit_with_retry(db)
    
    truncated_history = extract_chat_history_from_db_messages(all_msgs[:req.message_index + 1])
    
    async def stream_worker(emitter: SSEStreamEmitter):
        resp_text = await rag.query_chat(
            chat_id, 
            req.message, 
            chat_history=truncated_history, 
            status_callback=emitter.emit_status,
            delta_callback=emitter.emit_delta
        )
        save_stream_assistant_response(chat_id, resp_text)

        await emitter.emit_done(
            final_text=resp_text,
            message_payload={
                "role": "assistant",
                "content": resp_text,
                "created_at": get_utc_now().isoformat(),
                "variants": [resp_text],
                "active_variant_index": 0
            }
        )

    return create_sse_stream_response(stream_worker)

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
        
    # Find the preceding user message (or attachments)
    user_prompt = ""
    for m in reversed(all_msgs[:req.message_index]):
        if m.role == "user":
            user_prompt = m.content or ""
            break
            
    # History up to the user message
    truncated_history = extract_chat_history_from_db_messages(all_msgs[:req.message_index])
    target_msg_id = target_msg.id
    
    async def stream_worker(emitter: SSEStreamEmitter):
        resp_text = await rag.query_chat(
            chat_id, 
            user_prompt, 
            chat_history=truncated_history, 
            status_callback=emitter.emit_status,
            delta_callback=emitter.emit_delta
        )
        from database import SessionLocal
        bg_db = SessionLocal()
        try:
            db_msg = bg_db.query(ChatMessage).filter(ChatMessage.id == target_msg_id).first()
            if db_msg:
                # 1. Delete all descendant messages below this message (Truncate future history)
                bg_db.query(ChatMessage).filter(
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.created_at > db_msg.created_at
                ).delete(synchronize_session=False)

                existing_variants = []
                if db_msg.variants_json:
                    try:
                        existing_variants = json.loads(db_msg.variants_json)
                    except Exception:
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
                    bg_chat.updated_at = get_utc_now()
                commit_with_retry(bg_db)
                
                await emitter.emit_done(
                    final_text=resp_text,
                    message_index=req.message_index,
                    variants=existing_variants,
                    active_variant_index=new_active_idx,
                    message_payload={
                        "role": "assistant",
                        "content": resp_text,
                        "created_at": db_msg.created_at.isoformat() if hasattr(db_msg, 'created_at') else get_utc_now().isoformat(),
                        "variants": existing_variants,
                        "active_variant_index": new_active_idx
                    }
                )
        finally:
            bg_db.close()

    return create_sse_stream_response(stream_worker)

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
        except Exception:
            variants = []
    if not variants and target_msg.content:
        variants = [target_msg.content]
        
    if req.variant_index < 0 or req.variant_index >= len(variants):
        raise HTTPException(status_code=400, detail="Invalid variant index")
        
    target_msg.active_variant_index = req.variant_index
    target_msg.content = variants[req.variant_index]
    commit_with_retry(db)
    return {
        "status": "success", 
        "active_variant_index": req.variant_index, 
        "content": target_msg.content
    }
