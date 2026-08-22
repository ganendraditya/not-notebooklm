"""
RAG Package for Not-NotebookLM
Exports unified parsing, scholarly search & metadata resolution, and Vector Engine APIs.
"""

from .parsers import (
    parse_docx_file,
    parse_bibtex_text,
    parse_ris_text,
    parse_csv_file,
    parse_document_to_markdown,
)

from .search import (
    is_valid_academic_title,
    plan_academic_search,
    normalize_title_str,
    get_existing_notebook_sources_signatures,
    is_paper_duplicate,
    search_academic_papers_planned,
    clean_academic_abstract,
    is_valid_abstract_content,
    extract_abstract_from_html,
    is_title_match,
    is_ai_synthesized_overview,
    audit_paper_metadata_with_ai,
    resolve_paper_metadata_by_doi,
    fetch_full_abstract_by_doi,
    search_academic_papers,
)

from .engine import (
    vector_store,
    qdrant_client,
    delete_qdrant_vectors,
    create_llm_instances,
    ingest_document_text,
    ingest_documents_batch,
    ingest_document,
    web_search_and_ingest,
    fetch_and_ingest_doi,
    query_chat,
    generate_chat_title,
    ninerouter_llm,
    freellm_llm,
    gemini_llm,
    groq_llm,
)

__all__ = [
    # Parsers
    "parse_docx_file",
    "parse_bibtex_text",
    "parse_ris_text",
    "parse_csv_file",
    "parse_document_to_markdown",
    # Search & Metadata
    "is_valid_academic_title",
    "plan_academic_search",
    "normalize_title_str",
    "get_existing_notebook_sources_signatures",
    "is_paper_duplicate",
    "search_academic_papers_planned",
    "clean_academic_abstract",
    "is_valid_abstract_content",
    "extract_abstract_from_html",
    "is_title_match",
    "is_ai_synthesized_overview",
    "audit_paper_metadata_with_ai",
    "resolve_paper_metadata_by_doi",
    "fetch_full_abstract_by_doi",
    "search_academic_papers",
    # Engine & Agent
    "vector_store",
    "qdrant_client",
    "delete_qdrant_vectors",
    "create_llm_instances",
    "ingest_document_text",
    "ingest_document",
    "web_search_and_ingest",
    "fetch_and_ingest_doi",
    "query_chat",
    "generate_chat_title",
    "ninerouter_llm",
    "freellm_llm",
    "gemini_llm",
    "groq_llm",
]
