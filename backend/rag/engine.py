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

_CACHED_MAIN_LLM = None
_CACHED_FAST_LLM = None
_CACHED_CONFIG_HASH = None

def _get_env_config_signature():
    """Generates a snapshot of active LLM environment variables to detect config changes."""
    return (
        os.getenv("LLM_PROVIDER", ""),
        os.getenv("NINEROUTER_BASE_URL", ""),
        os.getenv("NINEROUTER_API_KEY", ""),
        os.getenv("NINEROUTER_MODEL", ""),
        os.getenv("NINEROUTER_FAST_MODEL", ""),
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GEMINI_MODEL", ""),
        os.getenv("GROQ_API_KEY", "")
    )

def clear_llm_cache():
    """Clears cached LLM instances, forcing fresh recreation on next query."""
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    _CACHED_MAIN_LLM = None
    _CACHED_FAST_LLM = None
    _CACHED_CONFIG_HASH = None

def get_main_llm(force_refresh: bool = False):
    """
    Returns the Primary / Heavy LLM.
    Priority:
    1. If LLM_PROVIDER is 'gemini' or 9Router not configured: Direct Gemini.
    2. If NINEROUTER_API_KEY is configured (not dummy): 9Router OpenAILike.
    3. Direct Gemini Fallback.
    4. Direct Groq Fallback.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_MAIN_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_MAIN_LLM

    provider = os.getenv("LLM_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and not gemini_key.startswith("your_"))
    
    ninerouter_key = os.getenv("NINEROUTER_API_KEY", "")
    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "")
    has_ninerouter = bool(ninerouter_key and not ninerouter_key.startswith("your_") and ninerouter_key != "dummy_key")

    groq_key = os.getenv("GROQ_API_KEY")
    has_groq = bool(groq_key and not groq_key.startswith("your_"))

    _CACHED_MAIN_LLM = None

    # Priority 1: Gemini if explicitly selected or if 9router not configured
    if (provider == "gemini" or not has_ninerouter) and has_gemini:
        try:
            _CACHED_MAIN_LLM = Gemini(
                model=os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash"),
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Gemini init failed: {e}")

    # Priority 2: 9Router
    if _CACHED_MAIN_LLM is None and has_ninerouter:
        try:
            _CACHED_MAIN_LLM = OpenAILike(
                api_base=ninerouter_url or "http://localhost:20128/v1",
                api_key=ninerouter_key,
                model=os.getenv("NINEROUTER_MODEL", "ag/gemini-3.8-flash-high"),
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=120.0
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] 9Router init failed: {e}")

    # Priority 3: Groq fallback
    if _CACHED_MAIN_LLM is None and has_groq:
        try:
            _CACHED_MAIN_LLM = Groq(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Groq init failed: {e}")

    # Final fallback if provider was not gemini but gemini is available
    if _CACHED_MAIN_LLM is None and has_gemini:
        try:
            _CACHED_MAIN_LLM = Gemini(
                model=os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash"),
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Final Gemini fallback failed: {e}")

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_MAIN_LLM

def get_fast_llm(force_refresh: bool = False):
    """
    Returns the Fast / Lite LLM.
    Used for rapid micro-tasks: intent classification, query planning, paper judging, title generation, and rubric checks.
    """
    global _CACHED_MAIN_LLM, _CACHED_FAST_LLM, _CACHED_CONFIG_HASH
    current_sig = _get_env_config_signature()
    if not force_refresh and _CACHED_FAST_LLM is not None and _CACHED_CONFIG_HASH == current_sig:
        return _CACHED_FAST_LLM

    provider = os.getenv("LLM_PROVIDER", "").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and not gemini_key.startswith("your_"))
    
    ninerouter_key = os.getenv("NINEROUTER_API_KEY", "")
    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "")
    has_ninerouter = bool(ninerouter_key and not ninerouter_key.startswith("your_") and ninerouter_key != "dummy_key")

    groq_key = os.getenv("GROQ_API_KEY")
    has_groq = bool(groq_key and not groq_key.startswith("your_"))

    _CACHED_FAST_LLM = None

    if (provider == "gemini" or not has_ninerouter) and has_gemini:
        try:
            _CACHED_FAST_LLM = Gemini(
                model=os.getenv("GEMINI_FAST_MODEL", "models/gemini-3.5-flash-lite"),
                api_key=gemini_key,
                max_tokens=4096
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Fast Gemini init failed: {e}")

    if _CACHED_FAST_LLM is None and has_ninerouter:
        try:
            _CACHED_FAST_LLM = OpenAILike(
                api_base=ninerouter_url or "http://localhost:20128/v1",
                api_key=ninerouter_key,
                model=os.getenv("NINEROUTER_FAST_MODEL", "ag/gemini-3.8-flash-low"),
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=4096,
                timeout=45.0
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Fast 9Router init failed: {e}")

    if _CACHED_FAST_LLM is None and has_groq:
        try:
            _CACHED_FAST_LLM = Groq(
                model=os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant"),
                api_key=groq_key,
                max_tokens=4096
            )
        except Exception as e:
            logger.warning(f"[RAG Engine] Fast Groq init failed: {e}")

    if _CACHED_FAST_LLM is None:
        _CACHED_FAST_LLM = get_main_llm(force_refresh=force_refresh)

    _CACHED_CONFIG_HASH = current_sig
    return _CACHED_FAST_LLM

def get_llm_factory(provider_override: Optional[str] = None, force_refresh: bool = False):
    """Singleton helper returning (main_llm, fast_llm)."""
    return get_main_llm(force_refresh=force_refresh), get_fast_llm(force_refresh=force_refresh)

def create_llm_instances(force_refresh: bool = False):
    """Backward compatibility helper returning (main_llm, fast_llm, None, None)."""
    main_llm, fast_llm = get_llm_factory(force_refresh=force_refresh)
    return main_llm, fast_llm, None, None

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

def ingest_document(file_path: str, chat_id: str, original_filename: Optional[str] = None):
    """Parses a multi-format document and ingests it into Qdrant with clean filename metadata."""
    try:
        if original_filename:
            filename = original_filename
        else:
            raw_base = os.path.basename(file_path)
            prefix = f"{chat_id}_"
            if raw_base.startswith(prefix):
                filename = raw_base[len(prefix):]
            else:
                try:
                    import werkzeug.utils
                    clean_prefix = f"{werkzeug.utils.secure_filename(chat_id)}_"
                    if raw_base.startswith(clean_prefix):
                        filename = raw_base[len(clean_prefix):]
                    else:
                        filename = raw_base
                except Exception:
                    filename = raw_base
        md_text = parse_document_to_markdown(file_path)
        return ingest_document_text(md_text, filename, chat_id)
    except Exception as e:
        logger.error(f"[Ingest Error] Failed to ingest {file_path} for chat {chat_id}: {e}")
        return False

def web_search_and_ingest(query: str, chat_id: str) -> str:
    """Searches scholarly databases (OpenAlex) and the web for research papers and articles."""
    logger.info(f"[Agent] Searching papers/web for: {query}")
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
            logger.debug(f"[Agent] Note: DDGS search skipped or timed out: {e}")
        
    if not output_snippets:
        return f"No results found for query: '{query}'."
                
    return "Temuan paper dan artikel web:\n\n" + "\n\n".join(output_snippets)

def fetch_and_ingest_doi(doi: str, chat_id: str) -> str:
    """Uses OpenAlex API to find an Open Access PDF for a given DOI, downloads it, and ingests it."""
    logger.info(f"[Agent] Fetching DOI: {doi}")
    
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
            
        logger.info(f"[Agent] Downloading PDF from {pdf_url}")
        pdf_resp = requests.get(pdf_url, timeout=20, headers={"User-Agent": "NotbookLM-Research/1.0"})
        if pdf_resp.status_code != 200:
            return f"Failed to download PDF from {pdf_url}."

        # Safety Check: Verify Content-Type & Authentic PDF Magic Bytes
        from utils.pdf_utils import is_authentic_pdf_bytes
        if not is_authentic_pdf_bytes(pdf_resp.content[:2048], min_size=1000):
            return f"The Open Access URL for DOI {clean_doi} did not return a valid binary PDF (possible HTML landing page redirect)."
            
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

def build_rag_tools(chat_id: str, has_local_docs: bool, query_engine: Any) -> List[FunctionTool]:
    """Builds FunctionTools for ReAct agentic execution."""
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
    return [local_search_tool, web_tool, doi_tool]

def get_candidate_llm_chain():
    """Builds prioritized list of candidate LLMs (Main Synthesizer with fallback)."""
    candidate_llms = []
    seen = set()

    def add_candidate(inst, label):
        if inst and id(inst) not in seen:
            candidate_llms.append((inst, label))
            seen.add(id(inst))

    main_instance = get_main_llm()
    fast_instance = get_fast_llm()

    if main_instance:
        label = getattr(main_instance, "model", "default")
        add_candidate(main_instance, f"Primary Synthesizer ({label})")

    # 9Router Fallback Candidate (e.g., ag/gemini-pro-agent)
    ninerouter_key = os.getenv("NINEROUTER_API_KEY", "").strip()
    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "").strip()
    ninerouter_fallback = os.getenv("NINEROUTER_FALLBACK_MODEL", "").strip()
    if ninerouter_key and ninerouter_fallback and not ninerouter_key.startswith("your_") and ninerouter_key != "dummy_key":
        try:
            fb_inst = OpenAILike(
                api_base=ninerouter_url or "http://localhost:20128/v1",
                api_key=ninerouter_key,
                model=ninerouter_fallback,
                is_chat_model=True,
                is_function_calling_model=True,
                max_tokens=8192,
                timeout=120.0
            )
            add_candidate(fb_inst, f"9Router Fallback ({ninerouter_fallback})")
        except Exception as e:
            logger.debug(f"[9Router Fallback init error]: {e}")

    if fast_instance and fast_instance != main_instance:
        label = getattr(fast_instance, "model", "default")
        add_candidate(fast_instance, f"Fast Lite ({label})")

    # Direct Gemini fallback
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-3.7-flash")
            g_inst = Gemini(model=gemini_model, api_key=gemini_key, max_tokens=8192)
            add_candidate(g_inst, f"Direct Gemini Fallback ({gemini_model})")
        except Exception as e:
            logger.debug(f"[LLM Fallback init error]: {e}")

    # Direct Groq fallback
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and not groq_key.startswith("your_"):
        try:
            gq_inst = Groq(model="llama-3.3-70b-versatile", api_key=groq_key)
            add_candidate(gq_inst, "Direct Groq Fallback")
        except Exception as e:
            logger.debug(f"[LLM Fallback init error]: {e}")

    return candidate_llms

async def astream_llm_response(
    target_llm: Any,
    chat_msgs: list,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """
    Executes an LLM chat request with progressive token streaming if on_delta is provided.
    Falls back gracefully to standard achat if astream_chat fails or is unsupported.
    """
    if on_delta and hasattr(target_llm, "astream_chat"):
        try:
            response_stream = await target_llm.astream_chat(chat_msgs)
            full_content = ""
            async for chunk in response_stream:
                token = chunk.delta or ""
                if token:
                    full_content += token
                    res = on_delta(token)
                    if inspect.isawaitable(res):
                        await res
            if full_content:
                return full_content
        except Exception as e:
            logger.warning(f"[RAG Streaming] astream_chat error ({e}), falling back to achat")

    resp = await target_llm.achat(chat_msgs)
    full_content = resp.message.content or ""
    if on_delta and full_content:
        res = on_delta(full_content)
        if inspect.isawaitable(res):
            await res
    return full_content

async def dispatch_intent_pipeline(
    intent: str,
    chat_id: str,
    query: str,
    local_docs: list,
    formatted_history: list,
    target_llm: Any,
    report_status: Callable,
    tools: List[FunctionTool],
    doc_context_info: str,
    timeout_sec: float = 60.0,
    on_delta: Optional[Callable[[str], Any]] = None
) -> str:
    """Dispatches query execution to the specialized modular pipeline based on intent with timeout protection."""
    has_local_docs = len(local_docs) > 0
    
    async def _execute_selected_pipeline() -> str:
        if intent == "GENERAL_CHAT":
            from .pipelines.chat_pipeline import handle_general_chat_pipeline
            raw_res = await handle_general_chat_pipeline(query, formatted_history, target_llm, report_status, on_delta=on_delta)
            return format_clean_response(raw_res)

        if intent == "REMOVE_SOURCES" and has_local_docs:
            from .pipelines.source_action_pipeline import handle_source_removal_pipeline
            return await handle_source_removal_pipeline(chat_id, query, target_llm, report_status)

        if intent == "SEARCH_NEW":
            from .pipelines.search_pipeline import handle_academic_search_pipeline
            raw_res = await handle_academic_search_pipeline(chat_id, query, formatted_history, target_llm, report_status, on_delta=on_delta)
            if "<!-- SOURCES_DATA:" in raw_res:
                parts = raw_res.split("<!-- SOURCES_DATA:", 1)
                cleaned_text = format_clean_response(parts[0])
                return f"{cleaned_text}\n\n<!-- SOURCES_DATA:{parts[1]}"
            return format_clean_response(raw_res)

        if intent == "ANALYZE_WORKSPACE" and has_local_docs:
            from .pipelines.workspace_pipeline import handle_workspace_analysis_pipeline
            return await handle_workspace_analysis_pipeline(
                chat_id=chat_id,
                query=query,
                local_docs=local_docs,
                formatted_history=formatted_history,
                target_llm=target_llm,
                report_status=report_status,
                on_delta=on_delta
            )

        # Agentic fallback path
        await report_status("Executing agent reasoning & searching academic sources...")
        agent = ReActAgent(
            tools=tools, 
            llm=target_llm, 
            verbose=False,
            streaming=False,
            max_iterations=6,
            timeout=timeout_sec,
            system_prompt=get_agentic_system_prompt(doc_context_info)
        )
        res = await agent.run(user_msg=query, chat_history=formatted_history if formatted_history else None)
        return format_clean_response(str(res))

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
    delta_callback: Optional[Callable[[str], Any]] = None
):
    """
    Orchestrates chat queries through intent classification and modular pipelines.
    Automatically handles attachment parsing, history formatting, and multi-LLM cascading fallback.
    Supports real-time token streaming via delta_callback.
    """
    from database import SessionLocal, Document as DBDocument
    
    query = prepare_query_attachments(query, chat_history)
    
    async def report_status(text: str):
        if status_callback:
            try:
                res = status_callback(text)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.debug(f"[Status Callback Error]: {e}")

    async def emit_delta(token: str):
        if delta_callback:
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
        
    query_engine = None
    if has_local_docs:
        try:
            index = VectorStoreIndex.from_vector_store(vector_store)
            filters = MetadataFilters(
                filters=[MetadataFilter(key="chat_id", operator=FilterOperator.EQ, value=chat_id)]
            )
            query_engine = index.as_query_engine(filters=filters)
        except Exception as e:
            logger.warning(f"[RAG Engine] Could not init local query engine: {e}")
    
    tools = build_rag_tools(chat_id, has_local_docs, query_engine)
    formatted_history = format_llama_history(chat_history)
    candidate_llms = get_candidate_llm_chain()

    if not candidate_llms:
        return "Error: Tidak ada LLM Provider yang terkonfigurasi. Silakan periksa file .env."

    # Intent classification is performed ultra-fast via Fast Lite LLM
    fast_instance = get_fast_llm() or (candidate_llms[0][0] if candidate_llms else None)
    intent = await classify_user_intent(query, has_local_docs, len(local_docs), fast_instance)
    logger.info(f"[RAG Engine] Fast LLM Semantic Intent: {intent}")

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
                tools=tools,
                doc_context_info=doc_context_info,
                timeout_sec=60.0,
                on_delta=emit_delta
            )
        except Exception as e:
            last_err = e
            logger.warning(f"[RAG Fallback] {curr_name} failed: {e}")
            if cand_idx + 1 < len(candidate_llms):
                next_name = candidate_llms[cand_idx+1][1]
                logger.info(f"[RAG Fallback] -> Automatically cascading to {next_name}...")
                await report_status(f"Switching AI provider to {next_name}...")
                continue
            else:
                raise last_err
