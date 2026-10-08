# Re-exports for backward compatibility and clean modular imports
from utils.file_utils import (
    UPLOAD_DIR,
    TEMP_ZIPS_DIR,
    CHAT_MEDIA_DIR,
    MAX_SOURCES_PER_CHAT,
    MAX_DOCUMENT_FILE_SIZE_BYTES,
    MAX_TOTAL_STORAGE_BYTES,
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
from utils.network_utils import (
    is_safe_external_url,
)

__all__ = [
    "UPLOAD_DIR",
    "TEMP_ZIPS_DIR",
    "CHAT_MEDIA_DIR",
    "MAX_SOURCES_PER_CHAT",
    "MAX_DOCUMENT_FILE_SIZE_BYTES",
    "MAX_TOTAL_STORAGE_BYTES",
    "make_content_disposition",
    "sanitize_paper_filename",
    "get_doc_file_path",
    "is_authentic_pdf_bytes",
    "get_authentic_document_pdf",
    "clean_doi",
    "is_safe_external_url",
]
