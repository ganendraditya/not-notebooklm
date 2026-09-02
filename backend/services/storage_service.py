import os
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from database import Document
from utils.file_utils import get_doc_file_path
import rag

logger = logging.getLogger("uvicorn.error")

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
