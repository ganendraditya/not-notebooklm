import os
import re
import json
import asyncio
import inspect
import logging
from typing import List, Optional, Callable, Any
from dotenv import load_dotenv

logger = logging.getLogger("uvicorn.error")

from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

from .parsers import parse_document_to_markdown
from .intent import (
    is_simple_conversational,
    classify_user_intent
)
from .formatters import format_clean_response
from .vector_store import (
    embed_model,
    vector_store,
    ingest_document_text,
    ingest_documents_batch,
    ingest_document,
)
from .llm_factory import (
    clear_llm_cache,
    get_main_llm,
    get_fast_llm,
    get_llm_factory,
    create_llm_instances,
    get_candidate_llm_chain,
    astream_llm_response,
)
from .pipelines import (
    chat_pipeline,
    source_action_pipeline,
    search_pipeline,
    workspace_pipeline,
)

load_dotenv()

async def generate_chat_title(first_user_message: str) -> str:
    """
    Generates a concise, professional, and descriptive conversation title (max 4-6 words)
    like standard ChatGPT/Claude from the user's first prompt, eliminating colloquial filler.
    """
    clean_prompt = first_user_message.strip()
    if not clean_prompt:
        return "New Research"
        
    fallback_title = re.sub(
        r'\b(halo|hai|hey|bro|sis|gan|min|tolong|coba|dong|ya|nih|deh|gw|gua|gue|aku|saya|kamu|lu|lo|bisa|cariin|carikan|cari|search|find|tentang|about|paper|jurnal|artikel|sumber|sources|buah|biji|referensi|makalah|lagi|bos|buat|ke|max|maksimal|tahun|terakhir|ke\s*belakang|jangan|lebih|dari|itu|open access|gratis|free)\b',
        ' ',
        clean_prompt,
        flags=re.I
    )
    fallback_title = ' '.join(fallback_title.split()).strip()
    if len(fallback_title) < 4:
        fallback_title = clean_prompt[:35]
    fallback_title = fallback_title.title()[:45].strip()

    if is_simple_conversational(first_user_message):
        return fallback_title or "New Research"

    # Use Fast LLM for rapid, lightweight title generation
    fast_llm_instance = get_fast_llm()
    if not fast_llm_instance:
        return fallback_title or "New Research"

    title_prompt = (
        "You are an AI conversation title generator.\n"
        "Task: Create a concise, professional title (2 to 5 words max) summarizing the topic of the user's message.\n"
        "Guidelines:\n"
        "- Match the EXACT language/dialect of the user's prompt (if English -> English; if Indonesian -> Indonesian; if Portuguese/Spanish/other -> that exact language).\n"
        "- If the prompt is just a greeting or short test word like 'tes', 'test', 'ping', 'halo', 'hi', simply return 'Test Conversation' or 'New Chat' in the corresponding language.\n"
        "- Do not translate or assume Indonesian if the prompt is English or ambiguous.\n"
        "- Output ONLY the title text. No quotes, no markdown, no punctuation, no 'Title:' prefix.\n\n"
        f"User Message: {clean_prompt}\n"
        "Title:"
    )

    try:
        resp = await fast_llm_instance.acomplete(title_prompt)
        raw_title = resp.text.strip().strip('"\'*`#').strip()
        raw_title = re.sub(r'^(Title|Judul|Topic)\s*:\s*', '', raw_title, flags=re.I).strip()
        if raw_title and len(raw_title) >= 3:
            return raw_title[:45].strip()
    except Exception as e:
        logger.debug(f"[Chat Title Gen Error]: {e}")

    return fallback_title or "New Research"

def prepare_query_attachments(query: str, chat_history: Optional[list] = None) -> str:
    """Processes any attachments present in the latest user message and appends extracted text."""
    if not chat_history:
        return query
        
    final_user_msg = chat_history[-1] if chat_history else {}
    attachments = final_user_msg.get("attachments", [])
    if not attachments:
        return query
        
    from helpers import UPLOAD_DIR
    chat_media_dir = os.path.join(UPLOAD_DIR, "chat_media")
    query += "\n\n[Attachments Provided by User:]"
    for att in attachments:
        fname = att.get('filename', '')
        att_type = att.get('type', '')
        url = att.get('url', '')
        
        extracted_text = ""
        if url:
            base_media_name = os.path.basename(url)
            media_path = os.path.join(chat_media_dir, base_media_name)
            if os.path.exists(media_path):
                try:
                    from rag.parsers import parse_document_to_markdown
                    extracted_text = parse_document_to_markdown(media_path)
                except Exception as pe:
                    logger.debug(f"[Parse Attachment Warning]: {pe}")
        
        if att_type == 'image':
            query += f"\n- Image attached: {fname}"
        else:
            query += f"\n- Document attached: {fname}"
            if extracted_text:
                truncated_content = extracted_text[:12000]
                if len(extracted_text) > 12000:
                    truncated_content += "\n...[Content truncated for length]..."
                query += f"\n\n--- Content of Attached File ({fname}) ---\n{truncated_content}\n--- End of Attached File Content ---\n"
                
    return query

def format_llama_history(chat_history: Optional[list] = None) -> List[LlamaChatMessage]:
    """Formats raw chat message dictionaries into LlamaChatMessage objects with cleaned markers."""
    formatted_history = []
    if not chat_history:
        return formatted_history
        
    for msg in chat_history:
        role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
        content = msg.get("content", "")
        if role == MessageRole.ASSISTANT:
            if "<!-- SOURCES_DATA" in content:
                content = content.split("<!-- SOURCES_DATA")[0].strip()
            if "<!-- CITATION_MAP" in content:
                content = content.split("<!-- CITATION_MAP")[0].strip()
        formatted_history.append(LlamaChatMessage(role=role, content=content))
    return formatted_history

async def dispatch_intent_pipeline(
    intent: str,
    chat_id: str,
    query: str,
    local_docs: list,
    formatted_history: list,
    target_llm: Any,
    report_status: Callable,
    tools: Optional[List[Any]] = None,
    doc_context_info: str = "",
    timeout_sec: float = 60.0,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """Dispatches query execution to the specialized modular pipeline based on intent with timeout protection."""
    has_local_docs = len(local_docs) > 0
    
    async def _execute_selected_pipeline() -> str:
        if intent == "GENERAL_CHAT":
            raw_res = await chat_pipeline.handle_general_chat_pipeline(query, formatted_history, target_llm, report_status, on_delta=on_delta)
            return format_clean_response(raw_res)

        if intent == "REMOVE_SOURCES":
            if not has_local_docs:
                return "Tidak ada dokumen yang diimpor di sesi ini untuk dihapus."
            return await source_action_pipeline.handle_source_removal_pipeline(chat_id, query, target_llm, report_status)

        if intent == "SEARCH_NEW":
            raw_res = await search_pipeline.handle_academic_search_pipeline(chat_id, query, formatted_history, target_llm, report_status, on_delta=on_delta)
            if "<!-- SOURCES_DATA:" in raw_res:
                parts = raw_res.split("<!-- SOURCES_DATA:", 1)
                cleaned_text = format_clean_response(parts[0])
                return f"{cleaned_text}\n\n<!-- SOURCES_DATA:{parts[1]}"
            return format_clean_response(raw_res)

        if intent == "ANALYZE_WORKSPACE":
            if not has_local_docs:
                if "[Attachments Provided by User:]" in query:
                    # User attached files directly in the chat message: route to general chat so the LLM reads and discusses them!
                    raw_res = await chat_pipeline.handle_general_chat_pipeline(query, formatted_history, target_llm, report_status, on_delta=on_delta)
                    return format_clean_response(raw_res)
                return "Sesi percakapan ini belum memiliki dokumen referensi. Silakan unggah dokumen PDF atau gunakan fitur pencarian paper untuk menambahkan referensi terlebih dahulu."
            return await workspace_pipeline.handle_workspace_analysis_pipeline(
                chat_id=chat_id,
                query=query,
                local_docs=local_docs,
                formatted_history=formatted_history,
                target_llm=target_llm,
                report_status=report_status,
                on_delta=on_delta
            )

        # Clean fallback path to general chat
        raw_res = await chat_pipeline.handle_general_chat_pipeline(query, formatted_history, target_llm, report_status, on_delta=on_delta)
        return format_clean_response(raw_res)

    if timeout_sec and timeout_sec > 0:
        try:
            return await asyncio.wait_for(_execute_selected_pipeline(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.error(f"[RAG Timeout] Pipeline {intent} exceeded {timeout_sec}s timeout.")
            raise TimeoutError(f"Proses analisis ({intent}) melebihi batas waktu {int(timeout_sec)} detik. Silakan coba lagi.")
    else:
        return await _execute_selected_pipeline()

async def query_chat(
    chat_id: str, 
    query: str, 
    chat_history: list = None,
    status_callback: Optional[Callable[[str], Any]] = None,
    delta_callback: Optional[Callable[[str], Any]] = None,
    reset_callback: Optional[Callable[[], Any]] = None
):
    """
    Orchestrates chat queries through intent classification and modular pipelines.
    Automatically handles attachment parsing, history formatting, and multi-LLM cascading fallback.
    Supports real-time token streaming via delta_callback and clean buffer reset via reset_callback.
    """
    from database import SessionLocal, Document as DBDocument
    
    raw_user_query = (query or "").strip()
    query = prepare_query_attachments(query, chat_history)
    
    async def report_status(text: str):
        if status_callback:
            try:
                res = status_callback(text)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.debug(f"[Status Callback Error]: {e}")

    has_emitted_tokens = False

    async def emit_delta(token: str):
        nonlocal has_emitted_tokens
        if delta_callback and token:
            has_emitted_tokens = True
            try:
                res = delta_callback(token)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.debug(f"[Delta Callback Error]: {e}")

    await report_status("Analyzing query intent & research parameters...")
    
    db = SessionLocal()
    local_docs = []
    try:
        db_docs = db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
        local_docs = [d.filename for d in db_docs]
    finally:
        db.close()
        
    has_local_docs = len(local_docs) > 0
    formatted_history = format_llama_history(chat_history)
    candidate_llms = get_candidate_llm_chain()

    if not candidate_llms:
        return "Error: Tidak ada LLM Provider yang terkonfigurasi. Silakan periksa file .env."

    # Intent classification is performed ultra-fast via Fast Lite LLM using clean user prompt
    fast_instance = get_fast_llm() or (candidate_llms[0][0] if candidate_llms else None)
    has_chat_attachments = "[Attachments Provided by User:]" in query
    intent_query = raw_user_query if raw_user_query else ("Silakan baca dan diskusikan dokumen terlampir." if has_chat_attachments else query)
    intent = await classify_user_intent(intent_query, has_local_docs, len(local_docs), fast_instance)
    logger.info(f"[RAG Engine] Fast LLM Semantic Intent: {intent}")

    # Dynamic timeout: complex comparative workspace queries need up to 150s
    pipeline_timeout = 150.0 if intent == "ANALYZE_WORKSPACE" else 75.0

    last_err = None
    for cand_idx, (curr_llm, curr_name) in enumerate(candidate_llms):
        try:
            logger.info(f"[RAG Engine] Executing pipeline with Primary LLM [{cand_idx+1}/{len(candidate_llms)}]: {curr_name}")
            
            return await dispatch_intent_pipeline(
                intent=intent,
                chat_id=chat_id,
                query=query,
                local_docs=local_docs,
                formatted_history=formatted_history,
                target_llm=curr_llm,
                report_status=report_status,
                timeout_sec=pipeline_timeout,
                on_delta=emit_delta
            )
        except Exception as e:
            last_err = e
            logger.warning(f"[RAG Fallback] {curr_name} failed: {e}")
            if cand_idx + 1 < len(candidate_llms):
                next_name = candidate_llms[cand_idx+1][1]
                logger.info(f"[RAG Fallback] -> Automatically cascading to {next_name}...")
                
                # If this model had already streamed partial tokens, instruct client to reset the buffer
                if has_emitted_tokens and reset_callback:
                    try:
                        res = reset_callback()
                        if inspect.isawaitable(res):
                            await res
                    except Exception as reset_err:
                        logger.debug(f"[Reset Callback Error]: {reset_err}")
                has_emitted_tokens = False

                await report_status(f"Switching AI provider to {next_name}...")
                continue
            else:
                raise last_err
