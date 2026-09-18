import os
import re
import json
import asyncio
import logging
from typing import List, Tuple, Dict, Any, Optional, Callable
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from database import SessionLocal, Document as DBDocument
from rag.prompts import get_workspace_analysis_system_prompt
from rag.formatters import format_clean_response, extract_structured_citations
from rag.parsers import parse_document_to_markdown
from utils.file_utils import get_doc_file_path
from rag.llm_factory import astream_llm_response
from rag.token_budget import (
    allocate_token_budget,
    count_tokens,
    pack_text_into_token_budget,
)

logger = logging.getLogger("uvicorn.error")

def extract_key_sentences_from_chunk(text: str, limit: int = 2) -> List[str]:
    """Extracts 1-2 distinct, substantive verbatim sentences from a chunk for grounding."""
    raw_sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    candidates = []
    for s in raw_sentences:
        s_clean = s.strip().replace('\n', ' ')
        if 40 <= len(s_clean) <= 300 and not s_clean.startswith('#') and not s_clean.startswith('['):
            if not re.match(r'^\d+\.?\s*$', s_clean):
                candidates.append(s_clean)
                if len(candidates) >= limit:
                    break
    return candidates

async def _load_single_doc_snippet_async(
    idx_fname_chat: tuple,
    db_records: Dict[str, Any],
    total_doc_count: int,
    per_doc_token_budget: Optional[int] = None,
    model_name: Optional[str] = None
) -> Tuple[bool, str]:
    """Helper that reads and formats text from a single document record or file on disk with dynamic token budgeting."""
    i, fname, chat_id = idx_fname_chat
    fpath = get_doc_file_path(chat_id, fname)
    content_snippet = ""
    db_record = db_records.get(fname, {})
    is_full_paper = False
    
    # 1. Try parsing full document text properly (PDF/DOCX/TXT/MD)
    if os.path.exists(fpath):
        fsize = os.path.getsize(fpath)
        try:
            parsed_text = await asyncio.to_thread(parse_document_to_markdown, fpath)
            if parsed_text and len(parsed_text.strip()) >= 150:
                if "NOTBOOKLM" in parsed_text:
                    is_full_paper = False
                elif fpath.lower().endswith(".txt") and fsize < 100:
                    is_full_paper = False
                elif fpath.lower().endswith(".pdf") and fsize < 10000:
                    is_full_paper = False
                else:
                    is_full_paper = True
                
                target_budget = per_doc_token_budget if (per_doc_token_budget and per_doc_token_budget > 0) else 6000
                content_snippet = pack_text_into_token_budget(
                    parsed_text,
                    budget_tokens=target_budget,
                    model_name=model_name
                )
        except Exception as parse_err:
            logger.debug(f"[Workspace Pipeline] Doc Parse Error for {fname}: {parse_err}")

    # 2. If physical file parse failed or short stub: read from DB metadata (fast, non-blocking)
    if (not is_full_paper) and db_record:
        meta_parts = []
        d_title = db_record.get("title") or fname.replace(".pdf", "").replace("_", " ")
        d_year = db_record.get("year") or ""
        d_venue = db_record.get("journal") or db_record.get("venue") or ""
        d_doi = db_record.get("doi") or ""
        d_abstract = db_record.get("abstract") or db_record.get("snippet") or ""
        
        meta_parts.append(f"# {d_title} ({d_year})")
        if d_venue: meta_parts.append(f"**Venue/Journal:** {d_venue}")
        if d_doi: meta_parts.append(f"**DOI:** {d_doi}")
        if d_abstract: meta_parts.append(f"## Abstract & Overview\n{d_abstract}")
        
        if content_snippet:
            meta_parts.append(f"## Parsed Text Snippet\n{content_snippet}")
            
        content_snippet = "\n\n".join(meta_parts)
        
    if not content_snippet:
        content_snippet = f"(Dokumen: {fname})"
        
    doc_display_title = (db_record.get("title") if db_record and db_record.get("title") else fname.replace(".pdf", "").replace("_", " ").strip())
    if doc_display_title.isupper() and len(doc_display_title) > 8:
        doc_display_title = doc_display_title.title()

    status_label = "FULL-TEXT ORIGINAL AVAILABLE (All Sections Included)" if is_full_paper else "ABSTRACT & OFFICIAL METADATA ONLY"
    has_doi_label = f"Official DOI: {db_record.get('doi')}" if (db_record and db_record.get("doi")) else "Official DOI: None / Campus Repository"

    return (
        is_full_paper,
        (
            f"--- DOCUMENT [{i+1}] ---\n"
            f"Document Number: [{i+1}]\n"
            f"Publication Title: {doc_display_title}\n"
            f"File Name: {fname}\n"
            f"Document Status: {status_label}\n"
            f"{has_doi_label}\n"
            f"Source Document Content:\n{content_snippet}\n"
        )
    )

async def _retrieve_hybrid_workspace_context(
    chat_id: str,
    query: str,
    local_docs: List[str],
    db_records: Dict[str, Any],
    report_status: Optional[Callable] = None,
    max_rag_tokens: int = 6000,
    model_name: Optional[str] = None
) -> Tuple[str, Dict[str, List[str]]]:
    """
    Hybrid semantic retrieval for large workspaces (> 4 documents):
    1. Builds a concise catalog overview for all workspace documents.
    2. Retrieves top semantically relevant chunks from Qdrant vector index.
    3. Reranks chunks via FlashRank Cross-Encoder to fit optimal context budget.
    4. Packs chunks strictly within max_rag_tokens to prevent Stanford 'Lost in the Middle' degradation.
    """
    total_docs = len(local_docs)
    catalog_lines = [f"=== WORKSPACE DOCUMENTS CATALOG ({total_docs} DOCUMENTS) ==="]

    for i, fname in enumerate(local_docs):
        d = db_records.get(fname, {})
        title = d.get("title") or fname.replace(".pdf", "").replace("_", " ").strip()
        year = f" ({d.get('year')})" if d.get("year") else ""
        venue = f" | Venue: {d.get('journal') or d.get('venue')}" if (d.get("journal") or d.get("venue")) else ""
        doi = f" | DOI: {d.get('doi')}" if d.get("doi") else ""
        snippet = (d.get("abstract") or d.get("snippet") or "").strip()
        if len(snippet) > 350:
            snippet = snippet[:350] + "..."
        catalog_lines.append(f"[{i+1}] {title}{year}{venue}{doi}\nSummary: {snippet or '(No summary available)'}")

    catalog_text = "\n\n".join(catalog_lines)

    retrieved_blocks = []
    pre_stored_rag_map: Dict[str, List[str]] = {}
    try:
        from rag.vector_store import vector_store, embed_model
        from llama_index.core import VectorStoreIndex
        from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator

        if report_status:
            await report_status("Searching relevant sections across workspace documents in vector store...")

        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
        filters = MetadataFilters(
            filters=[MetadataFilter(key="chat_id", operator=FilterOperator.EQ, value=chat_id)]
        )
        retriever = index.as_retriever(filters=filters, similarity_top_k=25)
        nodes = await retriever.aretrieve(query)

        if nodes:
            if report_status:
                await report_status("Reranking most relevant excerpts with Cross-Encoder...")

            try:
                from flashrank import RerankRequest
                from rag.vector_store import get_flashrank_ranker
                ranker = get_flashrank_ranker()
                if not ranker:
                    raise RuntimeError("FlashRank Ranker unavailable")
                passages = [{"id": idx, "text": n.node.get_content()[:1500]} for idx, n in enumerate(nodes)]
                reranked = ranker.rerank(RerankRequest(query=query, passages=passages))[:12]
                selected_nodes = [nodes[item["id"]] for item in reranked if "id" in item and 0 <= item["id"] < len(nodes)]
            except Exception as rank_err:
                logger.debug(f"[Workspace Hybrid] FlashRank fallback: {rank_err}")
                selected_nodes = nodes[:12]

            total_tokens = count_tokens(catalog_text, model_name=model_name)
            for idx, n in enumerate(selected_nodes, start=1):
                fname = n.node.metadata.get("filename", "Dokumen")
                sec = n.node.metadata.get("section") or n.node.metadata.get("breadcrumb") or ""
                sec_lbl = f" - Section: {sec}" if sec else ""
                doc_idx = local_docs.index(fname) + 1 if fname in local_docs else idx
                chunk_text = n.node.get_content()
                block_candidate = (
                    f"--- RELEVANT EXCERPT Document [{doc_idx}] (Source: {fname}{sec_lbl}) ---\n{chunk_text}"
                )
                block_tokens = count_tokens(block_candidate, model_name=model_name)

                # Token Waterfall budget check (preventing Lost in the Middle)
                if total_tokens + block_tokens > max_rag_tokens:
                    if len(retrieved_blocks) >= 2:
                        break
                    remaining_budget = max(0, max_rag_tokens - total_tokens)
                    if remaining_budget >= 150:
                        packed_chunk = pack_text_into_token_budget(chunk_text, remaining_budget, model_name=model_name)
                        retrieved_blocks.append(
                            f"--- RELEVANT EXCERPT Document [{doc_idx}] (Source: {fname}{sec_lbl}) ---\n{packed_chunk}"
                        )
                    break

                retrieved_blocks.append(block_candidate)
                total_tokens += block_tokens

                doc_key = str(doc_idx)
                if doc_key not in pre_stored_rag_map:
                    pre_stored_rag_map[doc_key] = []
                for s in extract_key_sentences_from_chunk(chunk_text, limit=2):
                    if s not in pre_stored_rag_map[doc_key] and len(pre_stored_rag_map[doc_key]) < 3:
                        pre_stored_rag_map[doc_key].append(s)
    except Exception as e:
        logger.warning(f"[Workspace Hybrid] Vector retrieval encountered error: {e}")

    if retrieved_blocks:
        return (
            f"{catalog_text}\n\n"
            f"=== DEEP EXCERPTS FROM DOCUMENTS RELEVANT TO QUERY ({len(retrieved_blocks)} HIGHEST-RANKED SECTIONS) ===\n\n"
            + "\n\n".join(retrieved_blocks),
            pre_stored_rag_map
        )
    else:
        # Fallback if vector index has no chunks yet: use compact snippets with budget protection
        per_doc_fallback = max(500, max_rag_tokens // max(1, total_docs))
        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async(
                (i, fname, chat_id),
                db_records,
                total_docs,
                per_doc_token_budget=per_doc_fallback,
                model_name=model_name
            ) for i, fname in enumerate(local_docs))
        )
        fb_map = {str(i): extract_key_sentences_from_chunk(s, limit=2) for i, (_, s) in enumerate(loaded_results, start=1)}
        return "\n\n".join([snippet for _, snippet in loaded_results]), fb_map

async def handle_workspace_analysis_pipeline(
    chat_id: str,
    query: str,
    local_docs: List[str],
    formatted_history: List[LlamaChatMessage],
    target_llm,
    report_status,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """Direct full-context or hybrid semantic comparative synthesis for workspace documents with dynamic token waterfall."""
    db_records: Dict[str, Any] = {}
    db = SessionLocal()
    try:
        for d in db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all():
            db_records[d.filename] = {
                "id": d.id,
                "title": d.title,
                "year": d.year,
                "journal": d.journal,
                "venue": d.venue,
                "doi": d.doi,
                "url": d.url,
                "pdf_url": d.pdf_url,
                "abstract": d.abstract,
                "snippet": d.snippet,
                "is_oa": d.is_oa,
                "filename": d.filename,
            }
    finally:
        db.close()

    total_doc_count = len(local_docs)
    pre_stored_rag_map: Dict[str, List[str]] = {}

    # 1. Resolve active model name safely (handles real LLMs and test mocks)
    model_name = None
    if target_llm is not None:
        raw_m = getattr(target_llm, "model", None)
        if isinstance(raw_m, str):
            model_name = raw_m
        else:
            raw_mn = getattr(target_llm, "model_name", None)
            if isinstance(raw_mn, str):
                model_name = raw_mn

    base_system_prompt = get_workspace_analysis_system_prompt(total_doc_count)
    token_budget = allocate_token_budget(
        model_name=model_name,
        system_prompt=base_system_prompt,
        user_query=query,
    )

    if total_doc_count <= 4:
        await report_status("Reading full content of loaded workspace documents...")
        if token_budget.max_context >= 128_000:
            per_doc_budget = min(20_000, max(4_000, token_budget.max_rag_tokens * 3 // total_doc_count))
        else:
            per_doc_budget = max(600, token_budget.max_rag_tokens // max(1, total_doc_count))

        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async(
                (i, fname, chat_id),
                db_records,
                total_doc_count,
                per_doc_token_budget=per_doc_budget,
                model_name=model_name
            ) for i, fname in enumerate(local_docs))
        )
        full_docs_context = "\n\n".join([snippet for _, snippet in loaded_results])
        for i, (_, snippet) in enumerate(loaded_results, start=1):
            pre_stored_rag_map[str(i)] = extract_key_sentences_from_chunk(snippet, limit=2)
    else:
        full_docs_context, pre_stored_rag_map = await _retrieve_hybrid_workspace_context(
            chat_id=chat_id,
            query=query,
            local_docs=local_docs,
            db_records=db_records,
            report_status=report_status,
            max_rag_tokens=token_budget.max_rag_tokens,
            model_name=model_name
        )
    
    system_prompt_text = get_workspace_analysis_system_prompt(total_doc_count)

    # Ingest active declarative research profile facts from SQLite (Issue #11)
    try:
        from services.memory_service import get_active_profile_facts, format_profile_for_prompt
        profile_db = SessionLocal()
        try:
            active_facts = get_active_profile_facts(profile_db, chat_id, max_tokens=250)
            if active_facts:
                profile_block = format_profile_for_prompt(active_facts)
                if profile_block:
                    system_prompt_text = f"{system_prompt_text}\n\n{profile_block}"
        finally:
            profile_db.close()
    except Exception as mem_err:
        logger.debug(f"[Workspace Pipeline] Profile memory injection skipped: {mem_err}")

    system_msg = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=system_prompt_text
    )
    context_msg = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=f"=== AUTHORITATIVE REFERENCE DOCUMENTS CONTEXT ({total_doc_count} DOCUMENTS) ===\n\n{full_docs_context}"
    )
    chat_msgs = [
        system_msg,
        *(formatted_history if formatted_history else []),
        context_msg,
        LlamaChatMessage(role=MessageRole.USER, content=query)
    ]
    
    await report_status("Synthesizing comparative findings and formatting response...")
    raw_content = await astream_llm_response(target_llm, chat_msgs, on_delta=on_delta)

    clean_text, llm_citations = extract_structured_citations(raw_content)

    # Initial document-level evidence quotes from Main LLM and RAG index
    # Note: Precise per-cell evidence highlighting is handled on-demand via the Fast LLM highlight service.
    merged_citations: Dict[str, List[str]] = {**pre_stored_rag_map}
    for k, v in llm_citations.items():
        clean_k = str(k).strip("[]")
        if clean_k not in merged_citations:
            merged_citations[clean_k] = []
        if isinstance(v, list):
            for quote in v:
                if quote not in merged_citations[clean_k]:
                    merged_citations[clean_k].append(quote)
        elif isinstance(v, str) and v not in merged_citations[clean_k]:
            merged_citations[clean_k].append(v)

    if merged_citations:
        draft_content = f"{clean_text}\n\n<!-- CITATION_MAP: {json.dumps(merged_citations, ensure_ascii=False)} -->"
    else:
        draft_content = clean_text

    draft_content = format_clean_response(draft_content)
    return draft_content
