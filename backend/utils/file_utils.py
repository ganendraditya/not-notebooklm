import os
import re
import urllib.parse
from typing import Optional

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
TEMP_ZIPS_DIR = os.path.join(UPLOAD_DIR, "temp_zips")
CHAT_MEDIA_DIR = os.path.join(UPLOAD_DIR, "chat_media")
os.makedirs(TEMP_ZIPS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHAT_MEDIA_DIR, exist_ok=True)

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
    """Returns absolute file path for a chat document safely with dual unescaped/secure fallback."""
    import werkzeug.utils

    raw_chat_id = (chat_id or "").strip()
    raw_fname = (filename or "").strip()
    clean_chat_id = werkzeug.utils.secure_filename(raw_chat_id)
    clean_fname = werkzeug.utils.secure_filename(raw_fname)

    # 1. Candidate paths to inspect (prefer authentic binary PDF on disk if available)
    candidate_paths = [
        # Direct raw path with spaces (how paper files are saved)
        os.path.join(UPLOAD_DIR, f"{raw_chat_id}_{raw_fname}"),
        os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{raw_fname}"),
        # Sanitized secure filename path
        os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{clean_fname}"),
        os.path.join(UPLOAD_DIR, f"None_{raw_fname}"),
        os.path.join(UPLOAD_DIR, f"None_{clean_fname}"),
        os.path.join(UPLOAD_DIR, raw_fname),
        os.path.join(UPLOAD_DIR, clean_fname),
    ]

    # Return first existing file that is an authentic binary PDF (>=1000 bytes)
    for p in candidate_paths:
        if os.path.exists(p) and os.path.getsize(p) >= 1000:
            return p

    # If no binary PDF found, return first existing text/markdown fallback file
    for p in candidate_paths:
        if os.path.exists(p):
            return p

    # Default fallback
    return os.path.join(UPLOAD_DIR, f"{clean_chat_id}_{clean_fname}")
