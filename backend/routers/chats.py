import uuid
import json
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document, ChatMessage
import models
import rag

router = APIRouter(tags=["chats"])
logger = logging.getLogger("uvicorn.error")

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
    for idx, d in enumerate(sorted_docs, start=1):
        doc_responses.append(models.DocumentResponse(
            id=d.id,
            filename=d.filename,
            created_at=d.created_at,
            index=idx
        ))
        
    return models.ChatSessionDetailResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        documents=doc_responses,
        messages=chat.messages
    )

@router.put("/chats/{chat_id}", response_model=models.ChatSessionResponse)
def update_chat(chat_id: str, update: models.ChatSessionUpdate, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = update.title
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(chat)
    return chat

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(chat)
    db.commit()
    return {"status": "success", "message": "Chat deleted"}

@router.post("/chats/{chat_id}/message", response_model=models.ChatMessageResponse)
async def send_message(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=query.message)
    db.add(user_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    chat_history = [{"role": msg.role, "content": msg.content} for msg in chat.messages]
    
    try:
        response_text = await rag.query_chat(chat_id, query.message, chat_history=chat_history)
    except Exception as e:
        logger.error(f"[Chat Query Error]: {e}")
        response_text = f"Maaf, terjadi kesalahan: {str(e)}"
        
    asst_msg = ChatMessage(chat_id=chat_id, role="assistant", content=response_text)
    db.add(asst_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asst_msg)
    
    return asst_msg

@router.post("/chats/{chat_id}/message/stream")
@router.post("/chats/{chat_id}/message_stream")
async def send_message_stream(chat_id: str, query: models.ChatQuery, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=query.message)
    db.add(user_msg)
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    all_msgs = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at.asc()).all()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in all_msgs]
    
    async def event_generator():
        import asyncio
        queue = asyncio.Queue()
        
        async def status_callback(status_text: str):
            await queue.put({"type": "status", "text": status_text, "data": status_text})
            
        async def worker():
            try:
                resp_text = await rag.query_chat(
                    chat_id, 
                    query.message, 
                    chat_history=chat_history, 
                    status_callback=status_callback
                )
                from database import SessionLocal
                bg_db = SessionLocal()
                try:
                    asst_msg = ChatMessage(chat_id=chat_id, role="assistant", content=resp_text)
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
                        "created_at": datetime.utcnow().isoformat()
                    }
                })
            except Exception as e:
                logger.error(f"[Chat Stream Worker Error]: {e}")
                await queue.put({"type": "error", "data": str(e), "message": {"role": "assistant", "content": f"Maaf, terjadi kesalahan: {str(e)}", "created_at": datetime.utcnow().isoformat()}})
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
        logger.error(f"[Edit Message Error]: {e}")
        response_text = f"Maaf, terjadi kesalahan: {str(e)}"
        
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
                    asst_msg = ChatMessage(chat_id=chat_id, role="assistant", content=resp_text)
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
                        "created_at": datetime.utcnow().isoformat()
                    }
                })
            except Exception as e:
                logger.error(f"[Edit Message Stream Worker Error]: {e}")
                await queue.put({"type": "error", "data": str(e), "message": {"role": "assistant", "content": f"Maaf, terjadi kesalahan: {str(e)}", "created_at": datetime.utcnow().isoformat()}})
            finally:
                await queue.put(None)
                
        asyncio.create_task(worker())
        
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")
