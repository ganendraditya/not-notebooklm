import os
import re
import json
import shutil
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import UploadFile

from database import Document, commit_with_retry
from utils.file_utils import UPLOAD_DIR, sanitize_safe_filename, MAX_SOURCES_PER_CHAT
from utils.pdf_utils import is_authentic_pdf_bytes
from services.document.metadata_extractor import extract_hybrid_document_metadata
from rag.format_parsers import extract_bibtex_entries, extract_ris_entries
from providers.academic.pdf_racing_resolver import resolve_and_fetch_authentic_pdf

logger = logging.getLogger("uvicorn.error")
_METADATA_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def extract_and_enrich_uploaded_file(file_path: str, filename: str) -> Dict[str, Any]:
    """Synchronous bridge for hybrid metadata extraction."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return _METADATA_POOL.submit(asyncio.run, extract_hybrid_document_metadata(file_path, filename)).result()
        return asyncio.run(extract_hybrid_document_metadata(file_path, filename))
    except Exception as e:
        logger.debug(f"[Sync metadata extraction fallback]: {e}")
        clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()
        return {
            "title": clean_fn_title,
            "authors": [],
            "year": "",
            "journal": "",
            "journal_metric": "Uploaded Document",
            "abstract": "",
            "url": "",
            "doi": "",
            "is_valid_pdf": False,
            "is_verified_academic": False
        }

async def handle_document_upload(chat_id: str, file: UploadFile, db: Session) -> Tuple[Document, str, Dict[str, Any]]:
    """
    Handles physical file storage, 3-tier hybrid metadata extraction (DOI -> Crossref -> Fast LLM),
    and DB row creation for uploaded documents.
    Returns (created_db_doc, file_path, enriched_metadata).
    """
    clean_chat_id = sanitize_safe_filename(chat_id)
    clean_fname = sanitize_safe_filename(file.filename or "uploaded_doc")
    file_path = os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{clean_fname}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Sync to S3 storage bucket if configured
    from services import storage_adapter
    storage_adapter.upload_file(file_path, s3_key=f"{clean_chat_id}_{clean_fname}")

    # 3-Tier Hybrid metadata extraction
    enriched = await extract_hybrid_document_metadata(file_path, file.filename or clean_fname)

    authors_json = json.dumps(enriched.get("authors", []), ensure_ascii=False) if enriched.get("authors") else None
    db_doc = Document(
        chat_id=chat_id,
        filename=clean_fname,
        title=enriched.get("title", ""),
        authors=authors_json,
        year=enriched.get("year", ""),
        journal=enriched.get("journal", ""),
        journal_metric=enriched.get("journal_metric", "Uploaded Document"),
        doi=enriched.get("doi", ""),
        url=enriched.get("url", ""),
        abstract=enriched.get("abstract", ""),
        abstract_type="official" if enriched.get("abstract") and len(enriched.get("abstract")) > 80 else "ai_summary",
        is_oa=True if enriched.get("is_verified_academic") and enriched.get("is_valid_pdf") else False,
        access_status=enriched.get("access_status") or ("Verified Publication (Uploaded)" if enriched.get("is_verified_academic") else "Uploaded Document"),
        quality_tier=4
    )
    db.add(db_doc)
    commit_with_retry(db)
    db.refresh(db_doc)

    return db_doc, file_path, enriched


async def handle_bib_or_ris_split_upload(
    chat_id: str,
    file: UploadFile,
    ext: str,
    db: Session
) -> list[Tuple[Document, str, Dict[str, Any]]]:
    """
    Splits multi-entry BibTeX or RIS file into individual standalone Document records.
    Each entry becomes its own searchable document in the workspace with clean metadata.
    """
    clean_chat_id = sanitize_safe_filename(chat_id)
    clean_fname = sanitize_safe_filename(file.filename or "uploaded_collection")

    # Read uploaded file content
    content_bytes = await file.read()
    raw_text = content_bytes.decode("utf-8", errors="replace")

    if ext in (".bib", ".bibtex"):
        entries = extract_bibtex_entries(raw_text)
    elif ext == ".ris":
        entries = extract_ris_entries(raw_text)
    else:
        entries = []

    if not entries:
        # Fallback: rewind file pointer for regular single document upload handler
        await file.seek(0)
        return []

    # Also archive the master collection file on disk
    master_path = os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{clean_fname}")
    try:
        with open(master_path, "wb") as f:
            f.write(content_bytes)
        from services import storage_adapter
        storage_adapter.upload_file(master_path, s3_key=f"{clean_chat_id}_{clean_fname}")
    except Exception as e:
        logger.debug(f"[Master bib/ris archive error]: {e}")

    existing_count = db.query(Document).filter(Document.chat_id == chat_id).count()
    remaining_slots = max(0, MAX_SOURCES_PER_CHAT - existing_count)
    if remaining_slots == 0:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Source limit reached! This conversation already contains {existing_count}/{MAX_SOURCES_PER_CHAT} sources."
        )

    entries = entries[:remaining_slots]
    results = []
    base_root, _ = os.path.splitext(clean_fname)

    for idx, entry in enumerate(entries):
        entry_key = sanitize_safe_filename(entry.get("key") or entry.get("title") or f"{base_root}_{idx + 1}")
        entry_key = entry_key[:45].strip("._-") or f"ref_{idx + 1}"

        authors_list = entry.get("authors", [])
        authors_json = json.dumps(authors_list, ensure_ascii=False) if authors_list else None
        doi = entry.get("doi", "").strip()
        url = entry.get("url", "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"

        title = entry.get("title") or entry_key

        # Proactively attempt authentic open-access PDF resolution via DOI / URL
        has_downloaded_pdf = False
        pdf_bytes = None
        if doi or url:
            try:
                pdf_bytes = await asyncio.to_thread(
                    resolve_and_fetch_authentic_pdf,
                    doi=doi,
                    title=title,
                    direct_url=url or "",
                    candidate_pdf_url=""
                )
                if pdf_bytes and is_authentic_pdf_bytes(pdf_bytes, min_size=1000):
                    has_downloaded_pdf = True
            except Exception as e:
                logger.debug(f"[Bib/RIS PDF Fetch Warning]: {e}")

        if has_downloaded_pdf and pdf_bytes:
            entry_fname = f"{entry_key}_{idx + 1}.pdf" if len(entries) > 1 else f"{entry_key}.pdf"
            storage_fname = f"{clean_chat_id}_{entry_fname}"
            entry_file_path = os.path.join(UPLOAD_DIR, storage_fname)
            with open(entry_file_path, "wb") as pf:
                pf.write(pdf_bytes)
            is_oa = True
            access_status = "Open Access (Full PDF Available)"
            metric_name = "Peer-Reviewed"
        else:
            entry_fname = f"{entry_key}_{idx + 1}.txt" if len(entries) > 1 else f"{entry_key}.txt"
            storage_fname = f"{clean_chat_id}_{entry_fname}"
            entry_file_path = os.path.join(UPLOAD_DIR, storage_fname)

            # Write clean human-readable text file with title, authors, year, DOI, and abstract
            content_lines = [f"Title: {title}"]
            if authors_list:
                content_lines.append(f"Authors: {', '.join(authors_list)}")
            if entry.get("year"):
                content_lines.append(f"Year: {entry.get('year')}")
            if entry.get("journal"):
                content_lines.append(f"Journal/Venue: {entry.get('journal')}")
            if doi:
                content_lines.append(f"DOI: {doi}")
            if url:
                content_lines.append(f"URL: {url}")
            content_lines.append("")
            if entry.get("abstract"):
                content_lines.append("Abstract:")
                content_lines.append(entry.get("abstract"))
            else:
                content_lines.append("Abstract:")
                content_lines.append("No abstract available in citation metadata.")

            with open(entry_file_path, "w", encoding="utf-8") as ef:
                ef.write("\n".join(content_lines))

            is_oa = False
            access_status = "Publication Brief & Abstract (Uploaded)"
            metric_name = "Uploaded Reference"

        from services import storage_adapter
        storage_adapter.upload_file(entry_file_path, s3_key=storage_fname)

        db_doc = Document(
            chat_id=chat_id,
            filename=entry_fname,
            title=title,
            authors=authors_json,
            year=entry.get("year", ""),
            journal=entry.get("journal", ""),
            journal_metric=metric_name,
            doi=doi,
            url=url,
            abstract=entry.get("abstract", ""),
            abstract_type="official" if entry.get("abstract") else "ai_summary",
            is_oa=is_oa,
            access_status=access_status,
            quality_tier=4
        )
        db.add(db_doc)
        commit_with_retry(db)
        db.refresh(db_doc)

        enriched = {
            "title": title,
            "authors": authors_list,
            "year": entry.get("year", ""),
            "journal": entry.get("journal", ""),
            "journal_metric": metric_name,
            "doi": doi,
            "url": url,
            "abstract": entry.get("abstract", ""),
            "is_valid_pdf": has_downloaded_pdf,
            "is_verified_academic": has_downloaded_pdf,
            "access_status": access_status
        }
        results.append((db_doc, entry_file_path, enriched))

    return results
