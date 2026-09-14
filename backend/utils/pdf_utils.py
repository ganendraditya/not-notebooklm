import os
import re
from typing import Tuple, Optional
from utils.file_utils import get_doc_file_path

TITLE_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
    "been", "being", "have", "has", "had", "does", "did", "doing", "would",
    "should", "could", "their", "they", "them", "about", "above", "across",
    "after", "again", "against", "all", "almost", "along", "also", "although",
    "always", "among", "any", "into", "through", "during", "before", "under",
    "around", "over", "such", "than", "too", "very", "can", "will", "just",
    "using", "based", "via", "towards", "study", "approach", "new", "method"
}

def verify_pdf_title_match(pdf_bytes: bytes, expected_title: str) -> bool:
    """
    In-memory title sanity verification: ensures candidate PDF matches expected title.
    Inspects only the first 2 pages (to account for repository splash/cover pages).
    Normalizes HTML/LaTeX formatting and computes fuzzy keyword token overlap.
    """
    if not expected_title or not pdf_bytes or len(pdf_bytes) < 1000:
        return True

    cleaned_title = re.sub(r"<[^>]+>", " ", expected_title)
    cleaned_title = re.sub(r"\\[a-zA-Z]+", " ", cleaned_title)
    cleaned_title = re.sub(r"[\$\^\{\}_~#&%@!\?:\(\)\[\]\"\'\.,;/\\]", " ", cleaned_title)
    words = re.findall(r"[a-zA-Z0-9]{3,}", cleaned_title.lower())
    keywords = [w for w in words if w not in TITLE_STOPWORDS]
    if not keywords:
        keywords = words[:5]
    if not keywords:
        return True

    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return False
        text = ""
        for i in range(min(2, len(doc))):
            text += " " + doc[i].get_text()
        doc.close()
    except Exception:
        return False

    text_lower = text.lower()
    matched = sum(1 for kw in keywords if kw in text_lower)
    if len(keywords) == 1:
        return matched >= 1
    return (matched / len(keywords)) >= 0.5

def is_authentic_pdf_bytes(data: bytes, min_size: int = 1000) -> bool:
    """Checks if raw bytes represent an authentic non-synthetic binary PDF."""
    if not data or len(data) < min_size:
        return False
    if not data.startswith(b"%PDF-"):
        return False
    if b"NOTBOOKLM" in data or b"OFFICIAL PUBLICATION ARCHIVE RECORD" in data:
        return False
    return True

def is_binary_pdf(file_path: str) -> bool:
    """Checks if a file on disk is an authentic binary PDF by inspecting magic bytes."""
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        if os.path.getsize(file_path) < 1000:
            return False
        with open(file_path, "rb") as f:
            header = f.read(2048)
            return is_authentic_pdf_bytes(header, min_size=500)
    except Exception:
        return False

def get_authentic_document_pdf(chat_id: str, doc_filename: str) -> Tuple[Optional[bytes], str]:
    """
    Returns authentic binary PDF bytes and a clean attachment filename for any document.
    Instant non-blocking disk inspection — returns (None, clean_filename) if not on disk.
    """
    file_path = get_doc_file_path(chat_id, doc_filename)
    clean_dl_name = doc_filename if doc_filename.lower().endswith(".pdf") else f"{doc_filename}.pdf"
    
    # If authentic publisher binary PDF exists on disk (>=1000 bytes), return directly
    if os.path.exists(file_path) and is_binary_pdf(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                if is_authentic_pdf_bytes(data, min_size=1000):
                    return data, clean_dl_name
        except Exception:
            pass

    # Instant return: No authentic binary PDF stored on disk
    return None, clean_dl_name
