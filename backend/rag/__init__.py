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
    get_existing_notebook_sources_signatures,
    search_academic_papers_planned,
    search_academic_papers,
    is_paper_duplicate,
)

from services.search.metadata_resolver_service import (
    resolve_paper_metadata_by_doi,
    fetch_full_abstract_by_doi
)

from services.search.llm_evaluator_service import (
    plan_academic_search,
    judge_and_filter_papers_with_llm,
    audit_paper_metadata_with_ai
)

from utils.text_processing import (
    is_valid_academic_title,
    normalize_title_str,
    clean_academic_abstract,
    is_valid_abstract_content,
    extract_abstract_from_html,
    is_title_match,
    is_ai_synthesized_overview
)

from .prompts import (
    get_general_chat_system_prompt,
    get_source_deletion_prompt,
    get_search_synthesis_prompt,
    get_workspace_analysis_system_prompt,
)

from .intent import (
    is_simple_conversational,
    is_technical_discussion,
    is_sources_meta_query,
    classify_user_intent
)

from .vector_store import (
    embed_model,
    vector_store,
    qdrant_client,
    delete_document_vectors,
    delete_qdrant_vectors,
    get_flashrank_ranker,
    ingest_document_text,
    ingest_documents_batch,
    ingest_document,
)

from .llm_factory import (
    create_llm_instances,
    get_llm_factory,
    get_main_llm,
    get_fast_llm,
    clear_llm_cache,
)

from .engine import (
    query_chat,
    generate_chat_title,
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
    "judge_and_filter_papers_with_llm",
    "clean_academic_abstract",
    "is_valid_abstract_content",
    "extract_abstract_from_html",
    "is_title_match",
    "is_ai_synthesized_overview",
    "audit_paper_metadata_with_ai",
    "resolve_paper_metadata_by_doi",
    "fetch_full_abstract_by_doi",
    "search_academic_papers",
    # Prompts
    "get_general_chat_system_prompt",
    "get_source_deletion_prompt",
    "get_search_synthesis_prompt",
    "get_workspace_analysis_system_prompt",
    # Intent
    "is_simple_conversational",
    "is_technical_discussion",
    "is_sources_meta_query",
    "classify_user_intent",
    # Vector Store
    "embed_model",
    "vector_store",
    "qdrant_client",
    "delete_document_vectors",
    "delete_qdrant_vectors",
    "get_flashrank_ranker",
    # LLM & Factory
    "create_llm_instances",
    "get_llm_factory",
    "get_main_llm",
    "get_fast_llm",
    "clear_llm_cache",
    # Engine & Ingestion
    "ingest_document_text",
    "ingest_documents_batch",
    "ingest_document",
    "query_chat",
    "generate_chat_title",
]
