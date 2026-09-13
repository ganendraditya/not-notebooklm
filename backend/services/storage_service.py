import os
import logging
from typing import List, Optional, Set
from sqlalchemy.orm import Session

from database import Document, ChatSession, ChatMessage, commit_with_retry
from utils.file_utils import get_doc_file_path, UPLOAD_DIR, TEMP_ZIPS_DIR, CHAT_MEDIA_DIR
import rag

logger = logging.getLogger("uvicorn.error")

def delete_chat_physical_files(chat_id: str) -> int:
    """Single Source of Truth: Deletes all physical upload and media files associated with a chat_id."""
    deleted_files = 0
    prefix = f"{chat_id}_"

    # 1. Clean source document files in UPLOAD_DIR
    if os.path.exists(UPLOAD_DIR):
        try:
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

    # 2. Clean in-chat media attachments in CHAT_MEDIA_DIR
    if os.path.exists(CHAT_MEDIA_DIR):
        try:
            for fname in os.listdir(CHAT_MEDIA_DIR):
                if fname.startswith(prefix):
                    fp = os.path.join(CHAT_MEDIA_DIR, fname)
                    try:
                        if os.path.isfile(fp):
                            os.remove(fp)
                            deleted_files += 1
                    except Exception as e:
                        logger.warning(f"[Storage] Failed to remove chat media file {fp}: {e}")
        except Exception as e:
            logger.error(f"[Storage] Error scanning chat media dir for chat {chat_id}: {e}")

    # 3. Clean S3 bucket objects matching chat prefix if configured
    try:
        from services import storage_adapter
        storage_adapter.delete_files_with_prefix(prefix)
        storage_adapter.delete_files_with_prefix(f"chat_media/{prefix}")
    except Exception as se:
        logger.debug(f"[StorageAdapter Chat Purge Warning]: {se}")

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
    commit_with_retry(db)
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

    try:
        from services import storage_adapter
        storage_adapter.delete_file(f"{chat_id}_{doc.filename}")
    except Exception as se:
        logger.debug(f"[StorageAdapter Doc Delete Warning]: {se}")
        
    db.delete(doc)
    commit_with_retry(db)
    return True

def delete_multiple_documents(db: Session, chat_id: str, doc_ids: List[int]) -> int:
    """Bulk deletes physical files, vector embeddings, and database records using batch SQL deletion."""
    docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.chat_id == chat_id).all()
    deleted_count = 0
    valid_ids = []
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

        try:
            from services import storage_adapter
            storage_adapter.delete_file(f"{chat_id}_{doc.filename}")
        except Exception as se:
            logger.debug(f"[StorageAdapter Batch Delete Warning]: {se}")
            
        valid_ids.append(doc.id)
        deleted_count += 1
        
    if valid_ids:
        db.query(Document).filter(Document.id.in_(valid_ids)).delete(synchronize_session=False)
        commit_with_retry(db)
    return deleted_count

def delete_storage_file_and_records(db: Session, file_path: str) -> bool:
    """
    Single Source of Truth: Deletes a physical file in storage and cascades cleanup to
    matching Document records and Qdrant vector embeddings, resolving chat_id prefix if present.
    """
    abs_path = file_path if os.path.isabs(file_path) else os.path.join(UPLOAD_DIR, file_path)
    if not os.path.exists(abs_path):
        return False

    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except Exception as e:
        logger.error(f"[Storage Delete Error] Failed to delete file {abs_path}: {e}")
        return False

    raw_filename = os.path.basename(abs_path)
    docs = []

    # Case 1: Exact raw filename match
    docs = db.query(Document).filter(Document.filename == raw_filename).all()

    # Case 2: Standard "None_" unassigned prefix
    if not docs and raw_filename.startswith("None_"):
        remainder = raw_filename[5:]
        docs = db.query(Document).filter(
            (Document.filename == remainder) & ((Document.chat_id == "None") | (Document.chat_id.is_(None)) | (Document.chat_id == ""))
        ).all()

    # Case 3: Canonical 36-char UUID prefix "{uuid}_{filename}"
    if not docs and len(raw_filename) > 37 and raw_filename[36] == "_":
        cid = raw_filename[:36]
        rem = raw_filename[37:]
        docs = db.query(Document).filter(
            Document.chat_id == cid,
            Document.filename == rem
        ).all()

    # Case 4: General prefix resolution across all potential "_" delimiters
    if not docs and "_" in raw_filename:
        parts = raw_filename.split("_")
        for i in range(1, len(parts)):
            candidate_cid = "_".join(parts[:i])
            candidate_fn = "_".join(parts[i:])
            matching = db.query(Document).filter(
                Document.chat_id == candidate_cid,
                Document.filename == candidate_fn
            ).all()
            if matching:
                docs.extend(matching)
                break

    valid_doc_ids = []
    for doc in docs:
        try:
            rag.delete_document_vectors(doc.chat_id, doc.filename)
        except Exception as ve:
            logger.warning(f"[Storage Delete] Vector cleanup error for {doc.filename}: {ve}")
        valid_doc_ids.append(doc.id)

    if valid_doc_ids:
        db.query(Document).filter(Document.id.in_(valid_doc_ids)).delete(synchronize_session=False)

    try:
        from services import storage_adapter
        storage_adapter.delete_file(raw_filename)
        storage_adapter.delete_file(f"chat_media/{raw_filename}")
    except Exception as se:
        logger.debug(f"[StorageAdapter Storage File Delete Warning]: {se}")

    return True

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

    # 2. Clean temporary ZIP archives older than 1 hour
    if os.path.exists(TEMP_ZIPS_DIR):
        import time
        now = time.time()
        for fname in os.listdir(TEMP_ZIPS_DIR):
            fp = os.path.join(TEMP_ZIPS_DIR, fname)
            try:
                if os.path.isfile(fp) and (now - os.path.getmtime(fp)) > 3600:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    deleted_files += 1
                    freed_bytes += sz
            except Exception as e:
                logger.warning(f"[Storage] Failed to remove temp zip {fp}: {e}")

    # 3. Clean orphan chat media
    if os.path.exists(CHAT_MEDIA_DIR):
        for fname in os.listdir(CHAT_MEDIA_DIR):
            fp = os.path.join(CHAT_MEDIA_DIR, fname)
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
                        logger.warning(f"[Storage] Failed to remove orphan chat media {fp}: {e}")

    return deleted_files, freed_bytes

def get_directory_total_size(path: str) -> int:
    """Calculates recursive size of a directory in bytes."""
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
            except Exception:
                pass
    return total

def get_unified_storage_summary(db_path: str) -> dict:
    """
    Single Source of Truth: Computes comprehensive disk usage breakdown.
    Covers uploaded documents, chat media attachments, sqlite database (including WAL/SHM), and Qdrant vectors.
    """
    uploads_count = 0
    categories = {"images": 0, "documents": 0, "others": 0}
    category_counts = {"images": 0, "documents": 0, "others": 0}

    if os.path.exists(UPLOAD_DIR):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            dirs[:] = [d for d in dirs if d != "temp_zips"]
            for file in files:
                uploads_count += 1
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    ext = file.split('.')[-1].lower() if '.' in file else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']:
                        categories["images"] += size
                        category_counts["images"] += 1
                    elif ext in ['pdf', 'txt', 'md', 'docx', 'csv', 'tsv', 'bib', 'bibtex', 'ris', 'xlsx', 'pptx', 'json']:
                        categories["documents"] += size
                        category_counts["documents"] += 1
                    else:
                        categories["others"] += size
                        category_counts["others"] += 1
                except Exception:
                    pass

    uploads_size = sum(categories.values())

    qdrant_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_data"))
    qdrant_size = get_directory_total_size(qdrant_dir)

    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    wal_path = f"{db_path}-wal"
    if os.path.exists(wal_path):
        db_size += os.path.getsize(wal_path)
    shm_path = f"{db_path}-shm"
    if os.path.exists(shm_path):
        db_size += os.path.getsize(shm_path)

    total_bytes = uploads_size + qdrant_size + db_size

    return {
        "total_bytes": 10 * 1024 * 1024 * 1024,  # 10GB Quota Limit
        "used_bytes": total_bytes,
        "uploads_bytes": uploads_size,
        "uploads_count": uploads_count,
        "qdrant_bytes": qdrant_size,
        "database_bytes": db_size,
        "categories": categories,
        "category_counts": category_counts,
        "file_count": uploads_count
    }
