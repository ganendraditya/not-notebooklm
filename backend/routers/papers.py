import re
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document
import models
import rag
from utils.file_utils import MAX_SOURCES_PER_CHAT
from utils.text_processing import clean_doi
from services.paper_service import (
    search_academic_papers,
    filter_novel_sources,
    import_sources_progressive_stream,
    import_sources_batch,
    import_single_doi_source,
)

router = APIRouter(tags=["papers"])
logger = logging.getLogger("uvicorn.error")

@router.get("/search_papers", response_model=List[models.PaperCandidate])
@router.get("/papers/search", response_model=List[models.PaperCandidate])
async def search_papers(query: str, limit: int = 10):
    return await search_academic_papers(query, limit)

@router.post("/chats/{chat_id}/import_sources_stream")
async def import_sources_stream(chat_id: str, req: models.ImportSourcesRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    remaining_slots = max(0, MAX_SOURCES_PER_CHAT - current_doc_count)
    if remaining_slots <= 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Document limit reached (Max {MAX_SOURCES_PER_CHAT} documents per chat). Please delete some sources before importing new ones."
        )
        
    # Allow requested sources through; import stream checks existing documents
    # and enforces remaining_slots quota strictly against novel candidate papers
    allowed_sources = req.sources

    return StreamingResponse(
        import_sources_progressive_stream(chat_id, allowed_sources, current_doc_count, remaining_slots=remaining_slots),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/chats/{chat_id}/import_sources", response_model=List[models.DocumentResponse])
async def import_sources(chat_id: str, req: models.ImportSourcesRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    remaining_slots = max(0, MAX_SOURCES_PER_CHAT - current_doc_count)
    if remaining_slots <= 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Document limit reached (Max {MAX_SOURCES_PER_CHAT} documents per chat). Please delete some sources before importing new ones."
        )
        
    allowed_sources = filter_novel_sources(chat_id, req.sources, remaining_slots)
    return await import_sources_batch(chat_id, allowed_sources, db)

@router.post("/chats/{chat_id}/import_doi", response_model=models.DocumentResponse)
@router.post("/chats/{chat_id}/documents/import-doi", response_model=models.DocumentResponse)
async def import_doi_source(chat_id: str, req: models.ImportDoiRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if current_doc_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(
            status_code=400, 
            detail=f"Source limit reached! (Max {MAX_SOURCES_PER_CHAT} sources per notebook). Please remove some sources first."
        )

    raw_doi = (req.doi or "").strip()
    clean_doi_val = clean_doi(raw_doi)
    
    doi_match = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', clean_doi_val)
    if not doi_match:
        raise HTTPException(status_code=422, detail="Invalid DOI format. Expected format: 10.xxxx/xxxx or https://doi.org/10.xxxx/xxxx")
    
    extracted_doi = doi_match.group(0).strip().rstrip(".")
    
    existing_sigs = rag.get_existing_notebook_sources_signatures(chat_id)
    if extracted_doi.lower() in existing_sigs.get("dois", set()):
        raise HTTPException(status_code=409, detail=f"This paper (DOI: {extracted_doi}) has already been added to your sources.")
        
    try:
        db_doc, has_downloaded_pdf, is_oa, total_count = await import_single_doi_source(chat_id, extracted_doi, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return models.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        title=db_doc.title or db_doc.filename.replace(".pdf", "").replace("_", " ").strip(),
        created_at=db_doc.created_at,
        index=total_count,
        has_full_pdf=has_downloaded_pdf,
        is_oa=is_oa
    )
