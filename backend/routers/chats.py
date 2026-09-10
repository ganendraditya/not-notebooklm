import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from database import get_db, ChatSession, ChatMessage, commit_with_retry, get_utc_now
from helpers import UPLOAD_DIR
import models

router = APIRouter(tags=["chats"])
logger = logging.getLogger("uvicorn.error")


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

    # Sync chat media to S3 storage bucket if configured
    try:
        from services import storage_adapter
        storage_adapter.upload_file(file_path, s3_key=f"chat_media/{safe_filename}")
    except Exception as se:
        logger.debug(f"[StorageAdapter Media Sync Warning]: {se}")
        
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
