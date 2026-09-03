import os
import re
import json
import asyncio
import inspect
import logging
from typing import List, Optional, Callable, Any
import requests
import pymupdf4llm
from duckduckgo_search import DDGS
from dotenv import load_dotenv

logger = logging.getLogger("uvicorn.error")

from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.llms.gemini import Gemini
from llama_index.llms.groq import Groq
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

from .parsers import (
    parse_document_to_markdown,
    split_markdown_into_academic_sections
)
from helpers import get_doc_file_path
from .search import (
    search_academic_papers,
    plan_academic_search,
    search_academic_papers_planned,
    judge_and_filter_papers_with_llm,
    get_existing_notebook_sources_signatures,
)
from .intent import (
    is_simple_conversational,
    is_technical_discussion,
    is_sources_meta_query,
    classify_user_intent
)
from .prompts import (
    get_general_chat_system_prompt,
    get_source_deletion_prompt,
    get_search_synthesis_prompt,
    get_workspace_analysis_system_prompt,
    get_agentic_system_prompt
)
from .formatters import format_clean_response, extract_structured_citations
from services.rubric_grader_service import evaluate_response_grounding
from .vector_store import embed_model, vector_store, qdrant_client, delete_document_vectors

load_dotenv()

# Setup variables
Settings.embed_model = embed_model

_CACHED_LLM_INSTANCES = None
_CACHED_CONFIG_HASH = None

def _get_env_config_signature():
    """Generates a snapshot of active LLM environment variables to detect config changes."""
    return (
        os.getenv("LLM_PROVIDER", ""),
        os.getenv("NINEROUTER_BASE_URL", ""),
        os.getenv("NINEROUTER_API_KEY", ""),
        os.getenv("NINEROUTER_MODEL", ""),
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GROQ_API_KEY", ""),
        os.getenv("FREELLMAPI_BASE_URL", ""),
        os.getenv("FREELLMAPI_API_KEY", ""),
        os.getenv("FREELLMAPI_MODEL", "")
    )

def clear_llm_cache():
    """Clears cached LLM instances, forcing fresh recreation on next query."""
    global _CACHED_LLM_INSTANCES, _CACHED_CONFIG_HASH
    _CACHED_LLM_INSTANCES = None
    _CACHED_CONFIG_HASH = None

def get_llm_factory(provider_override: Optional[str] = None, force_refresh: bool = False):
    """
    Thread-safe Singleton Factory function that returns cached LLM instances.
    Only recreates client instances if configuration changed or force_refresh=True.
    """
    global _CACHED_LLM_INSTANCES, _CACHED_CONFIG_HASH
    
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_LLM_INSTANCES is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_LLM_INSTANCES

    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "http://localhost:3000/v1")
    ninerouter_key = os.getenv("NINEROUTER_API_KEY")
    ninerouter_model = os.getenv("NINEROUTER_MODEL", "ag/gemini-3.7-flash-high")
    
    n_llm = None
    if ninerouter_key and not ninerouter_key.startswith("your_"):
        try:
            n_llm = OpenAILike(
                api_base=ninerouter_url,
                api_key=ninerouter_key,
                model=ninerouter_model,
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=90.0
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] 9Router initialization failed: {e}")

    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    freellm_url = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
    freellm_key = os.getenv("FREELLMAPI_API_KEY", "dummy")
    freellm_model = os.getenv("FREELLMAPI_MODEL", "gpt-oss-120b")
    
    fl_llm = None
    if freellm_key and not freellm_key.startswith("your_") and freellm_key != "dummy":
        try:
            fl_llm = OpenAILike(
                api_base=freellm_url,
                api_key=freellm_key,
                model=freellm_model or "gpt-4o-mini",
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=90.0
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] FreeLLMAPI not configured: {e}")
    
    gm_llm = None
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gm_llm = Gemini(
                model="models/gemini-2.0-flash", 
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            try:
                gm_llm = Gemini(
                    model="models/gemini-2.5-flash", 
                    api_key=gemini_key,
                    max_tokens=8192
                )
            except Exception as e2:
                logger.warning(f"[RAG Engine] Gemini initialization failed: {e2}")
            
    gq_llm = None
    if groq_key and not groq_key.startswith("your_"):
        try:
            gq_llm = Groq(
                model="llama-3.3-70b-versatile", 
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            try:
                gq_llm = Groq(
                    model="llama-3.1-8b-instant", 
                    api_key=groq_key,
                    max_tokens=8192
                )
            except Exception as e2:
                logger.warning(f"[RAG Engine] Groq initialization failed: {e2}")
            
    _CACHED_LLM_INSTANCES = (n_llm, fl_llm, gm_llm, gq_llm)
    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_LLM_INSTANCES

def create_llm_instances(force_refresh: bool = False):
    """Backward compatibility wrapper."""
    return get_llm_factory(force_refresh=force_refresh)

# Module-level aliases for backward compatibility
ninerouter_llm = None
freellm_llm = None
gemini_llm = None
groq_llm = None

def ingest_document_text(text: str, filename: str, chat_id: str):
    """Ingests text into the vector database under a specific chat_id with section-aware chunking."""
    sections = split_markdown_into_academic_sections(text, filename=filename)
    docs = []
    for sec in sections:
        docs.append(
            Document(
                text=sec.get("text", text),
                metadata={
                    "chat_id": chat_id,
                    "source_type": "file",
                    "filename": filename,
                    "section": sec.get("section", "Overview"),
                    "breadcrumb": sec.get("breadcrumb", "Overview"),
                    "canonical_section": sec.get("canonical_section", "general")
                }
            )
        )
    if not docs:
        docs = [
            Document(
                text=text,
                metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
            )
        ]
    VectorStoreIndex.from_documents(docs, vector_store=vector_store, show_progress=False)
    return True

def ingest_documents_batch(doc_items: List[tuple]):
    """Batch ingests multiple (text, filename, chat_id) into Qdrant with section-aware chunks."""
    if not doc_items:
        return True
    docs = []
    for text, filename, chat_id in doc_items:
        sections = split_markdown_into_academic_sections(text, filename=filename)
        for sec in sections:
            docs.append(
                Document(
                    text=sec.get("text", text),
                    metadata={
                        "chat_id": chat_id,
                        "source_type": "file",
                        "filename": filename,
                        "section": sec.get("section", "Overview"),
                        "breadcrumb": sec.get("breadcrumb", "Overview"),
                        "canonical_section": sec.get("canonical_section", "general")
                    }
                )
            )
    if not docs:
        docs = [
            Document(
                text=text,
                metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
            )
            for text, filename, chat_id in doc_items
        ]
    VectorStoreIndex.from_documents(docs, vector_store=vector_store, show_progress=False)
    return True

def ingest_document(file_path: str, chat_id: str):
    """Parses a multi-format document and ingests it into Qdrant."""
    filename = os.path.basename(file_path)
    md_text = parse_document_to_markdown(file_path)
    return ingest_document_text(md_text, filename, chat_id)

def web_search_and_ingest(query: str, chat_id: str) -> str:
    """Searches scholarly databases (OpenAlex) and the web for research papers and articles."""
    print(f"[Agent] Searching papers/web for: {query}")
    output_snippets = []
    
    academic_results = search_academic_papers(query, limit=5)
    if academic_results:
        for res in academic_results:
            title = res.get('title', 'Untitled')
            year = res.get('year', 'N/A')
            url = res.get('url', '')
            doi = res.get('doi', '')
            snippet = res.get('snippet', '')
            output_snippets.append(
                f"- **Judul:** {title} ({year})\n"
                f"  **DOI / URL:** {url or doi}\n"
                f"  **Ringkasan / Abstrak:** {snippet}"
            )
            
    if len(output_snippets) < 3:
        try:
            results = list(DDGS(timeout=4).text(query, max_results=3))
            for res in results:
                title = res.get('title', 'Untitled')
                url = res.get('href', '')
                snippet = res.get('body', '')
                output_snippets.append(f"- **{title}**\n  URL: {url}\n  Snippet: {snippet}")
        except Exception as e:
            print(f"[Agent] Note: DDGS search skipped or timed out: {e}")
        
    if not output_snippets:
        return f"No results found for query: '{query}'."
                
    return "Temuan paper dan artikel web:\n\n" + "\n\n".join(output_snippets)

def fetch_and_ingest_doi(doi: str, chat_id: str) -> str:
    """Uses OpenAlex API to find an Open Access PDF for a given DOI, downloads it, and ingests it."""
    print(f"[Agent] Fetching DOI: {doi}")
    
    match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', doi, re.I)
    if not match:
        return f"Invalid DOI format: {doi}"
    clean_doi = match.group(0)
    
    api_url = f"https://api.openalex.org/works/doi:{clean_doi}"
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return f"Failed to fetch metadata for DOI {clean_doi}. (Status: {resp.status_code})"
        
        data = resp.json()
        oa_info = data.get("open_access", {})
        if not oa_info.get("is_oa"):
            return f"The paper for DOI {clean_doi} is not Open Access (paywalled). Please upload the PDF manually."
        
        pdf_url = oa_info.get("oa_url")
        if not pdf_url:
            return f"Open Access URL not found for DOI {clean_doi}."
            
        print(f"[Agent] Downloading PDF from {pdf_url}")
        pdf_resp = requests.get(pdf_url, timeout=20)
        if pdf_resp.status_code != 200:
            return f"Failed to download PDF from {pdf_url}."
            
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_resp.content)
            tmp_path = tmp.name
            
        filename = f"{clean_doi.replace('/', '_')}.pdf"
        md_text = pymupdf4llm.to_markdown(tmp_path)
        ingest_document_text(md_text, filename, chat_id)
        
        os.remove(tmp_path)
        return f"Successfully downloaded and saved Open Access paper for DOI: {clean_doi}. The user can now ask questions about it."
        
    except Exception as e:
        return f"An error occurred while fetching DOI {clean_doi}: {str(e)}"

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

    # Dynamic per-request LLM instance creation (Thread-safe)
    n_llm, fl_llm, gm_llm, gq_llm = get_llm_factory()
    candidate_llms = [cand for cand in [n_llm, gm_llm, gq_llm, fl_llm] if cand is not None]

    if not candidate_llms:
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

    for llm in candidate_llms:
        try:
            resp = await llm.acomplete(title_prompt)
            raw_title = resp.text.strip().strip('"\'*`#').strip()
            raw_title = re.sub(r'^(Title|Judul|Topic)\s*:\s*', '', raw_title, flags=re.I).strip()
            if raw_title and len(raw_title) >= 3:
                return raw_title[:45].strip()
        except Exception as e:
            logger.debug(f"[Chat Title Gen Error]: {e}")
            continue

    return fallback_title or "New Research"

async def query_chat(
    chat_id: str, 
    query: str, 
    chat_history: list = None,
    status_callback: Optional[Callable[[str], Any]] = None
):
    """
    Queries the vector store via a ReAct Agent or Direct RAG Synthesis with real-time status callbacks.
    Automatically falls back between active LLMs if quota/rate limits occur.
    """
    from database import SessionLocal, Document as DBDocument
    
    # Process attachments on the latest user query if present
    final_user_msg = chat_history[-1] if chat_history else {}
    attachments = final_user_msg.get("attachments", [])
    
    if attachments:
        from helpers import UPLOAD_DIR
        chat_media_dir = os.path.join(UPLOAD_DIR, "chat_media")
        query += "\n\n[Attachments Provided by User:]"
        for att in attachments:
            fname = att.get('filename', '')
            att_type = att.get('type', '')
            url = att.get('url', '')
            
            # If doc/docx/pdf/txt/csv file attachment, extract text content so LLM can read draft
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
    
    async def report_status(text: str):
        if status_callback:
            try:
                res = status_callback(text)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.debug(f"[Status Callback Error]: {e}")

    await report_status("Analyzing query intent & research parameters...")
    
    db = SessionLocal()
    local_docs = []
    db_docs_by_filename = {}
    try:
        db_docs = db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
        local_docs = [d.filename for d in db_docs]
        db_docs_by_filename = {d.filename: d for d in db_docs}
    finally:
        db.close()
        
    has_local_docs = len(local_docs) > 0
    
    if has_local_docs:
        doc_list_str = "\n".join([f"  [{i+1}] {fname}" for i, fname in enumerate(local_docs)])
        doc_context_info = (
            f"INFORMASI SUMBER REFERENSI SESI INI:\n"
            f"- Sesi chat ini memiliki total {len(local_docs)} dokumen referensi aktif yang diimpor:\n"
            f"{doc_list_str}\n"
            f"- Selalu gunakan fakta ini secara akurat saat menjawab pertanyaan pengguna mengenai jumlah, relevansi judul, atau daftar dokumen yang tersedia."
        )
    else:
        doc_context_info = "INFORMASI SUMBER REFERENSI: Sesi percakapan ini saat ini belum memiliki dokumen referensi yang diunggah/diimpor."
        
    index = None
    query_engine = None
    if has_local_docs:
        try:
            index = VectorStoreIndex.from_vector_store(vector_store)
            filters = MetadataFilters(
                filters=[MetadataFilter(key="chat_id", operator=FilterOperator.EQ, value=chat_id)]
            )
            query_engine = index.as_query_engine(filters=filters)
        except Exception as e:
            print(f"[RAG Engine] Warning: Could not init local query engine: {e}")
    
    def search_local_documents(q: str) -> str:
        """Use this tool ONLY if the user asks questions about content inside their uploaded PDF/documents."""
        if not has_local_docs or not query_engine:
            return "Tidak ada dokumen yang diunggah di chat ini. Silakan gunakan search_web_tool untuk mencari paper atau informasi di internet."
        try:
            result = str(query_engine.query(q))
            if not result or result.strip() == "Empty Response":
                return "Tidak ditemukan informasi spesifik di dokumen yang diunggah."
            return result
        except Exception as e:
            return f"Tidak dapat membaca dokumen lokal: {str(e)}"
        
    local_search_tool = FunctionTool.from_defaults(fn=search_local_documents)
    
    def search_web_tool(q: str) -> str:
        """Use this tool to search the web or find research papers, journal articles, and information online."""
        return web_search_and_ingest(q, chat_id)
        
    web_tool = FunctionTool.from_defaults(fn=search_web_tool)
    
    def search_doi_tool(doi: str) -> str:
        """Use this tool when the user provides a DOI to download and ingest the full paper."""
        return fetch_and_ingest_doi(doi, chat_id)
        
    doi_tool = FunctionTool.from_defaults(fn=search_doi_tool)
    
    formatted_history = []
    if chat_history:
        for msg in chat_history:
            role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
            content = msg.get("content", "")
            if role == MessageRole.ASSISTANT:
                if "<!-- SOURCES_DATA" in content:
                    content = content.split("<!-- SOURCES_DATA")[0].strip()
                if "<!-- CITATION_MAP" in content:
                    content = content.split("<!-- CITATION_MAP")[0].strip()
            formatted_history.append(LlamaChatMessage(role=role, content=content))
            
    # Re-read environment and get instances dynamically
    n_llm, fl_llm, gm_llm, gq_llm = create_llm_instances()
    
    selected_provider = os.getenv("LLM_PROVIDER", "9router").lower()
    
    # Priority list of available LLMs
    candidate_llms = []
    if selected_provider == "9router" and n_llm:
        candidate_llms.append((n_llm, f"9Router ({os.getenv('NINEROUTER_MODEL', 'ag/gemini-3.7-flash-high')})"))
    elif selected_provider == "freellmapi" and fl_llm:
        candidate_llms.append((fl_llm, f"FreeLLMAPI ({os.getenv('FREELLMAPI_MODEL', 'gpt-oss-120b')})"))
    elif selected_provider == "groq" and gq_llm:
        candidate_llms.append((gq_llm, "Groq (Llama 3.3 70B)"))
    elif selected_provider == "gemini" and gm_llm:
        candidate_llms.append((gm_llm, "Google Gemini Flash"))

    # Add all other initialized LLMs as sequential fallbacks
    for llm_inst, name in [
        (n_llm, f"9Router ({os.getenv('NINEROUTER_MODEL', 'ag/gemini-3.7-flash-high')})"),
        (gq_llm, "Groq (Llama 3.3 70B)"),
        (gm_llm, "Google Gemini Flash"),
        (fl_llm, f"FreeLLMAPI ({os.getenv('FREELLMAPI_MODEL', 'gpt-oss-120b')})")
    ]:
        if llm_inst and not any(cand[0] == llm_inst for cand in candidate_llms):
            candidate_llms.append((llm_inst, name))

    if not candidate_llms:
        return "Error: Tidak ada LLM Provider yang terkonfigurasi. Silakan periksa file .env."

    active_llm, primary_name = candidate_llms[0]

    async def execute_agent(target_llm, timeout_sec=60.0):
        intent = await classify_user_intent(query, has_local_docs, len(local_docs), target_llm)
        print(f"[RAG Engine] LLM Semantic Intent: {intent}")

        # 1. Handle General Conversational & Technical Discussion
        if intent == "GENERAL_CHAT":
            from .pipelines.chat_pipeline import handle_general_chat_pipeline
            raw_res = await handle_general_chat_pipeline(query, formatted_history, target_llm, report_status)
            return format_clean_response(raw_res)

        # 2. Handle Explicit Source Removal Intent
        if intent == "REMOVE_SOURCES" and has_local_docs:
            from .pipelines.source_action_pipeline import handle_source_removal_pipeline
            return await handle_source_removal_pipeline(chat_id, query, target_llm, report_status)

        # 3. Direct Academic Literature Search Pipeline
        if intent == "SEARCH_NEW":
            from .pipelines.search_pipeline import handle_academic_search_pipeline
            raw_res = await handle_academic_search_pipeline(chat_id, query, formatted_history, target_llm, report_status)
            if "<!-- SOURCES_DATA:" in raw_res:
                parts = raw_res.split("<!-- SOURCES_DATA:", 1)
                cleaned_text = format_clean_response(parts[0])
                return f"{cleaned_text}\n\n<!-- SOURCES_DATA:{parts[1]}"
            return format_clean_response(raw_res)

        # 4. Direct Full-Context Synthesis for workspace documents
        if intent == "ANALYZE_WORKSPACE" and has_local_docs:
            from .pipelines.workspace_pipeline import handle_workspace_analysis_pipeline
            return await handle_workspace_analysis_pipeline(
                chat_id=chat_id,
                query=query,
                local_docs=local_docs,
                formatted_history=formatted_history,
                target_llm=target_llm,
                report_status=report_status
            )

        # 5. Agentic path for complex multi-tool workflows
        await report_status("Executing agent reasoning & searching academic sources...")
        agent = ReActAgent(
            tools=[local_search_tool, web_tool, doi_tool], 
            llm=target_llm, 
            verbose=False,
            streaming=False,
            max_iterations=6,
            timeout=timeout_sec,
            system_prompt=get_agentic_system_prompt(doc_context_info)
        )
        res = await agent.run(user_msg=query, chat_history=formatted_history if formatted_history else None)
        return format_clean_response(str(res))

    last_err = None
    for cand_idx, (curr_llm, curr_name) in enumerate(candidate_llms):
        try:
            print(f"[RAG Engine] Attempting query with LLM [{cand_idx+1}/{len(candidate_llms)}]: {curr_name}")
            return await execute_agent(curr_llm, timeout_sec=60.0)
        except Exception as e:
            last_err = e
            print(f"[RAG Fallback] {curr_name} failed: {e}")
            if cand_idx + 1 < len(candidate_llms):
                next_name = candidate_llms[cand_idx+1][1]
                print(f"[RAG Fallback] -> Automatically cascading to {next_name}...")
                await report_status(f"Switching AI provider to {next_name}...")
                continue
            else:
                raise last_err
