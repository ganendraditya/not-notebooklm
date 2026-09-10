import os
import io
import zipfile
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
import rag
from database import get_db, Document, ChatSession, commit_with_retry, DB_PATH
from utils.file_utils import UPLOAD_DIR, make_content_disposition
from services.storage_service import get_unified_storage_summary, delete_storage_file_and_records

router = APIRouter(prefix="/storage", tags=["storage"])
logger = logging.getLogger("uvicorn.error")

class StorageSummary(BaseModel):
    total_bytes: int
    used_bytes: int
    categories: Dict[str, int]
    category_counts: Dict[str, int] = {}
    file_count: int

class FileItem(BaseModel):
    id: str
    filename: str
    raw_filename: str
    size: int
    type: str
    category: str
    uploaded_at: str
    chat_id: Optional[str] = None
    chat_title: Optional[str] = None

@router.get("/summary", response_model=StorageSummary)
def get_storage_summary(db: Session = Depends(get_db)):
    data = get_unified_storage_summary(DB_PATH)
    
    return StorageSummary(
        total_bytes=data["total_bytes"],
        used_bytes=data["used_bytes"],
        categories=data["categories"],
        category_counts=data["category_counts"],
        file_count=data["file_count"]
    )

@router.get("/files", response_model=List[FileItem])
def list_files(category: Optional[str] = None, db: Session = Depends(get_db)):
    files_list = []
    normalized_cat = category.lower() if category else None
    if normalized_cat in ["files", "documents", "doc", "docs"]:
        target_cat = "documents"
    elif normalized_cat in ["images", "image", "media"]:
        target_cat = "images"
    elif normalized_cat in ["all", ""]:
        target_cat = None
    else:
        target_cat = normalized_cat

    # Pre-fetch chat sessions mapping for fast lookup
    chat_sessions_map = {}
    try:
        sessions = db.query(ChatSession).all()
        chat_sessions_map = {str(s.id): s.title for s in sessions}
    except Exception:
        pass

    if os.path.exists(UPLOAD_DIR):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    uploaded_at = datetime.fromtimestamp(mtime).isoformat() + "Z"
                    
                    ext = file.split('.')[-1].lower() if '.' in file else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']:
                        file_cat = "images"
                        type_str = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
                    elif ext in ['pdf', 'txt', 'md', 'docx', 'csv', 'xlsx', 'pptx', 'json', 'glb', 'gltf']:
                        file_cat = "documents"
                        type_str = f"application/{ext}" if ext != 'txt' else "text/plain"
                    else:
                        file_cat = "others"
                        type_str = "application/octet-stream"
                        
                    if target_cat and target_cat != file_cat:
                        continue
                        
                    # Extract clean display name and chat session
                    clean_name = file
                    found_chat_id = None
                    found_chat_title = None

                    if "_" in file:
                        prefix, remainder = file.split("_", 1)
                        if prefix == "None" or len(prefix) == 36:
                            clean_name = remainder
                        if prefix in chat_sessions_map:
                            found_chat_id = prefix
                            found_chat_title = chat_sessions_map[prefix]

                    rel_path = os.path.relpath(file_path, UPLOAD_DIR).replace("\\", "/")
                    
                    files_list.append(FileItem(
                        id=rel_path,
                        filename=clean_name,
                        raw_filename=file,
                        size=size,
                        type=type_str,
                        category=file_cat,
                        uploaded_at=uploaded_at,
                        chat_id=found_chat_id,
                        chat_title=found_chat_title
                    ))
                except Exception:
                    pass
                    
    # Sort by uploaded_at descending
    files_list.sort(key=lambda x: x.uploaded_at, reverse=True)
    return files_list

def is_safe_upload_path(file_path: str) -> bool:
    """Verifies that resolved absolute path is strictly contained within UPLOAD_DIR."""
    try:
        abs_upload_dir = os.path.abspath(UPLOAD_DIR)
        abs_target = os.path.abspath(file_path)
        return os.path.commonpath([abs_upload_dir, abs_target]) == abs_upload_dir
    except Exception:
        return False

class DeleteRequest(BaseModel):
    file_ids: List[str]

@router.post("/delete")
def delete_files(req: DeleteRequest, db: Session = Depends(get_db)):
    deleted = 0
    failed = 0
    
    for file_id in req.file_ids:
        # Sanitize path to prevent traversal
        safe_id = os.path.normpath(file_id)
        if safe_id.startswith('..') or os.path.isabs(safe_id):
            failed += 1
            continue
            
        file_path = os.path.join(UPLOAD_DIR, safe_id)
        if not is_safe_upload_path(file_path):
            failed += 1
            continue

        try:
            if delete_storage_file_and_records(db, file_path):
                deleted += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[Storage Delete] Error deleting {file_id}: {e}")
            failed += 1
            
    commit_with_retry(db)
    return {"status": "success", "deleted": deleted, "failed": failed}

class DownloadRequest(BaseModel):
    file_ids: List[str]

@router.post("/download")
def download_storage_files(req: DownloadRequest):
    if not req.file_ids:
        raise HTTPException(status_code=400, detail="No files selected for download")

    # Single file direct download
    if len(req.file_ids) == 1:
        safe_id = os.path.normpath(req.file_ids[0])
        if safe_id.startswith('..') or os.path.isabs(safe_id):
            raise HTTPException(status_code=400, detail="Invalid file path")
        file_path = os.path.join(UPLOAD_DIR, safe_id)
        if not is_safe_upload_path(file_path):
            raise HTTPException(status_code=400, detail="Invalid file path location")
        if not os.path.exists(file_path):
            from services import storage_adapter
            storage_adapter.ensure_local_copy(safe_id, file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = os.path.basename(file_path)
        if "_" in filename:
            prefix, remainder = filename.split("_", 1)
            if prefix == "None" or len(prefix) == 36:
                filename = remainder
                
        return FileResponse(
            file_path,
            filename=filename,
            headers={"Content-Disposition": make_content_disposition("attachment", filename)}
        )
    
    # Multiple files zipped download
    zip_buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_id in req.file_ids:
            safe_id = os.path.normpath(file_id)
            if safe_id.startswith('..') or os.path.isabs(safe_id):
                continue
            file_path = os.path.join(UPLOAD_DIR, safe_id)
            if not os.path.exists(file_path):
                from services import storage_adapter
                storage_adapter.ensure_local_copy(safe_id, file_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                base_name = os.path.basename(file_path)
                if "_" in base_name:
                    prefix, remainder = base_name.split("_", 1)
                    if prefix == "None" or len(prefix) == 36:
                        base_name = remainder
                try:
                    zf.write(file_path, arcname=base_name)
                    count += 1
                except Exception:
                    pass
                    
    if count == 0:
        raise HTTPException(status_code=404, detail="No valid files to download")
        
    zip_buffer.seek(0)
    zip_filename = f"Library_Export_{count}_files.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": make_content_disposition("attachment", zip_filename)}
    )
