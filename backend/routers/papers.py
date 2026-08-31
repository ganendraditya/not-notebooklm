import os
import re
import json
import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, ChatSession, Document
import models
import rag
import pdf_exporter
from helpers import (
    UPLOAD_DIR,
    MAX_SOURCES_PER_CHAT,
    sanitize_paper_filename,
    clean_doi,
    is_authentic_pdf_bytes,
)

router = APIRouter(tags=["papers"])
logger = logging.getLogger("uvicorn.error")

def _prepare_paper_file_sync(chat_id: str, paper: models.PaperCandidate) -> tuple:
    """Prepares paper file on disk, attempting authentic OA download or markdown fallback."""
    filename = sanitize_paper_filename(paper.title)
    abstract_text = (paper.snippet or "").strip()
    c_doi = clean_doi(paper.doi)
    full_doi = f"https://doi.org/{c_doi}" if c_doi and not c_doi.startswith("http") else c_doi

    doc_text = f"# {paper.title} ({paper.year})\n\n"
    if full_doi:
        doc_text += f"**DOI:** {full_doi}  \n"
    if paper.url:
        doc_text += f"**URL:** {paper.url}  \n\n"
    doc_text += f"## Abstract & Overview\n\n{abstract_text}\n"

    save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
    has_downloaded_pdf = False

    if c_doi or paper.pdf_url or paper.url:
        try:
            fetched_oa = pdf_exporter.resolve_and_fetch_authentic_pdf(
                doi=c_doi,
                title=paper.title,
                direct_url=paper.url or "",
                candidate_pdf_url=paper.pdf_url or ""
            )
            if is_authentic_pdf_bytes(fetched_oa, min_size=5000):
                with open(save_path, "wb") as f:
                    f.write(fetched_oa)
                has_downloaded_pdf = True
        except Exception as e:
            logger.debug(f"[OA Fetch on Import]: {e}")

    if not has_downloaded_pdf:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
        except Exception as e:
            logger.warning(f"[Doc text save Warning]: {e}")
    else:
        # If PDF was downloaded, parse markdown from PDF for vector embedding!
        try:
            parsed_full_text = rag.parse_document_to_markdown(save_path)
            if parsed_full_text and len(parsed_full_text.strip()) > 300:
                doc_text = parsed_full_text
        except Exception as e:
            logger.warning(f"[Parse full text for embedding warning]: {e}")

    return (doc_text, filename, chat_id, paper, c_doi, has_downloaded_pdf)

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
            snippet=p.get("snippet", ""),
            authors=p.get("authors", []),
            venue=p.get("venue", ""),
            pdf_url=p.get("pdf_url", ""),
            is_oa=p.get("is_oa", True),
            journal_metric=p.get("journal_metric", ""),
            citations=p.get("citations", 0),
        )
        for p in papers
    ]

@router.post("/chats/{chat_id}/import_sources_stream")
async def import_sources_stream(chat_id: str, req: models.ImportSourcesRequest, db: Session = Depends(get_db)):
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
    total_to_import = len(allowed_sources)

    async def event_generator():
        import json
        from database import SessionLocal
        
        batch_docs_for_embedding = []
        
        for idx, paper in enumerate(allowed_sources, start=1):
            doc_text, filename, _, _, c_doi, has_downloaded_pdf = await asyncio.to_thread(_prepare_paper_file_sync, chat_id, paper)
            abstract_text = (paper.snippet or "").strip()

            # Save to DB with full metadata persisted
            local_db = SessionLocal()
            created_doc_id = None
            created_at_str = ""
            try:
                authors_json = json.dumps(paper.authors or [], ensure_ascii=False)
                db_doc = Document(
                    chat_id=chat_id,
                    filename=filename,
                    title=paper.title,
                    authors=authors_json,
                    year=str(paper.year or ""),
                    journal=paper.venue or "",
                    journal_metric=paper.journal_metric or "",
                    doi=c_doi,
                    url=paper.url or "",
                    pdf_url=paper.pdf_url or "",
                    abstract=abstract_text,
                    abstract_type="official" if abstract_text and len(abstract_text) > 80 else "ai_summary",
                    is_oa=paper.is_oa if paper.is_oa is not None else True,
                    access_status="Open Access" if paper.is_oa else "Closed Access",
                    snippet=abstract_text,
                    venue=paper.venue or "",
                    citations=paper.citations or 0,
                    quality_tier=4,
                )
                local_db.add(db_doc)
                local_db.commit()
                local_db.refresh(db_doc)
                created_doc_id = db_doc.id
                created_at_str = db_doc.created_at.isoformat() if db_doc.created_at else ""
            finally:
                local_db.close()

            batch_docs_for_embedding.append((doc_text, filename, chat_id))

            # Stream progressive status event to frontend
            yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': total_to_import, 'doc': {'id': created_doc_id, 'filename': filename, 'created_at': created_at_str, 'index': current_doc_count + idx}})}\n\n"

        # Background batch embedding into Qdrant
        if batch_docs_for_embedding:
            try:
                await asyncio.to_thread(rag.ingest_documents_batch, batch_docs_for_embedding)
            except Exception as e:
                logger.warning(f"[Batch Vector Ingestion Warning]: {e}")

        yield f"data: {json.dumps({'type': 'done', 'total': total_to_import})}\n\n"

    return StreamingResponse(
        event_generator(),
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
    docs_to_ingest = await asyncio.gather(*(asyncio.to_thread(_prepare_paper_file_sync, chat_id, p) for p in allowed_sources))

    # 2. Single batch vector embedding into Qdrant (1 single API call instead of 50 separate calls)
    embedding_tuples = [(d[0], d[1], d[2]) for d in docs_to_ingest]
    try:
        await asyncio.to_thread(rag.ingest_documents_batch, embedding_tuples)
    except Exception as e:
        logger.warning(f"[Batch Vector Ingestion Warning]: {e}")

    # 3. Database commit with full metadata
    import json as _json
    created_docs = []
    for doc_text, fname, _cid, paper, c_doi, _has_pdf in docs_to_ingest:
        abstract_text = (paper.snippet or "").strip()
        authors_json = _json.dumps(paper.authors or [], ensure_ascii=False)
        db_doc = Document(
            chat_id=chat_id,
            filename=fname,
            title=paper.title,
            authors=authors_json,
            year=str(paper.year or ""),
            journal=paper.venue or "",
            journal_metric=paper.journal_metric or "",
            doi=c_doi,
            url=paper.url or "",
            pdf_url=paper.pdf_url or "",
            abstract=abstract_text,
            abstract_type="official" if abstract_text and len(abstract_text) > 80 else "ai_summary",
            is_oa=paper.is_oa if paper.is_oa is not None else True,
            access_status="Open Access" if paper.is_oa else "Closed Access",
            snippet=abstract_text,
            venue=paper.venue or "",
            citations=paper.citations or 0,
            quality_tier=4,
        )
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

@router.post("/chats/{chat_id}/import_doi", response_model=models.DocumentResponse)
async def import_doi_source(chat_id: str, req: models.ImportDoiRequest, db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    current_doc_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    if current_doc_count >= MAX_SOURCES_PER_CHAT:
        raise HTTPException(status_code=400, detail=f"Source limit reached! (Max {MAX_SOURCES_PER_CHAT} sources per notebook). Please remove some sources first.")

    raw_doi = (req.doi or "").strip()
    clean_doi = raw_doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
    clean_doi = re.sub(r'[;.,:)\s]+$', '', clean_doi).strip()
    
    doi_match = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', clean_doi)
    if not doi_match:
        raise HTTPException(status_code=422, detail="Invalid DOI format. Expected format: 10.xxxx/xxxx or https://doi.org/10.xxxx/xxxx")
    
    extracted_doi = doi_match.group(0).strip().rstrip(".")
    
    # Check duplicate in current chat
    existing_sigs = rag.get_existing_notebook_sources_signatures(chat_id)
    if extracted_doi.lower() in existing_sigs.get("dois", set()):
        raise HTTPException(status_code=409, detail=f"This paper (DOI: {extracted_doi}) has already been added to your sources.")
        
    # Resolve metadata from academic APIs
    meta = await asyncio.to_thread(rag.resolve_paper_metadata_by_doi, extracted_doi, fast_only=False)
    if not meta or not meta.get("title"):
        raise HTTPException(status_code=404, detail=f"Publication not found in Crossref/OpenAlex registries for DOI: {extracted_doi}")

    title = meta.get("title", "").strip()
    filename = sanitize_paper_filename(title)
    authors = meta.get("authors") or []
    year = str(meta.get("year") or "N/A")
    venue = meta.get("journal") or meta.get("venue") or "Academic Publication"
    journal_metric = meta.get("journal_metric") or "Peer-Reviewed"
    url = meta.get("url") or f"https://doi.org/{extracted_doi}"
    pdf_url = meta.get("pdf_url") or ""
    abstract_text = meta.get("abstract") or f"Official academic record for '{title}' ({year}). Indexed in Crossref under DOI {extracted_doi}."
    is_oa = meta.get("is_oa", True)

    save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
    has_downloaded_pdf = False

    # Attempt fetching authentic OA PDF
    try:
        fetched_oa = await asyncio.to_thread(
            pdf_exporter.resolve_and_fetch_authentic_pdf,
            doi=extracted_doi,
            title=title,
            direct_url=url,
            candidate_pdf_url=pdf_url
        )
        if fetched_oa and is_authentic_pdf_bytes(fetched_oa):
            with open(save_path, "wb") as f:
                f.write(fetched_oa)
            has_downloaded_pdf = True
    except Exception as e:
        logger.debug(f"[DOI Fetch OA]: {e}")

    if not has_downloaded_pdf:
        doc_text = f"# {title} ({year})\n\n**DOI:** {extracted_doi}  \n**URL:** {url}  \n\n## Abstract & Overview\n\n{abstract_text}\n"
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
        except Exception as e:
            logger.warning(f"[Save doc text Warning]: {e}")

    # Ingest into vector store
    try:
        await asyncio.to_thread(rag.ingest_document, save_path, chat_id)
    except Exception as e:
        logger.warning(f"[DOI Ingest Vector Warning]: {e}")

    authors_json = json.dumps(authors, ensure_ascii=False)
    db_doc = Document(
        chat_id=chat_id,
        filename=filename,
        title=title,
        authors=authors_json,
        year=year,
        journal=venue,
        journal_metric=journal_metric,
        doi=extracted_doi,
        url=url,
        pdf_url=pdf_url,
        abstract=abstract_text,
        abstract_type="official" if abstract_text and len(abstract_text) > 80 else "ai_summary",
        is_oa=is_oa,
        access_status="Open Access (Full PDF Available)" if has_downloaded_pdf else "Publication Brief & Abstract (Direct Download Restricted / HTTP 403)",
        snippet=abstract_text,
        venue=venue,
        citations=meta.get("citations", 0),
        quality_tier=4,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    total_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    return models.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        created_at=db_doc.created_at,
        index=total_count,
        has_full_pdf=has_downloaded_pdf,
        is_oa=is_oa
    )
