import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Tuple, List, Optional
from database import Document
from helpers import get_doc_file_path, UPLOAD_DIR
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
                if fb.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in fb and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in fb:
                    has_full_pdf = True
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

async def extract_and_enrich_uploaded_file(file_path: str, filename: str) -> Dict[str, Any]:
    """Extracts raw headers, resolves metadata from registries, and audits content for uploads."""
    clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()
    if clean_fn_title.isupper() and len(clean_fn_title) > 8:
        clean_fn_title = clean_fn_title.title()
        
    extracted_doi = ""
    raw_header = ""
    try:
        if filename.lower().endswith(".pdf"):
            import pymupdf
            pdoc = pymupdf.open(file_path)
            if len(pdoc) > 0:
                raw_header = pdoc[0].get_text()[:3000]
            pdoc.close()
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_header = f.read(3000)
    except Exception:
        raw_header = ""

    if raw_header:
        doi_m = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', raw_header)
        if doi_m:
            extracted_doi = doi_m.group(0).strip().rstrip(".")
            extracted_doi = re.sub(r'[;.,:)\s]+$', '', extracted_doi).strip()

    resolved_title = clean_fn_title
    resolved_authors = []
    resolved_year = ""
    resolved_journal = ""
    resolved_metric = "Peer-Reviewed"
    resolved_abstract = ""
    resolved_url = ""
    resolved_doi = extracted_doi

    if extracted_doi or clean_fn_title:
        try:
            meta = await asyncio.to_thread(
                rag.resolve_paper_metadata_by_doi,
                doi=extracted_doi,
                title_fallback=clean_fn_title,
                fast_only=False
            )
            if meta:
                if meta.get("title") and len(meta["title"]) > 5:
                    resolved_title = meta["title"].strip()
                resolved_authors = meta.get("authors") or []
                resolved_year = str(meta.get("year") or "")
                resolved_journal = meta.get("journal") or meta.get("venue") or ""
                resolved_metric = meta.get("journal_metric") or "Peer-Reviewed"
                resolved_abstract = meta.get("abstract") or ""
                resolved_url = meta.get("url") or (f"https://doi.org/{meta.get('doi')}" if meta.get("doi") else "")
                resolved_doi = meta.get("doi") or extracted_doi
        except Exception as e:
            logger.debug(f"[Upload Metadata Resolution Warning]: {e}")

    is_valid_pdf = False
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 35000:
        try:
            with open(file_path, "rb") as f:
                fb = f.read(2048)
                if fb.startswith(b"%PDF-"):
                    is_valid_pdf = True
        except Exception:
            is_valid_pdf = False

    if raw_header and (not resolved_abstract or resolved_title == clean_fn_title):
        try:
            ai_audit = await asyncio.to_thread(
                rag.audit_paper_metadata_with_ai,
                paper_title=resolved_title,
                raw_authors=resolved_authors,
                raw_journal=resolved_journal,
                raw_year=resolved_year,
                raw_doi=resolved_doi,
                raw_citations=0,
                raw_abstract_or_html=raw_header[:3500],
                is_oa=is_valid_pdf
            )
            if ai_audit:
                if ai_audit.get("abstract") and len(ai_audit["abstract"]) > 40:
                    resolved_abstract = ai_audit["abstract"]
                if ai_audit.get("title") and len(ai_audit["title"]) > 5:
                    resolved_title = ai_audit["title"]
                if ai_audit.get("authors"):
                    resolved_authors = ai_audit["authors"]
                if ai_audit.get("year"):
                    resolved_year = ai_audit["year"]
                if ai_audit.get("journal"):
                    resolved_journal = ai_audit["journal"]
                if ai_audit.get("journal_metric"):
                    resolved_metric = ai_audit["journal_metric"]
        except Exception as upload_audit_err:
            logger.debug(f"[Upload AI Audit Warning]: {upload_audit_err}")

    return {
        "title": resolved_title,
        "authors": resolved_authors,
        "year": resolved_year,
        "journal": resolved_journal,
        "journal_metric": resolved_metric,
        "doi": resolved_doi,
        "url": resolved_url,
        "abstract": resolved_abstract,
        "is_valid_pdf": is_valid_pdf
    }
