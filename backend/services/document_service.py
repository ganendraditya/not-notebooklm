import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Tuple, List, Optional
from database import Document
from helpers import get_doc_file_path, UPLOAD_DIR, is_authentic_pdf_bytes, clean_doi
import rag
import pdf_exporter

logger = logging.getLogger("uvicorn.error")

def calculate_doc_quality(chat_id: str, d: Document) -> Tuple[int, bool, int]:
    """Calculates quality score for duplicate cleanup (prefers authentic full PDF > metadata brief)."""
    fp = get_doc_file_path(chat_id, d.filename)
    sz = os.path.getsize(fp) if os.path.exists(fp) else 0
    has_full_pdf = False
    if os.path.exists(fp) and sz >= 35000:
        try:
            with open(fp, "rb") as f:
                fb = f.read(2048)
                has_full_pdf = is_authentic_pdf_bytes(fb, min_size=512)
        except Exception:
            has_full_pdf = False
            
    score = 0
    if has_full_pdf:
        score += 10000 + min(sz // 1024, 5000)
    if d.doi:
        score += 500
    if d.authors and d.authors != "[]" and "Academic Researchers" not in d.authors:
        score += 300
    if d.journal and "Academic Publication" not in d.journal:
        score += 200
    if d.abstract and len(d.abstract) > 100:
        score += min(len(d.abstract), 500)
        
    return (score, has_full_pdf, d.id)

def extract_and_enrich_uploaded_file(file_path: str, filename: str) -> Dict[str, Any]:
    """Purely local and instant metadata extraction using the exact filename as title."""
    clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()
        
    extracted_doi = ""
    raw_header = ""
    
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
        "abstract": "",
        "url": f"https://doi.org/{extracted_doi}" if extracted_doi else "",
        "doi": extracted_doi,
        "is_valid_pdf": is_valid_pdf
    }

async def check_and_fetch_authentic_pdf_on_demand(doc: Document, file_path: str) -> Tuple[bool, str]:
    """
    Validates if local file is authentic PDF. If not, but document has OA metadata,
    it attempts an on-demand background fetch from open-access repositories.
    
    Returns (is_authentic_pdf, content_markdown)
    """
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    is_authentic_pdf = False
    
    # 1. Local Disk Validation (DRY)
    if os.path.exists(file_path) and file_size >= 35000:
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(2048)
                is_authentic_pdf = is_authentic_pdf_bytes(first_bytes, min_size=512)
        except Exception:
            is_authentic_pdf = False

    new_content = ""

    # 2. On-demand fallback: if doc is OA or has PDF link but local file is not PDF, try fast download
    if not is_authentic_pdf and (doc.is_oa or doc.pdf_url or doc.doi):
        db_doi = clean_doi(doc.doi)
        try:
            fetched_oa = await asyncio.to_thread(
                pdf_exporter.resolve_and_fetch_authentic_pdf,
                doi=db_doi,
                title=doc.title,
                direct_url=doc.url or "",
                candidate_pdf_url=doc.pdf_url or ""
            )
            if fetched_oa and is_authentic_pdf_bytes(fetched_oa, min_size=35000):
                with open(file_path, "wb") as f:
                    f.write(fetched_oa)
                is_authentic_pdf = True
                
                # Re-extract markdown content from new PDF
                try:
                    import pymupdf4llm
                    new_content = await asyncio.to_thread(pymupdf4llm.to_markdown, file_path)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[On-demand OA Fetch Warning]: {e}")
            
    return is_authentic_pdf, new_content
