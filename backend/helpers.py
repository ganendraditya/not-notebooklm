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

MAX_SOURCES_PER_CHAT = 300

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
    """Returns absolute file path for a chat document across working directories and legacy fallbacks."""
    # 1. Standard per-chat upload path
    if chat_id:
        p1 = os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")
        if os.path.exists(p1):
            return p1
        p1_cwd = os.path.abspath(os.path.join(os.getcwd(), "uploads", f"{chat_id}_{filename}"))
        if os.path.exists(p1_cwd):
            return p1_cwd
            
    # 2. Legacy fallback with None_ prefix
    p_none = os.path.join(UPLOAD_DIR, f"None_{filename}")
    if os.path.exists(p_none):
        return p_none

    # 3. Direct filename fallback
    p_direct = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(p_direct):
        return p_direct

    return os.path.join(UPLOAD_DIR, f"{chat_id}_{filename}")

def get_authentic_document_pdf(chat_id: str, doc_filename: str) -> tuple:
    """
    Returns authentic binary PDF bytes and a clean attachment filename for any document.
    Instant non-blocking disk inspection — returns (None, clean_filename) if not on disk.
    """
    file_path = get_doc_file_path(chat_id, doc_filename)
    clean_dl_name = doc_filename if doc_filename.lower().endswith(".pdf") else f"{doc_filename}.pdf"
    
    # 1. If authentic publisher binary PDF exists on disk (>=35KB), return directly
    if os.path.exists(file_path) and pdf_exporter.is_binary_pdf(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                # Check that it is not a legacy synthetic template PDF
                if len(data) >= 35000 and data.startswith(b"%PDF-") and b"NOTBOOKLM SCHOLARLY ARCHIVE" not in data and b"OFFICIAL PUBLICATION ARCHIVE RECORD" not in data:
                    return data, clean_dl_name
        except Exception:
            pass

    # Instant return: No authentic binary PDF stored on disk
    return None, clean_dl_name

# Backward compatibility alias
get_or_generate_document_pdf = get_authentic_document_pdf
