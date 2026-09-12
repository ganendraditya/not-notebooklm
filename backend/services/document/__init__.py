# Facade for Document Domain Services
from services.document.upload_service import (
    extract_and_enrich_uploaded_file,
    handle_document_upload,
)
from services.document.duplicate_service import (
    calculate_doc_quality,
    clean_chat_duplicates,
)
from services.document.content_service import (
    check_and_fetch_authentic_pdf_on_demand,
    get_document_full_content,
)

__all__ = [
    "extract_and_enrich_uploaded_file",
    "handle_document_upload",
    "calculate_doc_quality",
    "clean_chat_duplicates",
    "check_and_fetch_authentic_pdf_on_demand",
    "get_document_full_content",
]
