import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple

from utils.pdf_utils import is_authentic_pdf_bytes
from utils.text_processing import clean_doi, is_title_match

logger = logging.getLogger("uvicorn.error")

def extract_raw_header_text(file_path: str, filename: str, max_chars: int = 6000) -> Tuple[str, bool]:
    """Extracts raw front matter / header text from PDF, Word, or text document."""
    ext = os.path.splitext(filename)[1].lower()
    is_valid_pdf = False
    raw_header = ""

    if not os.path.exists(file_path):
        return "", False

    if ext == ".pdf":
        sz = os.path.getsize(file_path)
        if sz >= 100:
            try:
                with open(file_path, "rb") as f:
                    first_bytes = f.read(2048)
                    is_valid_pdf = is_authentic_pdf_bytes(first_bytes, min_size=100)
            except Exception as e:
                logger.error(f"[Metadata Extractor] PDF read error {file_path}: {e}")
                is_valid_pdf = False

        if is_valid_pdf:
            try:
                import pymupdf
                with pymupdf.open(file_path) as pdoc:
                    pages_to_check = min(len(pdoc), 3)
                    chunks = [pdoc[i].get_text() for i in range(pages_to_check)]
                    raw_header = "\n".join(chunks)[:max_chars]
            except Exception as e:
                logger.debug(f"[Metadata Extractor] PyMuPDF header extraction failed: {e}")
                raw_header = ""
    elif ext in (".docx", ".doc"):
        try:
            from rag.parsers import parse_docx_file
            full_docx = parse_docx_file(file_path)
            raw_header = full_docx[:max_chars]
        except Exception as e:
            logger.debug(f"[Metadata Extractor] Docx extraction error: {e}")
            raw_header = ""
    else:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_header = f.read(max_chars)
        except Exception as e:
            logger.debug(f"[Metadata Extractor] Text file read error: {e}")
            raw_header = ""

    return raw_header, is_valid_pdf

async def resolve_tier1_doi(raw_header: str) -> Optional[Dict[str, Any]]:
    """Tier 1: Detects DOI in document header and resolves official metadata via Crossref / OpenAlex."""
    if not raw_header:
        return None

    doi_m = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', raw_header)
    if not doi_m:
        return None

    raw_matched = doi_m.group(0).strip().rstrip(".")
    clean_matched = re.sub(r'[;.,:)\s]+$', '', raw_matched).strip()
    extracted_doi = clean_doi(clean_matched)
    if not extracted_doi:
        return None

    try:
        from providers.academic.metadata_fetchers import fetch_crossref_metadata_by_doi, fetch_openalex_metadata_by_doi
        cr_meta = await asyncio.to_thread(fetch_crossref_metadata_by_doi, extracted_doi)
        if not cr_meta:
            cr_meta = await asyncio.to_thread(fetch_openalex_metadata_by_doi, extracted_doi)

        if cr_meta and cr_meta.get("title"):
            return {
                "title": cr_meta.get("title", ""),
                "authors": cr_meta.get("authors") or [],
                "year": str(cr_meta.get("year") or ""),
                "journal": cr_meta.get("journal") or "",
                "journal_metric": "Peer-Reviewed",
                "abstract": cr_meta.get("abstract") or "",
                "url": cr_meta.get("landing") or f"https://doi.org/{extracted_doi}",
                "doi": extracted_doi,
                "citations": cr_meta.get("citations", 0),
                "is_verified_academic": True,
                "document_type": "paper",
                "tier": 1
            }
    except Exception as e:
        logger.debug(f"[Tier 1 DOI Enrichment Warning]: {e}")

    return None

async def resolve_tier2_crossref_title(clean_fn_title: str, raw_header: str) -> Optional[Dict[str, Any]]:
    """Tier 2: Queries Crossref using candidate title if no DOI was found in raw text."""
    candidate_titles = []
    if clean_fn_title and len(clean_fn_title.split()) >= 4 and len(clean_fn_title) >= 20:
        candidate_titles.append(clean_fn_title)

    # Inspect first few lines of raw_header for candidate title
    if raw_header:
        lines = [line.strip() for line in raw_header.split("\n") if len(line.strip()) >= 20]
        for line in lines[:3]:
            # Exclude generic headers
            low = line.lower()
            if not any(g in low for g in ["contents lists", "journal homepage", "elsevier", "springer", "abstract", "researchgate", "http"]):
                if len(line.split()) >= 4 and line not in candidate_titles:
                    candidate_titles.append(line)

    if not candidate_titles:
        return None

    import urllib.parse
    import requests

    headers = {"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.app)"}
    for cand in candidate_titles[:2]:
        try:
            url = f"https://api.crossref.org/works?query.title={urllib.parse.quote(cand)}&rows=1"
            resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=4)
            if resp.status_code == 200:
                items = resp.json().get("message", {}).get("items", [])
                if items:
                    data = items[0]
                    cr_title_list = data.get("title", [])
                    cr_title = cr_title_list[0] if cr_title_list else ""
                    if cr_title and is_title_match(cand, cr_title, threshold=0.80):
                        doi = data.get("DOI", "")
                        authors = [
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in data.get("author", [])
                            if a.get("family") or a.get("given")
                        ]
                        container = data.get("container-title", [])
                        journal = container[0] if container else ""
                        issued_parts = (data.get("issued") or {}).get("date-parts", [])
                        issued = issued_parts[0] if issued_parts and isinstance(issued_parts, list) else []
                        year = str(issued[0]) if issued and isinstance(issued, list) else ""
                        citations = data.get("is-referenced-by-count", 0)
                        landing = data.get("URL", f"https://doi.org/{doi}" if doi else "")

                        return {
                            "title": cr_title,
                            "authors": authors,
                            "year": year,
                            "journal": journal,
                            "journal_metric": "Peer-Reviewed",
                            "abstract": "",
                            "url": landing,
                            "doi": doi,
                            "citations": citations,
                            "is_verified_academic": True,
                            "document_type": "paper",
                            "tier": 2
                        }
        except Exception as e:
            logger.debug(f"[Tier 2 Crossref Title Lookup Warning]: {e}")

    return None

async def resolve_tier3_ai_inspector(clean_fn_title: str, raw_header: str) -> Optional[Dict[str, Any]]:
    """Tier 3: AI Document Inspector via Fast LLM for theses (skripsi), dissertations, and reports."""
    if not raw_header or len(raw_header.strip()) < 40:
        return None

    try:
        from rag.llm_factory import get_fast_llm
        fast_llm = get_fast_llm()
        if not fast_llm:
            return None

        sample_text = raw_header[:2500].strip()
        prompt = f"""You are an academic document metadata extractor. Analyze the front matter/cover page of this uploaded document and extract its metadata in strict JSON format.

DOCUMENT TEXT:
\"\"\"
{sample_text}
\"\"\"

TASK:
1. Determine if this document is an academic work (e.g. skripsi / undergraduate thesis, master's thesis, PhD dissertation, technical report, research paper, or academic CV).
2. Extract the actual document title (clean, without all-caps clutter, and without generic prefixes like "SKRIPSI", "TESIS", "LAPORAN AKHIR", or "TUGAS AKHIR"). If unclear, use: "{clean_fn_title}".
3. Identify the PRIMARY AUTHOR(S) who authored this work.
   - For theses/skripsi/dissertations: Extract ONLY the student author(s).
   - CRITICAL: NEVER include academic advisors, supervisors, dosen pembimbing, or examiners (penguji) as authors!
   - If author is unknown or personal notes, return an empty array [].
4. Publication, completion, or defense year (e.g. "2024"). If unknown, return "".
5. Institution / University / Organization (e.g. "Universitas Islam Indonesia", "Japan Atomic Energy Agency"). If unknown, return "".
6. Determine document_type: "thesis" | "paper" | "report" | "cv" | "document".
7. Extract a concise abstract or summary if present (up to 400 chars).

Respond ONLY with valid JSON (no markdown fences, no explanation):
{{
  "is_academic_work": true/false,
  "document_type": "thesis" | "paper" | "report" | "cv" | "document",
  "title": "string",
  "authors": ["string"],
  "year": "string",
  "institution": "string",
  "abstract": "string"
}}"""

        resp = await fast_llm.acomplete(prompt)
        raw_resp = resp.text.strip()
        raw_resp = re.sub(r'^```(?:json)?\s*', '', raw_resp, flags=re.I)
        raw_resp = re.sub(r'\s*```$', '', raw_resp)
        data = json.loads(raw_resp)

        doc_type = data.get("document_type", "document").lower()
        institution = (data.get("institution") or "").strip()
        authors = data.get("authors") or []
        # Filter out supervisor keywords in author names if LLM slipped
        cleaned_authors = []
        for a in authors:
            a_clean = a.strip()
            a_low = a_clean.lower()
            if not any(sw in a_low for sw in ["pembimbing", "supervisor", "advisor", "penguji", "examiner", "dosen"]):
                cleaned_authors.append(a_clean)

        title = (data.get("title") or "").strip() or clean_fn_title
        year = str(data.get("year") or "").strip()
        if not re.match(r'^\d{4}$', year):
            year = ""

        # Format thesis/report journal tag cleanly for standard citations
        if doc_type in ("thesis", "skripsi", "dissertation"):
            journal = f"[Thesis, {institution}]" if institution else "[Thesis]"
            journal_metric = "Academic Thesis"
            access_status = "Academic Thesis"
            is_verified = True
        elif doc_type == "report":
            journal = f"[Technical Report, {institution}]" if institution else "[Technical Report]"
            journal_metric = "Technical Report"
            access_status = "Institutional Report"
            is_verified = True
        elif doc_type == "paper":
            journal = institution or "Scholarly Paper"
            journal_metric = "Academic Paper"
            access_status = "Academic Paper"
            is_verified = True
        else:
            journal = ""
            journal_metric = "Uploaded Document"
            access_status = "Uploaded Document"
            is_verified = False

        return {
            "title": title,
            "authors": cleaned_authors,
            "year": year,
            "journal": journal,
            "journal_metric": journal_metric,
            "access_status": access_status,
            "abstract": (data.get("abstract") or "").strip(),
            "url": "",
            "doi": "",
            "citations": 0,
            "is_verified_academic": is_verified,
            "document_type": doc_type,
            "tier": 3
        }
    except Exception as e:
        logger.debug(f"[Tier 3 AI Document Inspector Warning]: {e}")

    return None

async def extract_hybrid_document_metadata(file_path: str, filename: str) -> Dict[str, Any]:
    """
    Unified 3-Tier Hybrid Academic Metadata Extraction:
    - Tier 1: Direct DOI Extraction & Crossref / OpenAlex Registry Lookup
    - Tier 2: Crossref Title Fuzzy Matching
    - Tier 3: AI Document Inspector (Fast LLM) for Skripsi, Theses & Reports
    """
    clean_fn_title = re.sub(r'<[^>]+>', '', os.path.splitext(filename)[0]).replace("_", " ").strip()
    raw_header, is_valid_pdf = extract_raw_header_text(file_path, filename)

    extracted_doi = ""
    if raw_header:
        doi_m = re.search(r'10\.\d{4,9}/[^\s\n<>\"\'{}|\\^`]+', raw_header)
        if doi_m:
            raw_matched = doi_m.group(0).strip().rstrip(".")
            clean_matched = re.sub(r'[;.,:)\s]+$', '', raw_matched).strip()
            extracted_doi = clean_doi(clean_matched)

    # 1. Tier 1: DOI Lookup
    tier1_res = await resolve_tier1_doi(raw_header)
    if tier1_res:
        tier1_res["is_valid_pdf"] = is_valid_pdf
        return tier1_res

    # 2. Tier 2: Crossref Title Search
    tier2_res = await resolve_tier2_crossref_title(clean_fn_title, raw_header)
    if tier2_res:
        tier2_res["is_valid_pdf"] = is_valid_pdf
        return tier2_res

    # 3. Tier 3: AI Document Inspector for Skripsi / Thesis / Reports
    tier3_res = await resolve_tier3_ai_inspector(clean_fn_title, raw_header)
    if tier3_res:
        tier3_res["is_valid_pdf"] = is_valid_pdf
        if extracted_doi:
            tier3_res["doi"] = extracted_doi
            tier3_res["url"] = f"https://doi.org/{extracted_doi}"
        return tier3_res

    # 4. Standard Fallback for non-academic personal files
    return {
        "title": clean_fn_title,
        "authors": [],
        "year": "",
        "journal": "",
        "journal_metric": "Uploaded Document",
        "abstract": raw_header[:1000] if raw_header else "",
        "url": f"https://doi.org/{extracted_doi}" if extracted_doi else "",
        "doi": extracted_doi,
        "is_valid_pdf": is_valid_pdf,
        "citations": 0,
        "is_verified_academic": bool(extracted_doi),
        "document_type": "document",
        "tier": 0
    }
