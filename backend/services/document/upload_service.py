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
from utils.file_utils import UPLOAD_DIR, sanitize_safe_filename
from services.document.metadata_extractor import extract_hybrid_document_metadata

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
