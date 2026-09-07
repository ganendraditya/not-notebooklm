import os
from typing import Tuple, Optional
from utils.file_utils import get_doc_file_path

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
