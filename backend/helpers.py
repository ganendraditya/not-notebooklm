import os
import re
import urllib.parse
from typing import List, Optional
import rag
import pdf_exporter

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
TEMP_ZIPS_DIR = os.path.join(UPLOAD_DIR, "temp_zips")
os.makedirs(TEMP_ZIPS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SOURCES_PER_CHAT = 250

def make_content_disposition(disposition_type: str, filename: str) -> str:
    """Generates an RFC 5987 / RFC 6266 compliant Content-Disposition header supporting Unicode."""
    ascii_fn = re.sub(r'[^\x20-\x7E]', '_', filename).replace('"', '')
    if not ascii_fn.strip():
        ascii_fn = "document.pdf"
    encoded_fn = urllib.parse.quote(filename, safe='')
    return f"{disposition_type}; filename=\"{ascii_fn}\"; filename*=UTF-8''{encoded_fn}"

def sanitize_paper_filename(title: str, max_length: int = 200) -> str:
    """Sanitizes paper title into a clean filename preserving full words without mid-word truncation."""
    clean = re.sub(r'<[^>]+>', '', title).strip()
    clean = re.sub(r'[\/*?:"<>|]', '', clean).strip()
    clean = re.sub(r'\s+', ' ', clean)
    if len(clean) > max_length:
        truncated = clean[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > int(max_length * 0.7):
            clean = truncated[:last_space].strip()
        else:
            clean = truncated.strip()
    return f"{clean}.pdf" if not clean.lower().endswith(".pdf") else clean

def get_doc_file_path(chat_id: str, filename: str) -> str:
    """Returns absolute file path for a chat document across working directories."""
    p1 = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
    if os.path.exists(p1):
        return p1
    p2 = os.path.abspath(os.path.join(os.getcwd(), "uploads", f"{chat_id}_{filename}"))
    if os.path.exists(p2):
        return p2
    return p1

def get_or_generate_document_pdf(chat_id: str, doc_filename: str) -> tuple:
    """
    Returns authentic binary PDF bytes and a clean attachment filename for any document.
    """
    file_path = get_doc_file_path(chat_id, doc_filename)
    clean_dl_name = doc_filename if doc_filename.lower().endswith(".pdf") else f"{doc_filename}.pdf"
    
    # 1. If authentic publisher binary PDF exists on disk (>50KB), return directly
    if os.path.exists(file_path) and pdf_exporter.is_binary_pdf(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                if len(data) >= 50000 and data.startswith(b"%PDF-"):
                    return data, clean_dl_name
        except Exception:
            pass

    # 2. Extract structured metadata & text from disk or DB
    raw_content = ""
    if os.path.exists(file_path):
        try:
            if pdf_exporter.is_binary_pdf(file_path):
                import pymupdf
                doc = pymupdf.open(file_path)
                raw_content = "\n".join([page.get_text() for page in doc]).strip()
                doc.close()
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_content = f.read()
        except Exception:
            raw_content = ""

    title = doc_filename.replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace(".md", "").strip()
    doi = ""
    year = ""
    journal = "Academic Publication"
    journal_metric = "Peer-Reviewed"
    abstract = ""
    url = ""
    authors = []

    if raw_content.startswith("#"):
        first_line = raw_content.split("\n")[0].replace("#", "").strip()
        year_match = re.search(r'\((\d{4})\)', first_line)
        if year_match:
            year = year_match.group(1)
            title = first_line.replace(f"({year})", "").strip()
        else:
            title = first_line

    doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', raw_content)
    if doi_match:
        doi = doi_match.group(0).strip().rstrip(".")

    url_match = re.search(r'(?:https?://[^\s\n\)\"]+)', raw_content)
    if url_match and "doi.org" in url_match.group(0):
        url = url_match.group(0)

    abs_match = re.search(r'## Abstract & Overview\s*([\s\S]*?)(?:$|##)', raw_content, re.IGNORECASE)
    if not abs_match:
        abs_match = re.search(r'ABSTRACT & SCHOLARLY OVERVIEW\s*([\s\S]*?)(?:Keywords:|I\.)', raw_content, re.IGNORECASE)
    if abs_match:
        abstract = abs_match.group(1).strip()
    elif len(raw_content) > 50 and not raw_content.startswith("%PDF-"):
        abstract = raw_content.strip()

    candidate_pdf_url = ""
    if doi or title:
        meta = rag.resolve_paper_metadata_by_doi(doi=doi, title_fallback=title, fast_only=False)
        if meta:
            title = meta.get("title") or title
            authors = meta.get("authors") or authors
            year = str(meta.get("year")) if meta.get("year") else year
            journal = meta.get("journal") or journal
            journal_metric = meta.get("journal_metric") or journal_metric
            if not abstract and meta.get("abstract"):
                abstract = meta.get("abstract")
            if not url and meta.get("url"):
                url = meta.get("url")
            candidate_pdf_url = meta.get("pdf_url") or ""

    oa_pdf = pdf_exporter.resolve_and_fetch_authentic_pdf(
        doi=doi,
        title=title,
        direct_url=url,
        candidate_pdf_url=candidate_pdf_url
    )
    if oa_pdf and len(oa_pdf) >= 1024 and oa_pdf.startswith(b"%PDF-"):
        try:
            with open(file_path, "wb") as f:
                f.write(oa_pdf)
        except Exception:
            pass
        return oa_pdf, clean_dl_name

    pdf_bytes = pdf_exporter.generate_academic_pdf_bytes(
        title=title,
        authors=authors,
        year=year,
        journal=journal,
        journal_metric=journal_metric,
        doi=doi,
        abstract=abstract,
        url=url
    )
    
    try:
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
    except Exception:
        pass

    return pdf_bytes, clean_dl_name
