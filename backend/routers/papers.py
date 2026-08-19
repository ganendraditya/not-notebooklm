import os
import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document
import models
import rag
import pdf_exporter
from helpers import (
    UPLOAD_DIR,
    MAX_SOURCES_PER_CHAT,
    sanitize_paper_filename,
)

router = APIRouter(tags=["papers"])
logger = logging.getLogger("uvicorn.error")

@router.get("/search_papers", response_model=List[models.PaperCandidate])
@router.get("/papers/search", response_model=List[models.PaperCandidate])
async def search_papers(query: str, limit: int = 10):
    if not query.strip():
        return []
        
    ninerouter_llm, freellm_llm, gemini_llm, groq_llm = rag.create_llm_instances()
    active_llm = ninerouter_llm or freellm_llm or gemini_llm or groq_llm
    
    plan = await rag.plan_academic_search(query.strip(), None, active_llm)
    if limit and limit != 10:
        plan["target_count"] = max(limit, plan.get("target_count", 10))
        
    papers = await asyncio.to_thread(rag.search_academic_papers_planned, plan)
    return [
        models.PaperCandidate(
            title=p.get("title", "Untitled"),
            year=str(p.get("year", "N/A")),
            doi=p.get("doi", ""),
            url=p.get("url", ""),
            snippet=p.get("snippet", "")
        )
        for p in papers
    ]

@router.post("/chats/{chat_id}/import_sources", response_model=List[models.DocumentResponse])
async def import_sources(chat_id: str, req: models.ImportSourcesRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    remaining_slots = max(0, MAX_SOURCES_PER_CHAT - current_doc_count)
    if remaining_slots <= 0:
        raise HTTPException(status_code=400, detail=f"Document limit reached (Max {MAX_SOURCES_PER_CHAT} documents per chat). Please delete some sources before importing new ones.")
        
    existing_sigs = rag.get_existing_notebook_sources_signatures(chat_id)
    novel_sources = []
    for paper in req.sources:
        if not rag.is_paper_duplicate(paper.title, paper.doi, existing_sigs):
            novel_sources.append(paper)
            norm = rag.normalize_title_str(paper.title)
            if norm:
                existing_sigs["token_signatures"].append((norm, set(norm.split())))
            if paper.doi:
                existing_sigs["dois"].add(paper.doi.lower().strip())

    allowed_sources = novel_sources[:remaining_slots]
    
    # 1. Prepare batch metadata and disk files concurrently
    docs_to_ingest = []
    created_docs = []

    def prepare_paper_file(paper):
        filename = sanitize_paper_filename(paper.title)
        abstract_text = paper.snippet.strip()
        
        doc_text = f"# {paper.title} ({paper.year})\n\n"
        if paper.doi:
            doc_text += f"**DOI:** {paper.doi}  \n"
        if paper.url:
            doc_text += f"**URL:** {paper.url}  \n\n"
        doc_text += f"## Abstract & Overview\n\n{abstract_text}\n"

        save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
        try:
            pdf_bytes = pdf_exporter.generate_academic_pdf_bytes(
                title=paper.title,
                authors=[],
                year=str(paper.year or ""),
                journal="Academic Research Publication",
                journal_metric="Peer-Reviewed",
                doi=paper.doi or "",
                abstract=abstract_text,
                url=paper.url or ""
            )
            with open(save_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            logger.warning(f"[PDF Creation Warning]: {e}")

        return (doc_text, filename, chat_id)

    # Disk files prepared in thread pool
    docs_to_ingest = await asyncio.gather(*(asyncio.to_thread(prepare_paper_file, p) for p in allowed_sources))

    # 2. Single batch vector embedding into Qdrant (1 single API call instead of 50 separate calls)
    try:
        await asyncio.to_thread(rag.ingest_documents_batch, docs_to_ingest)
    except Exception as e:
        logger.warning(f"[Batch Vector Ingestion Warning]: {e}")

    # 3. Database commit
    for _, fname, _ in docs_to_ingest:
        db_doc = Document(chat_id=chat_id, filename=fname)
        db.add(db_doc)
        created_docs.append(db_doc)
        
    db.commit()
    for d in created_docs:
        db.refresh(d)
        
    all_current_docs = db.query(Document).filter(Document.chat_id == chat_id).order_by(Document.id.asc()).all()
    id_to_index = {d.id: idx for idx, d in enumerate(all_current_docs, start=1)}
    
    return [
        models.DocumentResponse(
            id=d.id,
            filename=d.filename,
            created_at=d.created_at,
            index=id_to_index.get(d.id, 1)
        )
        for d in created_docs
    ]
