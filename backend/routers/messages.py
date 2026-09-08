import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, ChatSession, ChatMessage, commit_with_retry, get_utc_now
from utils.streaming import create_sse_stream_response, SSEStreamEmitter
import models
import rag

router = APIRouter(tags=["messages"])
logger = logging.getLogger("uvicorn.error")


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
            delta_callback=emitter.emit_delta,
            reset_callback=emitter.emit_clear_delta
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
        
    all_msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if not all_msgs:
        raise HTTPException(status_code=400, detail="No messages found in this chat session")
        
    target_idx = req.message_index
    if target_idx < 0:
        target_idx = 0
    elif target_idx >= len(all_msgs):
        target_idx = len(all_msgs) - 1

    target_msg = all_msgs[target_idx]
    if target_msg.role != "user":
        # Gracefully resolve to the intended user message to prevent index drift errors
        user_indices = [i for i, m in enumerate(all_msgs) if m.role == "user"]
        if not user_indices:
            raise HTTPException(status_code=400, detail="Only user messages can be edited")
        target_idx = min(user_indices, key=lambda i: abs(i - target_idx))
        target_msg = all_msgs[target_idx]

    target_msg.content = req.message
    for msg_to_del in all_msgs[target_idx + 1:]:
        db.delete(msg_to_del)
        
    chat.updated_at = get_utc_now()
    commit_with_retry(db)
    
    truncated_history = extract_chat_history_from_db_messages(all_msgs[:target_idx + 1])
    
    async def stream_worker(emitter: SSEStreamEmitter):
        resp_text = await rag.query_chat(
            chat_id, 
            req.message, 
            chat_history=truncated_history, 
            status_callback=emitter.emit_status,
            delta_callback=emitter.emit_delta,
            reset_callback=emitter.emit_clear_delta
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
        
    all_msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if req.message_index < 0 or req.message_index >= len(all_msgs):
        raise HTTPException(status_code=400, detail="Invalid message index")
        
    target_msg = all_msgs[req.message_index]
    if target_msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Only assistant messages can be regenerated")
        
    # Find the preceding user message
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
            delta_callback=emitter.emit_delta,
            reset_callback=emitter.emit_clear_delta
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
