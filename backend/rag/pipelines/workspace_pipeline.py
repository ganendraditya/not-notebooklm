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

async def _load_single_doc_snippet_async(idx_fname_chat: tuple, db_records: Dict[str, Any], total_doc_count: int) -> Tuple[bool, str]:
    """Helper that reads and formats text from a single document record or file on disk."""
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
                max_chars = 48000 if total_doc_count > 20 else 80000
                content_snippet = parsed_text[:max_chars]
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
    report_status: Optional[Callable] = None
) -> str:
    """
    Hybrid semantic retrieval for large workspaces (> 4 documents):
    1. Builds a concise catalog overview for all workspace documents.
    2. Retrieves top semantically relevant chunks from Qdrant vector index.
    3. Reranks chunks via FlashRank Cross-Encoder to fit optimal context budget.
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

            pre_stored_rag_map: Dict[str, List[str]] = {}
            for idx, n in enumerate(selected_nodes, start=1):
                fname = n.node.metadata.get("filename", "Dokumen")
                sec = n.node.metadata.get("section") or n.node.metadata.get("breadcrumb") or ""
                sec_lbl = f" - Section: {sec}" if sec else ""
                doc_idx = local_docs.index(fname) + 1 if fname in local_docs else idx
                chunk_text = n.node.get_content()
                retrieved_blocks.append(
                    f"--- RELEVANT EXCERPT Document [{doc_idx}] (Source: {fname}{sec_lbl}) ---\n{chunk_text}"
                )

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
        # Fallback if vector index has no chunks yet: use compact snippets
        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async((i, fname, chat_id), db_records, total_docs) for i, fname in enumerate(local_docs))
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
    """Direct full-context or hybrid semantic comparative synthesis for workspace documents."""
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
    if total_doc_count <= 4:
        await report_status("Reading full content of loaded workspace documents...")
        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async((i, fname, chat_id), db_records, total_doc_count) for i, fname in enumerate(local_docs))
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
            report_status=report_status
        )
    
    system_prompt_text = (
        f"{get_workspace_analysis_system_prompt(total_doc_count)}\n\n"
        "CRITICAL INSTRUCTIONS FOR SYNTHESIS & ANALYSIS:\n"
        "- STRICT LANGUAGE MIRRORING: You MUST ALWAYS respond in the EXACT same language or dialect as the user query (e.g. English -> English, Indonesian -> Indonesian, Chinese -> Chinese (中文), Korean -> Korean (한국어), Spanish -> Spanish (Español), Japanese -> Japanese (日本語), etc.). Zero unsolicited translation or cross-language mixing.\n"
        "- ZERO CONVERSATIONAL PREAMBLE: Begin your response directly with the factual answer or findings. Strictly avoid conversational filler or introductory throat-clearing (e.g. do NOT start with 'Berdasarkan dokumen...', 'Based on the provided document...', 'In the paper...', etc.). State the findings directly.\n"
        "- EMPIRICAL METRICS PRECISION: When reporting empirical performance, accuracy, or benchmark scores, ALWAYS provide the exact final absolute metrics (e.g. 'F1 scores of 85.99 on DL-PS, 75.15 on EC-MT, and 71.53 on EC-UQ') alongside any relative improvements. NEVER report only improvement deltas (+1.08) when final absolute metrics are present.\n"
        "- DIRECT NEGATIVE ABSTENTION & UNMENTIONED ACTIONS: If any requested aspect, metric, parameter, mechanism, or platform is not explicitly documented or discussed in the text, you MUST state in the FIRST SENTENCE that the information is not mentioned or provided in the paper (e.g. 'This information is not mentioned or provided in the paper.'). If the question asks how or why an action is performed when the authors do not mention performing that action (false premise), state directly: 'The paper does not mention [action].' Do NOT speculate, extrapolate, or attempt to explain adjacent mechanisms or general architecture.\n"
        "- Respond strictly and proportionally to what the user asks. If the user asks a simple question (e.g. counting, listing, or checking status), answer directly and concisely without unsolicited long tables or essays.\n"
        "- When the user explicitly asks to summarize, analyze, compare, or generate chapters/sections, write a structured, highly analytical synthesis. Cover all comparison dimensions asked by the user, maintain dense academic conciseness (avoid overly verbose repetitive preamble), and ensure all points and sentences are fully and cleanly concluded.\n"
        "- DO NOT refuse with excuses about copyright or partial text. Leverage the available document text fully.\n\n"
        "STRICT IEEE CITATION & CITATION_MAP REQUIREMENTS (MANDATORY BEFORE COMPLETION):\n"
        "1. IEEE CITATION POSITION: Citation tags [X] MUST ALWAYS appear BEFORE sentence-ending periods or punctuation (e.g. 'mencapai akurasi 93% [13].' or 'metode Swin [1], [2].'). NEVER place citation tags after the period (NEVER write 'akurasi 93%. [1]'). In table cells, place citation tags before the closing period of each bullet (e.g. '• Integrates DA-Blocks [2].').\n"
        "2. CITATION MAP (MANDATORY): Whenever your response contains citations [X], you MUST append the hidden CITATION_MAP at the VERY END of your response:\n"
        "<!-- CITATION_MAP: {\"X\": [\"Verbatim sentence proving finding A from Doc X\", \"Verbatim sentence proving finding B from Doc X\"]} -->\n"
        "Copy authentic verbatim sentences directly from the document text provided in the prompt context (provide 1 to 3 key evidence sentences per cited document). Do not paraphrase or invent quotes. This is required for the document viewer to highlight the source evidence accurately.\n"
        "3. UNIVERSAL FACTUALITY (ZERO HALLUCINATION BY OMISSION): If any requested aspect, metric, parameter, limitation, or recommendation is not explicitly discussed by the authors in Document X, report honestly in the prompt's language (e.g. 'This information is not mentioned or provided in the paper.' or 'Tidak disebutkan secara eksplisit dalam naskah') without attaching any citation tag [X] and without inventing claims."
    )

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
