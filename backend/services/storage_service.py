import os
import logging
from typing import List, Optional, Set
from sqlalchemy.orm import Session

from database import Document, ChatSession, ChatMessage
from utils.file_utils import get_doc_file_path, UPLOAD_DIR, TEMP_ZIPS_DIR
import rag

logger = logging.getLogger("uvicorn.error")

def delete_chat_physical_files(chat_id: str) -> int:
    """Single Source of Truth: Deletes all physical upload and media files associated with a chat_id."""
    deleted_files = 0
    if not os.path.exists(UPLOAD_DIR):
        return 0
    try:
        prefix = f"{chat_id}_"
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(prefix):
                fp = os.path.join(UPLOAD_DIR, fname)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                        deleted_files += 1
                except Exception as e:
                    logger.warning(f"[Storage] Failed to remove chat file {fp}: {e}")
    except Exception as e:
        logger.error(f"[Storage] Error scanning upload dir for chat {chat_id}: {e}")
    return deleted_files

def delete_chat_session_cascade(db: Session, chat_id: str) -> bool:
    """Single Source of Truth: Cascades deletion across physical files, vector indices, and relational database."""
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        return False
        
    # 1. Clean physical files from disk
    delete_chat_physical_files(chat_id)

    # 2. Clean vectors from Vector Store
    try:
        rag.delete_document_vectors(chat_id)
    except Exception as e:
        logger.warning(f"[Storage] Vector cleanup failed for chat {chat_id}: {e}")

    # 3. Clean database records
    db.query(Document).filter(Document.chat_id == chat_id).delete(synchronize_session=False)
    db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).delete(synchronize_session=False)
    db.delete(chat)
    db.commit()
    return True

def delete_document_by_id(db: Session, chat_id: str, doc_id: int) -> bool:
    """Safely deletes physical file, vector embeddings, and database record for a single document."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        return False
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"[Delete Document Error] Failed to delete file {file_path}: {e}")
            
    try:
        rag.delete_document_vectors(chat_id, doc.filename)
    except Exception as e:
        logger.error(f"[Delete Vector Error] Failed to delete vectors for {doc.filename}: {e}")
        
    db.delete(doc)
    db.commit()
    return True

def delete_multiple_documents(db: Session, chat_id: str, doc_ids: List[int]) -> int:
    """Bulk deletes physical files, vector embeddings, and database records."""
    docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.chat_id == chat_id).all()
    deleted_count = 0
    for doc in docs:
        file_path = get_doc_file_path(chat_id, doc.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"[Bulk Delete Error] Failed to delete file {file_path}: {e}")
        try:
            rag.delete_document_vectors(chat_id, doc.filename)
        except Exception as e:
            logger.error(f"[Bulk Delete Vector Error] Failed to delete vectors for {doc.filename}: {e}")
            
        db.delete(doc)
        deleted_count += 1
        
    db.commit()
    return deleted_count

def cleanup_orphan_files_on_disk(active_chat_ids: Set[str]) -> tuple:
    """Single Source of Truth: Scans and removes orphan upload files and expired temporary zip archives."""
    deleted_files = 0
    freed_bytes = 0

    # 1. Clean orphan files in uploads/
    if os.path.exists(UPLOAD_DIR):
        for fname in os.listdir(UPLOAD_DIR):
            fp = os.path.join(UPLOAD_DIR, fname)
            if not os.path.isfile(fp):
                continue
            if "_" in fname:
                cid = fname.split("_", 1)[0]
                if cid not in active_chat_ids and len(cid) >= 32:
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        deleted_files += 1
                        freed_bytes += sz
                    except Exception as e:
                        logger.warning(f"[Storage] Failed to remove orphan file {fp}: {e}")

    # 2. Clean temporary ZIP archives
    if os.path.exists(TEMP_ZIPS_DIR):
        for fname in os.listdir(TEMP_ZIPS_DIR):
            fp = os.path.join(TEMP_ZIPS_DIR, fname)
            try:
                if os.path.isfile(fp):
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    deleted_files += 1
                    freed_bytes += sz
            except Exception as e:
                logger.warning(f"[Storage] Failed to remove temp zip {fp}: {e}")

    return deleted_files, freed_bytes
