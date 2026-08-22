import os
import shutil
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from database import get_db, Document
from helpers import UPLOAD_DIR
from routers.chats import ChatSession  # For DB context if needed

router = APIRouter(prefix="/storage", tags=["storage"])
logger = logging.getLogger("uvicorn.error")

class StorageSummary(BaseModel):
    total_bytes: int
    used_bytes: int
    categories: Dict[str, int]
    file_count: int

class FileItem(BaseModel):
    id: str
    filename: str
    size: int
    type: str
    category: str
    uploaded_at: str

@router.get("/summary", response_model=StorageSummary)
def get_storage_summary(db: Session = Depends(get_db)):
    total_bytes = 10 * 1024 * 1024 * 1024  # Example: 10GB quota
    used_bytes = 0
    categories = {"images": 0, "documents": 0, "others": 0}
    file_count = 0
    
    if os.path.exists(UPLOAD_DIR):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    used_bytes += size
                    file_count += 1
                    
                    ext = file.split('.')[-1].lower() if '.' in file else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                        categories["images"] += size
                    elif ext in ['pdf', 'txt', 'md', 'docx', 'csv']:
                        categories["documents"] += size
                    else:
                        categories["others"] += size
                except Exception as e:
                    pass

    return StorageSummary(
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        categories=categories,
        file_count=file_count
    )

@router.get("/files", response_model=List[FileItem])
def list_files(category: Optional[str] = None, db: Session = Depends(get_db)):
    files_list = []
    
    if os.path.exists(UPLOAD_DIR):
        for root, dirs, files in os.walk(UPLOAD_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    mtime = os.path.getmtime(file_path)
                    uploaded_at = datetime.fromtimestamp(mtime).isoformat() + "Z"
                    
                    ext = file.split('.')[-1].lower() if '.' in file else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                        file_cat = "images"
                        type_str = f"image/{ext}" if ext != 'jpg' else "image/jpeg"
                    elif ext in ['pdf', 'txt', 'md', 'docx', 'csv']:
                        file_cat = "documents"
                        type_str = f"application/{ext}" if ext != 'txt' else "text/plain"
                    else:
                        file_cat = "others"
                        type_str = "application/octet-stream"
                        
                    if category and category != file_cat:
                        continue
                        
                    # Basic ID is the relative path
                    rel_path = os.path.relpath(file_path, UPLOAD_DIR)
                    
                    files_list.append(FileItem(
                        id=rel_path,
                        filename=file,
                        size=size,
                        type=type_str,
                        category=file_cat,
                        uploaded_at=uploaded_at
                    ))
                except Exception:
                    pass
                    
    # Sort by uploaded_at descending
    files_list.sort(key=lambda x: x.uploaded_at, reverse=True)
    return files_list

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
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted += 1
                
                # Also delete DB document if it exists (assuming filename match for simplicity)
                filename = os.path.basename(file_path)
                db.query(Document).filter(Document.filename == filename).delete()
            else:
                failed += 1
        except Exception:
            failed += 1
            
    db.commit()
    return {"status": "success", "deleted": deleted, "failed": failed}

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Ensure upload dir exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Determine subfolder based on category (optional)
        target_dir = UPLOAD_DIR
        if category and category in ["images", "documents"]:
            target_dir = os.path.join(UPLOAD_DIR, category)
            os.makedirs(target_dir, exist_ok=True)
            
        file_id = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(target_dir, file_id)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        size = os.path.getsize(file_path)
        ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        file_cat = category or ("images" if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp'] else "documents")
        
        rel_path = os.path.relpath(file_path, UPLOAD_DIR)
        
        return {
            "status": "success", 
            "file": {
                "id": rel_path,
                "filename": file.filename,
                "size": size,
                "category": file_cat,
                "url": f"/uploads/{rel_path}" # Assuming static mount
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
