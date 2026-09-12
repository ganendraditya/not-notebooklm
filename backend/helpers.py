# Re-exports for backward compatibility and clean modular imports
from utils.file_utils import (
    UPLOAD_DIR,
    TEMP_ZIPS_DIR,
    CHAT_MEDIA_DIR,
    MAX_SOURCES_PER_CHAT,
    make_content_disposition,
    sanitize_paper_filename,
    get_doc_file_path,
)
from utils.pdf_utils import (
    is_authentic_pdf_bytes,
    get_authentic_document_pdf,
)
from utils.text_processing import (
    clean_doi,
)

__all__ = [
    "UPLOAD_DIR",
    "TEMP_ZIPS_DIR",
    "CHAT_MEDIA_DIR",
    "MAX_SOURCES_PER_CHAT",
    "make_content_disposition",
    "sanitize_paper_filename",
    "get_doc_file_path",
    "is_authentic_pdf_bytes",
    "get_authentic_document_pdf",
    "clean_doi",
]
