import os
import re
import json
import shutil
import logging
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import UploadFile

from database import Document
from utils.file_utils import UPLOAD_DIR
from utils.pdf_utils import is_authentic_pdf_bytes

logger = logging.getLogger("uvicorn.error")

def extract_and_enrich_uploaded_file(file_path: str, filename: str) -> Dict[str, Any]:
    """Purely local and instant metadata extraction using the exact filename as title."""
    clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()
        
    extracted_doi = ""
    raw_header = ""
    enriched_abstract = ""
    
    # Check PDF magic bytes locally
    is_valid_pdf = False
    if os.path.exists(file_path):
        sz = os.path.getsize(file_path)
        if filename.lower().endswith(".pdf") and sz >= 100:
            try:
                with open(file_path, "rb") as f:
                    first_bytes = f.read(2048)
                    is_valid_pdf = is_authentic_pdf_bytes(first_bytes, min_size=100)
            except Exception as e:
                logger.error(f"[Upload PDF Validation Error] Failed to read {file_path}: {e}")
                is_valid_pdf = False

    # Extract basic text header to find DOI if present
    try:
        if filename.lower().endswith(".pdf") and is_valid_pdf:
            import pymupdf
            pdoc = pymupdf.open(file_path)
            if len(pdoc) > 0:
                raw_header = pdoc[0].get_text()[:3000]
            pdoc.close()
        elif not filename.lower().endswith(".pdf"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_header = f.read(3000)
                # If text/markdown file, populate abstract snippet from the content so DB has full context preview
                if not enriched_abstract:
                    enriched_abstract = raw_header[:1000]
    except Exception:
        raw_header = ""

    if raw_header:
        doi_m = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', raw_header)
        if doi_m:
            extracted_doi = doi_m.group(0).strip().rstrip(".")
            extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()

    return {
        "title": clean_fn_title,
        "authors": [],
        "year": "",
        "journal": "",
        "journal_metric": "Uploaded Document",
        "abstract": enriched_abstract,
        "url": f"https://doi.org/{extracted_doi}" if extracted_doi else "",
        "doi": extracted_doi,
        "is_valid_pdf": is_valid_pdf
    }

def handle_document_upload(chat_id: str, file: UploadFile, db: Session) -> Tuple[Document, str, Dict[str, Any]]:
    """
    Handles physical file storage and DB row creation for uploaded documents.
    Returns (created_db_doc, file_path, enriched_metadata).
    """
    import werkzeug.utils

    clean_chat_id = werkzeug.utils.secure_filename(chat_id)
    clean_fname = werkzeug.utils.secure_filename(file.filename or "uploaded_doc")
    file_path = os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{clean_fname}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    enriched = extract_and_enrich_uploaded_file(file_path, file.filename or clean_fname)

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
        is_oa=True if enriched.get("is_valid_pdf", False) else False,
        access_status="Open Access (Full PDF Available)" if enriched.get("is_valid_pdf", False) else "Uploaded Document",
        quality_tier=4
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    return db_doc, file_path, enriched
