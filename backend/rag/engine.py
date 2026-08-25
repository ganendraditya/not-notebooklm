import os
import re
import json
import asyncio
import inspect
import logging
from typing import List, Optional, Callable, Any
import requests
import pymupdf4llm
from ddgs import DDGS
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
from .vector_store import embed_model, vector_store, qdrant_client, delete_qdrant_vectors

load_dotenv()

# Setup variables
Settings.embed_model = embed_model

def get_llm_factory(provider_override: Optional[str] = None):
    """
    Thread-safe factory function that builds and returns configured LLM instances
    without mutating global shared variables.
    """
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
            except Exception:
                logger.warning(f"[RAG Engine] Gemini initialization failed: {e}")
            
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
            except Exception:
                logger.warning(f"[RAG Engine] Groq initialization failed: {e}")
            
    return n_llm, fl_llm, gm_llm, gq_llm

def create_llm_instances():
    """Backward compatibility wrapper."""
    return get_llm_factory()

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

    def clean_response(text: str) -> str:
        text = re.sub(r'Thought:[\s\S]*?(?=Action:|Answer:|$)', '', text)
        text = re.sub(r'Action:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'Action Input:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'Observation:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'^Answer:\s*', '', text, flags=re.MULTILINE)
        
        # 1. Preserve and separate <!-- CITATION_MAP --> hidden comment at the very end
        citation_map_comment = ""
        if "<!-- CITATION_MAP:" in text:
            parts = text.split("<!-- CITATION_MAP:", 1)
            text = parts[0]
            citation_map_comment = "\n\n<!-- CITATION_MAP:" + parts[1]

        # 2. Strip conversational excuses / hallucinations about UI text limitations
        text = re.sub(r'(?:Antarmuka\s+berbasis\s+teks|The\s+text-based\s+interface)[^\n]*\n+', '', text, flags=re.IGNORECASE)
        
        # 3. Strip pseudo-button text hallucinated in tables: e.g. "🔍 Bukti Metode", "🔍 Bukti Temuan", "[Lihat Bukti]"
        text = re.sub(r'<br\s*/?>\s*🔍\s*Bukti\s*(?:Metode|Temuan|Klaim|Rujukan)[^\n<|]*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'🔍\s*Bukti\s*(?:Metode|Temuan|Klaim|Rujukan)[^\n<|]*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[(?:Lihat\s+Bukti|Bukti\s+Metode|Bukti\s+Temuan)\](?:\([^)]*\))?', '', text, flags=re.IGNORECASE)

        # 4. Strip heading and text for manual quote sections, verification panels, anchor links (<a id=...>), and bulleted quote lists
        # Also parse quotes if LLM wrote manual "Bukti Tekstual & Snippet Verifikasi Sumber" in response body into CITATION_MAP
        text = re.sub(r'<a\s+id=[\'"][^\'"]*[\'"]\s*>\s*(?:</a>)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<a\s+href=[\'"]#[^\'"]*[\'"]\s*>([\s\S]*?)</a>', r'\1', text, flags=re.IGNORECASE)

        # Extract manual snippets into citation_map before stripping if CITATION_MAP wasn't generated
        manual_quotes_match = re.search(
            r'(?:#{1,4}\s*(?:Bukti\s+Tekstual|Teks\s+Sitasi|Verifikasi\s+Teks|Panel\s+Verifikasi|Highlight\s+Bukti|Kutipan\s+Rujukan|Bukti\s+Klaim|Bukti\s+Kutipan|Kutipan\s+Verbatim)[\s\S]*)$',
            text,
            flags=re.IGNORECASE
        )
        if manual_quotes_match:
            manual_section = manual_quotes_match.group(0)
            text = text[:manual_quotes_match.start()].rstrip()
            
            if not citation_map_comment:
                extracted_quotes = {}
                # Match patterns like "Sumber: [7]" or "[7]" followed by quoted snippet
                doc_blocks = re.split(r'(?:Sumber:\s*|Dokumen:\s*)?\[(\d{1,3})\]', manual_section)
                for b_idx in range(1, len(doc_blocks), 2):
                    num = doc_blocks[b_idx]
                    b_content = doc_blocks[b_idx + 1] if b_idx + 1 < len(doc_blocks) else ""
                    # Find text in double quotes inside this block
                    found_quotes = re.findall(r'"([^"]{25,})"', b_content)
                    if not found_quotes:
                        found_quotes = [
                            s.strip() for s in b_content.splitlines() 
                            if len(s.strip()) >= 30 and not re.search(r'^(?:Snippet|Sumber|Dokumen|http|\d+\.)', s.strip(), re.I)
                        ]
                    if found_quotes:
                        extracted_quotes[num] = found_quotes
                if extracted_quotes:
                    citation_map_comment = f"\n\n<!-- CITATION_MAP: {json.dumps(extracted_quotes, ensure_ascii=False)} -->"

        text = text.strip() + citation_map_comment

        # Auto-extract CITATION_MAP fallback if LLM cited [1], [2] but forgot to output CITATION_MAP
        if has_local_docs and not citation_map_comment and re.search(r'\[\d{1,3}\]', text):
            try:
                cited_nums = set(int(m) for m in re.findall(r'\[(\d{1,3})\]', text))
                auto_map = {}
                for num in cited_nums:
                    doc_idx = num - 1
                    if 0 <= doc_idx < len(local_docs):
                        fname = local_docs[doc_idx]
                        fpath = get_doc_file_path(chat_id, fname)
                        doc_text = ""
                        if os.path.exists(fpath):
                            try:
                                doc_text = parse_document_to_markdown(fpath)
                            except Exception:
                                pass
                        if not doc_text and fname in db_docs_by_filename:
                            d_rec = db_docs_by_filename[fname]
                            doc_text = d_rec.abstract or d_rec.snippet or ""
                        
                        if doc_text:
                            # Extract meaningful non-empty sentences from the document text
                            sentences = [
                                s.strip() for s in re.split(r'(?<!\d)(?<!\d\s)[.!?]+(?=\s|$)|[\n\r]+', doc_text)
                                if len(s.strip()) >= 30 and not re.search(r'https?:\/\/|doi\.org|\bvol\b|\bissn\b', s, re.I)
                            ]
                            if sentences:
                                auto_map[str(num)] = sentences[:4]
                if auto_map:
                    text += f"\n\n<!-- CITATION_MAP: {json.dumps(auto_map, ensure_ascii=False)} -->"
            except Exception as auto_map_err:
                logger.debug(f"[Auto CitationMap Error]: {auto_map_err}")

        return text.strip()

    def is_simple_conversational(text: str) -> bool:
        pass

    def is_technical_discussion(text: str) -> bool:
        pass

    def is_sources_meta_query(text: str) -> bool:
        pass

    async def execute_agent(target_llm, timeout_sec=60.0):
        intent = await classify_user_intent(query, has_local_docs, len(local_docs), target_llm)
        print(f"[RAG Engine] LLM Semantic Intent: {intent}")

        # 1. Handle General Conversational & Technical Discussion
        if intent == "GENERAL_CHAT":
            chat_msgs = [
                LlamaChatMessage(role=MessageRole.SYSTEM, content=get_general_chat_system_prompt()),
                *(formatted_history if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Thinking...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 3. Handle Explicit Source Removal Intent (ONLY when explicitly instructed by user)
        if intent == "REMOVE_SOURCES" and has_local_docs:
            await report_status("Processing document deletion request...")
            from database import SessionLocal, Document as DBDocument
            db_s = SessionLocal()
            current_db_docs = []
            try:
                current_db_docs = db_s.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
            finally:
                db_s.close()

            doc_summaries = []
            for d in current_db_docs:
                t = d.title or d.filename.replace(".pdf", "")
                snippet = (d.abstract or d.snippet or "")[:200]
                doc_summaries.append(f"- ID: {d.id} | Filename: {d.filename} | Title: {t} | Abstract: {snippet}")

            eval_prompt = get_source_deletion_prompt(query, doc_summaries)
            try:
                eval_resp = await target_llm.acomplete(eval_prompt)
                clean_json_text = eval_resp.text.strip()
                clean_json_text = re.sub(r'^```(?:json)?\s*', '', clean_json_text, flags=re.I)
                clean_json_text = re.sub(r'\s*```$', '', clean_json_text)
                eval_data = json.loads(clean_json_text)
                to_delete_ids = eval_data.get("remove_doc_ids", [])
                
                deleted_titles = []
                if to_delete_ids:
                    db_del = SessionLocal()
                    try:
                        docs_to_del = db_del.query(DBDocument).filter(
                            DBDocument.id.in_(to_delete_ids),
                            DBDocument.chat_id == chat_id
                        ).all()
                        for dd in docs_to_del:
                            deleted_titles.append(dd.title or dd.filename.replace(".pdf", ""))
                            from helpers import get_doc_file_path
                            fp = get_doc_file_path(chat_id, dd.filename)
                            if os.path.exists(fp):
                                try: os.remove(fp)
                                except Exception: pass
                            db_del.delete(dd)
                        db_del.commit()
                    finally:
                        db_del.close()

                num_deleted = len(deleted_titles)
                resp_text = f"Successfully removed **{num_deleted} requested document(s)** from sources:\n\n"
                for dt in deleted_titles:
                    resp_text += f"- ❌ {dt}\n"
                resp_text += f"\nYour workspace sources have been updated per your request."
                
                action_payload = json.dumps({"action": "bulk_delete", "deleted_doc_ids": to_delete_ids})
                return f"{resp_text}\n\n<!-- SOURCES_ACTION: {action_payload} -->"
            except Exception as eval_err:
                logger.error(f"[Source Clean Error]: {eval_err}")
                return f"Failed to remove requested documents: {str(eval_err)}"

        # 4. Direct Academic Literature Search Pipeline (OpenAlex, Europe PMC, Crossref with Sources Card UI)
        if intent == "SEARCH_NEW":
            await report_status("Planning academic query parameters & search terms...")
            plan = await plan_academic_search(query, formatted_history, target_llm)
            
            await report_status(f"Searching verified academic repositories for {plan.get('target_count', 15)} papers...")
            existing_sigs = get_existing_notebook_sources_signatures(chat_id)
            papers = await asyncio.to_thread(search_academic_papers_planned, plan, existing_sigs)
            
            if not papers:
                return f"Maaf, tidak ditemukan paper ilmiah yang cocok dengan kriteria pencarian untuk topik: '{query}'."

            await report_status("Synthesizing research landscape and structuring sources...")
            
            # Format candidate papers for synthesis
            paper_bullet_list = []
            for p in papers[:25]:
                p_authors = ", ".join(p.get("authors", [])[:3]) if p.get("authors") else "Academic Researchers"
                p_venue = p.get("venue", "Academic Publication")
                paper_bullet_list.append(
                    f"- **{p.get('title')}** ({p.get('year')}) by {p_authors} in *{p_venue}*\n"
                    f"  Abstract: {p.get('snippet', '')[:400]}"
                )
            papers_context = "\n\n".join(paper_bullet_list)

            synthesis_prompt = get_search_synthesis_prompt(query, len(papers), papers_context)

            synth_msgs = [
                LlamaChatMessage(role=MessageRole.SYSTEM, content=synthesis_prompt),
                *(formatted_history if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            
            resp = await target_llm.achat(synth_msgs)
            text_response = clean_response(resp.message.content)
            
            # Append structured SOURCES_DATA payload for frontend ChatMessageItem interactive import card!
            sources_json_str = json.dumps(papers, ensure_ascii=False)
            return f"{text_response}\n\n<!-- SOURCES_DATA: {sources_json_str} -->"

        # 4. Direct Full-Context Synthesis for workspace documents
        if intent == "ANALYZE_WORKSPACE" and has_local_docs:
            await report_status("Reading full content of all loaded documents...")
            uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
            full_docs_context_parts = []
            
            # Fetch all documents from DB for this chat session to use as primary/fallback metadata
            db_docs_by_filename = {}
            try:
                from database import SessionLocal, Document as DBDocument
                _db = SessionLocal()
                try:
                    for db_d in _db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all():
                        db_docs_by_filename[db_d.filename] = db_d
                finally:
                    _db.close()
            except Exception:
                pass

            from helpers import get_doc_file_path

            def load_single_doc_snippet(idx_fname):
                i, fname = idx_fname
                fpath = get_doc_file_path(chat_id, fname)
                content_snippet = ""
                db_record = db_docs_by_filename.get(fname)
                is_full_paper = False
                
                # 1. Try parsing full document text properly (PDF/DOCX/TXT/MD)
                if os.path.exists(fpath):
                    fsize = os.path.getsize(fpath)
                    try:
                        parsed_text = parse_document_to_markdown(fpath)
                        if parsed_text and len(parsed_text.strip()) >= 150:
                            if "NOTBOOKLM SCHOLARLY ARCHIVE" in parsed_text:
                                is_full_paper = False
                            elif fpath.lower().endswith(".pdf") and fsize < 35000:
                                is_full_paper = False
                            else:
                                is_full_paper = True
                            # Dynamic allocation: keep rich content without blowing context limits
                            max_chars = 4000 if len(local_docs) > 20 else 12000
                            content_snippet = parsed_text[:max_chars]
                    except Exception as parse_err:
                        logger.debug(f"[Doc Parse Error for {fname}]: {parse_err}")
                        
                # 2. If physical file parse failed or short stub: read from DB metadata
                if (not content_snippet or len(content_snippet.strip()) < 150) and db_record:
                    is_full_paper = False
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
                    
                    content_snippet = "\n\n".join(meta_parts)
                    
                if not content_snippet:
                    content_snippet = f"(Dokumen: {fname})"
                    
                doc_display_title = (db_record.title if db_record and db_record.title else fname.replace(".pdf", "").replace("_", " ").strip())
                if doc_display_title.isupper() and len(doc_display_title) > 8:
                    doc_display_title = doc_display_title.title()

                status_header = "VERIFIED WORKSPACE SOURCE"

                return (
                    f"--- DOKUMEN [{i+1}] ---\n"
                    f"Nomor Dokumen: [{i+1}]\n"
                    f"Judul Publikasi: {doc_display_title}\n"
                    f"Nama File: {fname}\n"
                    f"Status Naskah: {status_header}\n"
                    f"Teks Dokumen:\n{content_snippet}\n"
                )

            # Load all documents concurrently in thread pool without blocking event loop
            # Maintain deterministic ordering matching DOKUMEN [1], [2], ... [N]
            full_docs_context_parts = await asyncio.gather(
                *(asyncio.to_thread(load_single_doc_snippet, (i, fname)) for i, fname in enumerate(local_docs))
            )
            
            full_docs_context = "\n\n".join(full_docs_context_parts)
            
            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=get_workspace_analysis_system_prompt(len(local_docs))
            )
            context_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=f"BERIKUT ADALAH SELURUH DATA & TEKS DOKUMEN REFERENSI YANG DIIMPOR ({len(local_docs)} DOKUMEN):\n\n{full_docs_context}"
            )
            chat_msgs = [
                system_msg,
                *(formatted_history if formatted_history else []),
                context_msg,
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            
            await report_status("Synthesizing comparative findings and formatting response...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 5. Agentic path for complex workflows
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
        return clean_response(str(res))

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
