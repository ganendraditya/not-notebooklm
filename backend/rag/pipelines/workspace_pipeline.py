import os
import asyncio
import logging
from typing import List, Tuple, Dict, Any, Optional, Callable
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from database import SessionLocal, Document as DBDocument
from rag.prompts import get_workspace_analysis_system_prompt
from rag.formatters import format_clean_response
from rag.parsers import parse_document_to_markdown
from utils.file_utils import get_doc_file_path
from rag.llm_factory import astream_llm_response

logger = logging.getLogger("uvicorn.error")

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

    status_label = "NASKAH LENGKAP TERSEDIA (Full-Text Original PDF Downloaded - Seluruh Bab Lengkap Ada)" if is_full_paper else "RINGKASAN ABSTRAK & METADATA RESMI (Abstract & Metadata Only)"
    has_doi_label = f"DOI Resmi: {db_record.get('doi')}" if (db_record and db_record.get("doi")) else "DOI Resmi: Tidak Ada / Repositori Kampus"

    return (
        is_full_paper,
        (
            f"--- DOKUMEN [{i+1}] ---\n"
            f"Nomor Dokumen: [{i+1}]\n"
            f"Judul Publikasi: {doc_display_title}\n"
            f"Nama File: {fname}\n"
            f"Status File Dokumen: {status_label}\n"
            f"{has_doi_label}\n"
            f"Teks Dokumen Asli:\n{content_snippet}\n"
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
    catalog_lines = [f"=== KATALOG DOKUMEN WORKSPACE ({total_docs} DOKUMEN) ==="]

    for i, fname in enumerate(local_docs):
        d = db_records.get(fname, {})
        title = d.get("title") or fname.replace(".pdf", "").replace("_", " ").strip()
        year = f" ({d.get('year')})" if d.get("year") else ""
        venue = f" | Venue: {d.get('journal') or d.get('venue')}" if (d.get("journal") or d.get("venue")) else ""
        doi = f" | DOI: {d.get('doi')}" if d.get("doi") else ""
        snippet = (d.get("abstract") or d.get("snippet") or "").strip()
        if len(snippet) > 350:
            snippet = snippet[:350] + "..."
        catalog_lines.append(f"[{i+1}] {title}{year}{venue}{doi}\nRingkasan: {snippet or '(Tidak ada ringkasan)'}")

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

            for idx, n in enumerate(selected_nodes, start=1):
                fname = n.node.metadata.get("filename", "Dokumen")
                sec = n.node.metadata.get("section") or n.node.metadata.get("breadcrumb") or ""
                sec_lbl = f" - Bagian: {sec}" if sec else ""
                retrieved_blocks.append(
                    f"--- KUTIPAN RELEVAN [{idx}] (Sumber: {fname}{sec_lbl}) ---\n{n.node.get_content()}"
                )
    except Exception as e:
        logger.warning(f"[Workspace Hybrid] Vector retrieval encountered error: {e}")

    if retrieved_blocks:
        return (
            f"{catalog_text}\n\n"
            f"=== KUTIPAN MENDALAM DARI DOKUMEN TERKAIT QUERY ({len(retrieved_blocks)} BAGIAN RELEVAN TERTINGGI) ===\n\n"
            + "\n\n".join(retrieved_blocks)
        )
    else:
        # Fallback if vector index has no chunks yet: use compact snippets
        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async((i, fname, chat_id), db_records, total_docs) for i, fname in enumerate(local_docs))
        )
        return "\n\n".join([snippet for _, snippet in loaded_results])

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
    if total_doc_count <= 4:
        await report_status("Reading full content of loaded workspace documents...")
        loaded_results = await asyncio.gather(
            *(_load_single_doc_snippet_async((i, fname, chat_id), db_records, total_doc_count) for i, fname in enumerate(local_docs))
        )
        full_docs_context = "\n\n".join([snippet for _, snippet in loaded_results])
    else:
        full_docs_context = await _retrieve_hybrid_workspace_context(
            chat_id=chat_id,
            query=query,
            local_docs=local_docs,
            db_records=db_records,
            report_status=report_status
        )
    
    system_prompt_text = (
        f"{get_workspace_analysis_system_prompt(total_doc_count)}\n\n"
        "CRITICAL INSTRUCTIONS FOR SYNTHESIS & ANALYSIS:\n"
        "- When the user asks to summarize, analyze, compare, or generate chapters/sections (like Bab 3, Metodologi, Hasil, dll.), write a rich, detailed, and comprehensive academic text synthesizing the data.\n"
        "- DO NOT refuse with excuses about copyright or partial text. Leverage the available document text fully."
    )

    system_msg = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=system_prompt_text
    )
    context_msg = LlamaChatMessage(
        role=MessageRole.SYSTEM,
        content=f"BERIKUT ADALAH SELURUH DATA & TEKS DOKUMEN REFERENSI YANG DIIMPOR ({total_doc_count} DOKUMEN):\n\n{full_docs_context}"
    )
    augmented_user_query = (
        f"{query}\n\n"
        "[PETUNJUK FORMAT PENTING: Wajib cantumkan tag sitasi bracket [1], [2], dst. pada SETIAP baris temuan/metrik dan DI DALAM SETIAP SEL TABEL (jangan hanya di judul/header kolom). "
        "Setiap temuan, metode, angka metrik harus memiliki tag [X] agar tombol bukti interaktif muncul. "
        "Di baris paling akhir respon, sertakan blok <!-- CITATION_MAP: {\"1\": [\"...\"], \"2\": [\"...\"]} --> dengan kutipan kalimat persis dari naskah sumber.]"
    )

    chat_msgs = [
        system_msg,
        *(formatted_history if formatted_history else []),
        context_msg,
        LlamaChatMessage(role=MessageRole.USER, content=augmented_user_query)
    ]
    
    await report_status("Synthesizing comparative findings and formatting response...")
    raw_content = await astream_llm_response(target_llm, chat_msgs, on_delta=on_delta)
    draft_content = format_clean_response(raw_content)

    return draft_content
