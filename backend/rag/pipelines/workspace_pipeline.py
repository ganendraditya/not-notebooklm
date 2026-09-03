import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from database import SessionLocal, Document as DBDocument
from rag.parsers import parse_document_to_markdown
from rag.prompts import get_workspace_analysis_system_prompt
from services.rubric_grader_service import evaluate_response_grounding
from utils.file_utils import get_doc_file_path

logger = logging.getLogger("uvicorn.error")

def _load_single_doc_snippet(idx_fname_chat: tuple, db_records: Dict[str, Any], total_doc_count: int) -> tuple:
    """Helper that reads and formats text from a single document record or file on disk."""
    i, fname, chat_id = idx_fname_chat
    fpath = get_doc_file_path(chat_id, fname)
    content_snippet = ""
    db_record = db_records.get(fname)
    is_full_paper = False
    
    # 1. Try parsing full document text properly (PDF/DOCX/TXT/MD)
    if os.path.exists(fpath):
        fsize = os.path.getsize(fpath)
        try:
            parsed_text = parse_document_to_markdown(fpath)
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

    # 1b. If not full paper, attempt on-demand OA PDF fetch
    if (not is_full_paper) and db_record and (db_record.is_oa or db_record.pdf_url or db_record.doi):
        try:
            from services.document_service import check_and_fetch_authentic_pdf_on_demand
            fetched_ok, new_md = asyncio.run(check_and_fetch_authentic_pdf_on_demand(db_record, fpath))
            if fetched_ok:
                if db_record.filename:
                    fpath = get_doc_file_path(chat_id, db_record.filename)
                    fname = db_record.filename

                try:
                    parsed_text = parse_document_to_markdown(fpath)
                    if parsed_text and len(parsed_text.strip()) >= 150 and "NOTBOOKLM" not in parsed_text:
                        is_full_paper = True
                        max_chars = 48000 if total_doc_count > 20 else 80000
                        content_snippet = parsed_text[:max_chars]
                except Exception as parse_err:
                    logger.debug(f"[Workspace Pipeline] Doc Parse Error after fetch for {fname}: {parse_err}")
                    if new_md and len(new_md.strip()) >= 300:
                        is_full_paper = True
                        max_chars = 48000 if total_doc_count > 20 else 80000
                        content_snippet = new_md[:max_chars]
        except Exception as on_demand_err:
            logger.debug(f"[Workspace Pipeline] On-Demand Fetch Error for {fname}: {on_demand_err}")
            
    # 2. If physical file parse failed or short stub: read from DB metadata
    if (not is_full_paper) and db_record:
        meta_parts = []
        d_title = db_record.title or fname.replace(".pdf", "").replace("_", " ")
        d_year = db_record.year or ""
        d_venue = db_record.journal or db_record.venue or ""
        d_doi = db_record.doi or ""
        d_abstract = db_record.abstract or db_record.snippet or ""
        
        meta_parts.append(f"# {d_title} ({d_year})")
        if d_venue: meta_parts.append(f"**Venue/Journal:** {d_venue}")
        if d_doi: meta_parts.append(f"**DOI:** {d_doi}")
        if d_abstract: meta_parts.append(f"## Abstract & Overview\n{d_abstract}")
        
        if content_snippet:
            meta_parts.append(f"## Parsed Text Snippet\n{content_snippet}")
            
        content_snippet = "\n\n".join(meta_parts)
        
    if not content_snippet:
        content_snippet = f"(Dokumen: {fname})"
        
    doc_display_title = (db_record.title if db_record and db_record.title else fname.replace(".pdf", "").replace("_", " ").strip())
    if doc_display_title.isupper() and len(doc_display_title) > 8:
        doc_display_title = doc_display_title.title()

    status_label = "NASKAH LENGKAP TERSEDIA (Full-Text Original PDF Downloaded - Seluruh Bab Lengkap Ada)" if is_full_paper else "RINGKASAN ABSTRAK & METADATA RESMI (Abstract & Metadata Only)"
    has_doi_label = f"DOI Resmi: {db_record.doi}" if (db_record and db_record.doi) else "DOI Resmi: Tidak Ada / Repositori Kampus"

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

async def handle_workspace_analysis_pipeline(
    chat_id: str,
    query: str,
    local_docs: List[str],
    formatted_history: List[LlamaChatMessage],
    target_llm,
    report_status,
    clean_response_fn
) -> str:
    """Direct full-context comparative synthesis for loaded workspace documents."""
    await report_status("Reading full content of all loaded documents...")
    
    db_records = {}
    db = SessionLocal()
    try:
        for db_d in db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all():
            db_records[db_d.filename] = db_d
    finally:
        db.close()

    total_doc_count = len(local_docs)
    loaded_results = await asyncio.gather(
        *(asyncio.to_thread(_load_single_doc_snippet, (i, fname, chat_id), db_records, total_doc_count) for i, fname in enumerate(local_docs))
    )
    
    full_docs_context = "\n\n".join([snippet for _, snippet in loaded_results])
    
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
    chat_msgs = [
        system_msg,
        *(formatted_history if formatted_history else []),
        context_msg,
        LlamaChatMessage(role=MessageRole.USER, content=query)
    ]
    
    await report_status("Synthesizing comparative findings and formatting response...")
    resp = await target_llm.achat(chat_msgs)
    draft_content = clean_response_fn(resp.message.content)

    # Self-Correction Loop with Rubric Grader
    try:
        await report_status("Auditing factual grounding and citations with AI Rubric...")
        rubric_res = await evaluate_response_grounding(
            query=query,
            sources_context=full_docs_context,
            draft_response=draft_content,
            llm=target_llm
        )

        if rubric_res.is_grounded or rubric_res.grounding_score >= 0.8:
            return draft_content

        if rubric_res.revision_instruction:
            await report_status("Refining and correcting factual citations...")
            revision_prompt = (
                f"{system_prompt_text}\n\n"
                "CRITICAL AUDIT FEEDBACK (SELF-CORRECTION REQUIRED):\n"
                f"Your previous draft failed the academic grounding rubric:\n"
                f"- Issues: {json.dumps(rubric_res.hallucinated_claims, ensure_ascii=False)}\n"
                f"- Revision Instruction: {rubric_res.revision_instruction}\n\n"
                "Please rewrite the response to be 100% truthful, strictly aligned with the provided documents, and fix all citation tags."
            )
            revised_chat_msgs = [
                LlamaChatMessage(role=MessageRole.SYSTEM, content=revision_prompt),
                *(formatted_history if formatted_history else []),
                context_msg,
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            revised_resp = await target_llm.achat(revised_chat_msgs)
            return clean_response_fn(revised_resp.message.content)
    except Exception as grade_err:
        logger.warning(f"[Workspace Pipeline] Rubric audit bypassed due to error: {grade_err}")

    return draft_content
