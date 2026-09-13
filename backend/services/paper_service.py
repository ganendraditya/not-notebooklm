import os
import re
import json
import logging
import asyncio
from typing import List, Tuple, Dict, Any, AsyncGenerator, Optional
from sqlalchemy.orm import Session

from database import Document, ChatSession, SessionLocal, commit_with_retry
import models
import rag
from providers.academic import resolve_and_fetch_authentic_pdf
from utils.file_utils import (
    UPLOAD_DIR,
    MAX_SOURCES_PER_CHAT,
    sanitize_paper_filename,
)
from utils.pdf_utils import is_authentic_pdf_bytes
from utils.text_processing import clean_doi, normalize_title_str

logger = logging.getLogger("uvicorn.error")

def prepare_paper_file_sync(chat_id: str, paper: models.PaperCandidate) -> Tuple[str, str, str, bool]:
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
    txt_save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename.replace('.pdf', '')}.txt")
    has_downloaded_pdf = False

    if c_doi or paper.pdf_url or paper.url:
        try:
            fetched_oa = resolve_and_fetch_authentic_pdf(
                doi=c_doi,
                title=paper.title,
                direct_url=paper.url or "",
                candidate_pdf_url=paper.pdf_url or ""
            )
            if is_authentic_pdf_bytes(fetched_oa, min_size=1000):
                with open(save_path, "wb") as f:
                    f.write(fetched_oa)
                has_downloaded_pdf = True
        except Exception as e:
            logger.debug(f"[OA Fetch on Import]: {e}")

    if not has_downloaded_pdf:
        try:
            with open(txt_save_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
            filename = filename.replace('.pdf', '') + '.txt'
            save_path = txt_save_path
        except Exception as e:
            logger.warning(f"[Doc text save Warning]: {e}")
    else:
        try:
            parsed_full_text = rag.parse_document_to_markdown(save_path)
            if parsed_full_text and len(parsed_full_text.strip()) > 300:
                doc_text = parsed_full_text
        except Exception as e:
            logger.warning(f"[Parse full text for embedding warning]: {e}")

    # Sync downloaded paper or text summary to S3 storage bucket if configured
    try:
        from services import storage_adapter
        storage_adapter.upload_file(save_path, s3_key=f"{chat_id}_{filename}")
    except Exception as se:
        logger.debug(f"[StorageAdapter Paper Sync Warning]: {se}")

    return (doc_text, filename, c_doi, has_downloaded_pdf)

async def search_academic_papers(query: str, limit: int = 10) -> List[models.PaperCandidate]:
    """Orchestrates query planning and academic paper search."""
    if not query.strip():
        return []
        
    active_llm = rag.get_fast_llm() or rag.get_main_llm()
    
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

def filter_novel_sources(chat_id: str, sources: List[models.PaperCandidate], remaining_slots: int) -> List[models.PaperCandidate]:
    """Filters duplicate papers within a notebook session based on title and DOI signatures."""
    existing_sigs = rag.get_existing_notebook_sources_signatures(chat_id)
    novel_sources = []
    for paper in sources:
        if not rag.is_paper_duplicate(paper.title, paper.doi, existing_sigs):
            novel_sources.append(paper)
            norm = rag.normalize_title_str(paper.title)
            if norm:
                existing_sigs["token_signatures"].append((norm, set(norm.split())))
            if paper.doi:
                existing_sigs["dois"].add(paper.doi.lower().strip())
    return novel_sources[:remaining_slots]

async def import_sources_progressive_stream(
    chat_id: str,
    allowed_sources: List[models.PaperCandidate],
    current_doc_count: int,
    remaining_slots: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """Progressively downloads papers, creates DB entries, and batches embedding into vector store."""
    batch_docs_for_embedding = []
    created_doc_ids = []
    total_to_import = len(allowed_sources)
    
    # Pre-fetch existing chat documents once before entering the loop to eliminate redundant DB roundtrips
    pre_db = SessionLocal()
    existing_docs = []
    try:
        existing_docs = pre_db.query(Document).filter(Document.chat_id == chat_id).all()
    finally:
        pre_db.close()

    doi_map: Dict[str, Any] = {}
    title_entries: List[Tuple[Any, str]] = []
    for d in existing_docs:
        if d.doi:
            doi_map[clean_doi(d.doi)] = d
        d_norm = normalize_title_str(d.title or d.filename)
        if d_norm:
            title_entries.append((d, d_norm))

    try:
        for idx, paper in enumerate(allowed_sources, start=1):
            c_doi = clean_doi(paper.doi) if paper.doi else ""
            existing_doc = None
            if c_doi and c_doi in doi_map:
                existing_doc = doi_map[c_doi]

            if not existing_doc and paper.title:
                norm_cand = normalize_title_str(paper.title)
                if norm_cand:
                    for d, d_norm in title_entries:
                        if norm_cand == d_norm:
                            existing_doc = d
                            break
                        if len(norm_cand) >= 20 and len(d_norm) >= 20 and (norm_cand.startswith(d_norm) or d_norm.startswith(norm_cand)):
                            existing_doc = d
                            break

            if existing_doc:
                created_at_str = existing_doc.created_at.isoformat() if existing_doc.created_at else ""
                has_pdf = (existing_doc.filename or "").lower().endswith(".pdf")
                clean_title = existing_doc.title or (existing_doc.filename or "").replace('.pdf', '').replace('_', ' ').strip()
                yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': total_to_import, 'doc': {'id': existing_doc.id, 'filename': existing_doc.filename, 'title': clean_title, 'created_at': created_at_str, 'index': current_doc_count + len(created_doc_ids) + 1, 'has_full_pdf': has_pdf, 'is_oa': existing_doc.is_oa if existing_doc.is_oa is not None else True}})}\n\n"
                continue

            # Enforce remaining slot limit against novel papers
            if remaining_slots is not None and len(created_doc_ids) >= remaining_slots:
                logger.info(f"[Import Stream] Capacity limit reached ({remaining_slots} novel papers). Halting stream.")
                break

            doc_text, filename, c_doi, has_downloaded_pdf = await asyncio.to_thread(prepare_paper_file_sync, chat_id, paper)
            abstract_text = (paper.snippet or "").strip()

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
                commit_with_retry(local_db)
                local_db.refresh(db_doc)
                created_doc_id = db_doc.id
                created_at_str = db_doc.created_at.isoformat() if db_doc.created_at else ""

                if c_doi:
                    doi_map[c_doi] = db_doc
                new_norm = normalize_title_str(db_doc.title or db_doc.filename)
                if new_norm:
                    title_entries.append((db_doc, new_norm))
            finally:
                local_db.close()

            if created_doc_id:
                created_doc_ids.append(created_doc_id)
            batch_docs_for_embedding.append((doc_text, filename, chat_id))

            clean_doc_title = db_doc.title or (filename or "").replace('.pdf', '').replace('_', ' ').strip()
            yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': total_to_import, 'doc': {'id': created_doc_id, 'filename': filename, 'title': clean_doc_title, 'created_at': created_at_str, 'index': current_doc_count + len(created_doc_ids), 'has_full_pdf': has_downloaded_pdf, 'is_oa': db_doc.is_oa if db_doc.is_oa is not None else True}})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'total': total_to_import})}\n\n"
    except (GeneratorExit, asyncio.CancelledError):
        logger.info(f"[Import Stream Stopped] Stream interrupted. Preserving {len(created_doc_ids)} completed documents.")
    finally:
        if batch_docs_for_embedding:
            try:
                await asyncio.to_thread(rag.ingest_documents_batch, batch_docs_for_embedding)
            except Exception as e:
                logger.warning(f"[Batch Vector Ingestion Warning]: {e}")

async def import_sources_batch(chat_id: str, allowed_sources: List[models.PaperCandidate], db: Session) -> List[models.DocumentResponse]:
    """Batch imports sources synchronously, preparing files, saving to DB, and vectorizing."""
    prepared_results = await asyncio.gather(*(asyncio.to_thread(prepare_paper_file_sync, chat_id, p) for p in allowed_sources))

    embedding_tuples = [(item[0], item[1], chat_id) for item in prepared_results]
    try:
        await asyncio.to_thread(rag.ingest_documents_batch, embedding_tuples)
    except Exception as e:
        logger.warning(f"[Batch Vector Ingestion Warning]: {e}")

    created_docs = []
    for (doc_text, fname, c_doi, _has_pdf), paper in zip(prepared_results, allowed_sources):
        abstract_text = (paper.snippet or "").strip()
        authors_json = json.dumps(paper.authors or [], ensure_ascii=False)
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
        
    commit_with_retry(db)
    for d in created_docs:
        db.refresh(d)
        
    all_current_docs = db.query(Document).filter(Document.chat_id == chat_id).order_by(Document.id.asc()).all()
    id_to_index = {d.id: idx for idx, d in enumerate(all_current_docs, start=1)}
    
    return [
        models.DocumentResponse(
            id=d.id,
            filename=d.filename,
            title=d.title or d.filename.replace(".pdf", "").replace("_", " ").strip(),
            created_at=d.created_at,
            index=id_to_index.get(d.id, 1),
            has_full_pdf=d.filename.endswith(".pdf"),
            is_oa=d.is_oa if d.is_oa is not None else True
        )
        for d in created_docs
    ]

async def import_single_doi_source(chat_id: str, clean_doi_val: str, db: Session) -> Tuple[Document, bool, bool, int]:
    """Resolves paper by DOI, fetches authentic PDF or generates brief, saves to DB and vector store."""
    meta = await asyncio.to_thread(rag.resolve_paper_metadata_by_doi, clean_doi_val, fast_only=False)
    if not meta or not meta.get("title"):
        raise ValueError(f"Publication not found in Crossref/OpenAlex registries for DOI: {clean_doi_val}")

    title = meta.get("title", "").strip()
    filename = sanitize_paper_filename(title)
    authors = meta.get("authors") or []
    year = str(meta.get("year") or "N/A")
    venue = meta.get("journal") or meta.get("venue") or "Academic Publication"
    journal_metric = meta.get("journal_metric") or "Peer-Reviewed"
    url = meta.get("url") or f"https://doi.org/{clean_doi_val}"
    pdf_url = meta.get("pdf_url") or ""
    abstract_text = meta.get("abstract") or f"Official academic record for '{title}' ({year}). Indexed in Crossref under DOI {clean_doi_val}."
    is_oa = meta.get("is_oa", True)

    save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
    txt_save_path = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename.replace('.pdf', '')}.txt")
    has_downloaded_pdf = False

    try:
        fetched_oa = await asyncio.to_thread(
            resolve_and_fetch_authentic_pdf,
            doi=clean_doi_val,
            title=title,
            direct_url=url,
            candidate_pdf_url=pdf_url
        )
        if fetched_oa and is_authentic_pdf_bytes(fetched_oa, min_size=1000):
            with open(save_path, "wb") as f:
                f.write(fetched_oa)
            has_downloaded_pdf = True
    except Exception as e:
        logger.debug(f"[DOI Fetch OA]: {e}")

    if not has_downloaded_pdf:
        doc_text = f"# {title} ({year})\n\n**DOI:** {clean_doi_val}  \n**URL:** {url}  \n\n## Abstract & Overview\n\n{abstract_text}\n"
        try:
            with open(txt_save_path, "w", encoding="utf-8") as f:
                f.write(doc_text)
            filename = filename.replace('.pdf', '') + '.txt'
            save_path = txt_save_path
        except Exception as e:
            logger.warning(f"[Doc text save Warning]: {e}")

    try:
        await asyncio.to_thread(rag.ingest_document, save_path, chat_id, filename)
    except Exception as e:
        logger.warning(f"[DOI Ingest Vector Warning]: {e}")

    # Sync imported paper to S3 storage bucket if configured
    try:
        from services import storage_adapter
        storage_adapter.upload_file(save_path, s3_key=f"{chat_id}_{filename}")
    except Exception as se:
        logger.debug(f"[StorageAdapter DOI Sync Warning]: {se}")

    authors_json = json.dumps(authors, ensure_ascii=False)
    db_doc = Document(
        chat_id=chat_id,
        filename=filename,
        title=title,
        authors=authors_json,
        year=year,
        journal=venue,
        journal_metric=journal_metric,
        doi=clean_doi_val,
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
    commit_with_retry(db)
    db.refresh(db_doc)

    total_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    return db_doc, has_downloaded_pdf, is_oa, total_count
