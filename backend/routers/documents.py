import os
import re
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document
import models
import rag
from utils.file_utils import (
    UPLOAD_DIR,
    TEMP_ZIPS_DIR,
    MAX_SOURCES_PER_CHAT,
    make_content_disposition,
    get_doc_file_path,
)
from utils.pdf_utils import (
    get_authentic_document_pdf,
    is_authentic_pdf_bytes,
)
from services.document import (
    handle_document_upload,
    clean_chat_duplicates,
    get_document_full_content,
)
from services.storage_service import (
    delete_document_by_id,
    delete_multiple_documents,
)
from services.export_service import (
    generate_bulk_zip_stream,
)

router = APIRouter(tags=["documents"])
logger = logging.getLogger("uvicorn.error")

@router.post("/chats/{chat_id}/upload", response_model=models.DocumentResponse)
async def upload_document(
    chat_id: str, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".bib", ".bibtex", ".ris"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTS))}"
        )

    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    existing_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if existing_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(status_code=400, detail=f"Source limit reached! This conversation already contains {existing_count}/{MAX_SOURCES_PER_CHAT} sources.")
        
    db_doc, file_path, enriched = handle_document_upload(chat_id, file, db)

    # Schedule vector store indexing in background
    background_tasks.add_task(rag.ingest_document, file_path, chat_id)
    
    total_docs_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    return models.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        title=db_doc.title or db_doc.filename.replace(".pdf", "").replace("_", " ").strip(),
        created_at=db_doc.created_at,
        index=total_docs_count,
        has_full_pdf=enriched.get("is_valid_pdf", False),
        is_oa=True if enriched.get("is_valid_pdf", False) else False
    )

@router.delete("/chats/{chat_id}/documents/{doc_id}")
def delete_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    success = delete_document_by_id(db, chat_id, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "success"}

@router.patch("/chats/{chat_id}/documents/{doc_id}/rename", response_model=models.DocumentResponse)
def rename_document(chat_id: str, doc_id: int, payload: models.RenameDocumentRequest, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    clean_title = payload.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Document title cannot be empty.")
        
    doc.title = clean_title
    db.commit()
    db.refresh(doc)
    
    fp = get_doc_file_path(chat_id, doc.filename)
    is_valid_pdf = False
    if os.path.exists(fp):
        try:
            with open(fp, "rb") as f:
                fb = f.read(2048)
                is_valid_pdf = is_authentic_pdf_bytes(fb, min_size=500) and os.path.getsize(fp) >= 1000
        except Exception:
            is_valid_pdf = False

    return models.DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        created_at=doc.created_at,
        has_full_pdf=is_valid_pdf,
        is_oa=is_valid_pdf
    )

@router.post("/chats/{chat_id}/documents/bulk_delete")
def bulk_delete_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    deleted_count = delete_multiple_documents(db, chat_id, req.doc_ids)
    return {"status": "success", "deleted_count": deleted_count}

@router.post("/chats/{chat_id}/clean_duplicates")
async def clean_duplicate_documents(chat_id: str, db: Session = Depends(get_db)):
    db_chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return await clean_chat_duplicates(chat_id, db)

@router.get("/chats/{chat_id}/documents/{doc_id}/download")
def download_document(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    pdf_bytes, download_filename = get_authentic_document_pdf(chat_id, doc.filename)
    if not pdf_bytes:
        raise HTTPException(
            status_code=404, 
            detail="Naskah lengkap PDF tidak tersedia untuk diunduh (hanya metadata / abstrak)."
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": make_content_disposition("attachment", download_filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/raw")
def view_document_raw(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    file_path = get_doc_file_path(chat_id, doc.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File on disk not found")
        
    ext = os.path.splitext(doc.filename)[1].lower()
    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".bib": "text/plain",
        ".ris": "text/plain"
    }
    return FileResponse(
        file_path,
        media_type=media_types.get(ext, "application/octet-stream"),
        filename=doc.filename,
        headers={"Content-Disposition": make_content_disposition("inline", doc.filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/stream")
def stream_document_pdf(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    pdf_bytes, stream_filename = get_authentic_document_pdf(chat_id, doc.filename)
    if not pdf_bytes:
        raise HTTPException(
            status_code=404, 
            detail="Naskah lengkap PDF tidak tersedia untuk dokumen ini."
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": make_content_disposition("inline", stream_filename)}
    )

@router.get("/chats/{chat_id}/documents/{doc_id}/content")
async def get_document_content(chat_id: str, doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.chat_id == chat_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return await get_document_full_content(chat_id, doc, db)

@router.post("/chats/{chat_id}/documents/bulk_download")
def bulk_download_documents(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.id.in_(req.doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for download")
        
    if len(docs) == 1:
        doc = docs[0]
        pdf_bytes, download_filename = get_authentic_document_pdf(chat_id, doc.filename)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="Naskah lengkap PDF tidak tersedia untuk diunduh.")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": make_content_disposition("attachment", download_filename)}
        )
        
    import uuid as uuid_pkg
    task_id = str(uuid_pkg.uuid4())
    return {"status": "processing", "task_id": task_id, "message": "Download started in background. Use streaming endpoint to track progress."}

@router.post("/chats/{chat_id}/documents/bulk_download_stream")
async def bulk_download_stream(chat_id: str, req: models.BulkDeleteRequest, db: Session = Depends(get_db)):
    return StreamingResponse(
        generate_bulk_zip_stream(chat_id, req.doc_ids, db),
        media_type="text/event-stream"
    )

@router.get("/chats/{chat_id}/documents/download_zip/{task_id}")
def download_prepared_zip(chat_id: str, task_id: str):
    clean_task = re.sub(r'[^a-zA-Z0-9-]', '', task_id)
    zip_path = os.path.join(TEMP_ZIPS_DIR, f"{clean_task}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Prepared download file not found or expired.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        headers={"Content-Disposition": make_content_disposition("attachment", f"NotbookLM_Sources_{chat_id[:8]}.zip")}
    )
