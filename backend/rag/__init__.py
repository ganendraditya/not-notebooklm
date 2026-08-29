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
    judge_and_filter_papers_with_llm,
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

from .prompts import (
    get_general_chat_system_prompt,
    get_source_deletion_prompt,
    get_search_synthesis_prompt,
    get_workspace_analysis_system_prompt,
    get_agentic_system_prompt
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
    delete_qdrant_vectors,
)

from .streamer import (
    parse_sse_stream,
    llm_stream_generator,
    create_streaming_response
)

from .engine import (
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
    "get_agentic_system_prompt",
    # Intent
    "is_simple_conversational",
    "is_technical_discussion",
    "is_sources_meta_query",
    "classify_user_intent",
    # Vector Store
    "embed_model",
    "vector_store",
    "qdrant_client",
    "delete_qdrant_vectors",
    # Streamer
    "parse_sse_stream",
    "llm_stream_generator",
    "create_streaming_response",
    # Engine & Agent
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
