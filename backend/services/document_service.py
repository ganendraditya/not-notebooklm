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

    is_valid_pdf = False
    if os.path.exists(file_path) and os.path.getsize(file_path) >= 35000:
        try:
            with open(file_path, "rb") as f:
                first_bytes = f.read(2048)
                is_valid_pdf = is_authentic_pdf_bytes(first_bytes, min_size=512)
        except Exception as e:
            logger.error(f"[Upload PDF Validation Error] Failed to read {file_path}: {e}")
            is_valid_pdf = False

    state = {
        "title": clean_fn_title,
        "authors": [],
        "year": "",
        "journal": "",
        "journal_metric": "Peer-Reviewed",
        "abstract": "",
        "url": "",
        "doi": extracted_doi,
        "is_valid_pdf": is_valid_pdf
    }

    # 1. Fetch from Academic API
    if state["doi"] or state["title"]:
        try:
            meta = await asyncio.to_thread(
                rag.resolve_paper_metadata_by_doi,
                doi=state["doi"],
                title_fallback=state["title"],
                fast_only=False
            )
            if meta:
                if meta.get("title") and len(meta["title"]) > 5: state["title"] = meta["title"].strip()
                if meta.get("authors"): state["authors"] = meta["authors"]
                if meta.get("year"): state["year"] = str(meta["year"])
                if meta.get("journal") or meta.get("venue"): state["journal"] = meta.get("journal") or meta.get("venue")
                if meta.get("journal_metric"): state["journal_metric"] = meta["journal_metric"]
                if meta.get("abstract"): state["abstract"] = meta["abstract"]
                if meta.get("doi"): state["doi"] = meta["doi"]
                if meta.get("url"): state["url"] = meta["url"]
                elif state["doi"]: state["url"] = f"https://doi.org/{state['doi']}"
        except Exception as e:
            logger.error(f"[Upload Metadata Resolution Error]: {e}")

    # 2. Fallback to AI Audit if missing critical info
    if raw_header and (not state["abstract"] or state["title"] == clean_fn_title):
        try:
            ai_audit = await asyncio.to_thread(
                rag.audit_paper_metadata_with_ai,
                paper_title=state["title"],
                raw_authors=state["authors"],
                raw_journal=state["journal"],
                raw_year=state["year"],
                raw_doi=state["doi"],
                raw_citations=0,
                raw_abstract_or_html=raw_header[:3500],
                is_oa=is_valid_pdf
            )
            if ai_audit:
                if ai_audit.get("abstract") and len(ai_audit["abstract"]) > 40: state["abstract"] = ai_audit["abstract"]
                if ai_audit.get("title") and len(ai_audit["title"]) > 5: state["title"] = ai_audit["title"]
                if ai_audit.get("authors"): state["authors"] = ai_audit["authors"]
                if ai_audit.get("year"): state["year"] = ai_audit["year"]
                if ai_audit.get("journal"): state["journal"] = ai_audit["journal"]
                if ai_audit.get("journal_metric"): state["journal_metric"] = ai_audit["journal_metric"]
        except Exception as upload_audit_err:
            logger.error(f"[Upload AI Audit Warning]: {upload_audit_err}")

    return state
