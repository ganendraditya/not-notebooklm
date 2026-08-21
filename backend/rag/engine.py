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
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
try:
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
except Exception:
    HuggingFaceEmbedding = None
from llama_index.llms.groq import Groq
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole

from .parsers import parse_document_to_markdown
from .search import (
    search_academic_papers,
    plan_academic_search,
    search_academic_papers_planned,
    get_existing_notebook_sources_signatures,
)

load_dotenv()

# Setup Qdrant Client (Supports Remote Server / Docker or Local Disk fallback)
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if QDRANT_URL:
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        logger.info(f"[Qdrant] Connected to remote server at {QDRANT_URL}")
    except Exception as e:
        logger.warning(f"[Qdrant] Failed connecting to remote URL {QDRANT_URL}: {e}. Falling back to disk.")
        QDRANT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_data"))
        os.makedirs(QDRANT_PATH, exist_ok=True)
        qdrant_client = QdrantClient(path=QDRANT_PATH, force_disable_check_same_thread=True)
else:
    QDRANT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_data"))
    os.makedirs(QDRANT_PATH, exist_ok=True)
    try:
        qdrant_client = QdrantClient(path=QDRANT_PATH, force_disable_check_same_thread=True)
    except Exception:
        try:
            qdrant_client = QdrantClient(path=QDRANT_PATH)
        except Exception:
            qdrant_client = QdrantClient(location=":memory:")

def init_embedding_and_vector_store():
    """Initializes high-performance embeddings (Local BGE or Gemini) and associates with Qdrant collection."""
    env_provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")

    if env_provider == "gemini" and gemini_key and not gemini_key.startswith("your_"):
        try:
            embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=gemini_key)
            coll_name = "not_notebooklm_gemini"
            vstore = QdrantVectorStore(client=qdrant_client, collection_name=coll_name, path=None, url=None, api_key=None)
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] Gemini Embedding initialization failed ({e}), falling back to local BGE embeddings.")

    # Default Local Offline Embeddings (Zero API Quota limit, zero rate limit)
    if HuggingFaceEmbedding is not None:
        try:
            embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
            coll_name = "not_notebooklm_bge"
            vstore = QdrantVectorStore(client=qdrant_client, collection_name=coll_name, path=None, url=None, api_key=None)
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] HuggingFace Embedding loading failed: {e}")

    # Ultimate fallback to Gemini
    embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=gemini_key)
    vstore = QdrantVectorStore(client=qdrant_client, collection_name="not_notebooklm", path=None, url=None, api_key=None)
    return embed_model, vstore

Settings.embed_model, vector_store = init_embedding_and_vector_store()

def create_llm_instances():
    """Initializes LLM instances for 9Router, FreeLLMAPI, Gemini, and Groq."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(dotenv_path=env_path, override=True)
    load_dotenv(override=True)
    
    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
    ninerouter_key = os.getenv("NINEROUTER_API_KEY")
    ninerouter_model = os.getenv("NINEROUTER_MODEL", "ag/gemini-3.7-flash-high")
    
    ninerouter_llm = None
    if ninerouter_key and not ninerouter_key.startswith("your_"):
        try:
            ninerouter_llm = OpenAILike(
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
    
    freellm_llm = None
    if freellm_key and not freellm_key.startswith("your_") and freellm_key != "dummy":
        try:
            freellm_llm = OpenAILike(
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
    
    gemini_llm = None
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gemini_llm = Gemini(
                model="models/gemini-2.0-flash", 
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            try:
                gemini_llm = Gemini(
                    model="models/gemini-2.5-flash", 
                    api_key=gemini_key,
                    max_tokens=8192
                )
            except Exception:
                logger.warning(f"[RAG Engine] Gemini initialization failed: {e}")
            
    groq_llm = None
    if groq_key and not groq_key.startswith("your_"):
        try:
            groq_llm = Groq(
                model="llama-3.3-70b-versatile", 
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            try:
                groq_llm = Groq(
                    model="llama-3.1-8b-instant", 
                    api_key=groq_key,
                    max_tokens=8192
                )
            except Exception:
                logger.warning(f"[RAG Engine] Groq initialization failed: {e}")
            
    return ninerouter_llm, freellm_llm, gemini_llm, groq_llm

ninerouter_llm, freellm_llm, gemini_llm, groq_llm = create_llm_instances()
Settings.llm = ninerouter_llm or freellm_llm or gemini_llm or groq_llm

def ingest_document_text(text: str, filename: str, chat_id: str):
    """Ingests raw text into the vector database under a specific chat_id."""
    doc = Document(
        text=text,
        metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
    )
    VectorStoreIndex.from_documents([doc], vector_store=vector_store, show_progress=False)
    return True

def ingest_documents_batch(doc_items: List[tuple]):
    """Batch ingests multiple (text, filename, chat_id) into Qdrant in a single embedding call."""
    if not doc_items:
        return True
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

    candidate_llms = []
    if ninerouter_llm: candidate_llms.append(ninerouter_llm)
    if gemini_llm: candidate_llms.append(gemini_llm)
    if groq_llm: candidate_llms.append(groq_llm)
    if freellm_llm: candidate_llms.append(freellm_llm)

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
        text = re.sub(r'\n+#{1,4}\s*(?:Teks\s+Sitasi|Verifikasi\s+Teks|Panel\s+Verifikasi|Highlight\s+Bukti|Kutipan\s+Rujukan|Bukti\s+Klaim|Bukti\s+Kutipan|Kutipan\s+Verbatim|Pemetaan\s+Langsung|Bukti\s+Validasi)[\s\S]*$', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\n+(?:Teks\s+Sitasi\s+Rujukan|Verifikasi\s+Teks\s+Sitasi|Panel\s+Verifikasi\s+Bukti|Highlight\s+Bukti\s+Klaim|Bukti\s+Kutipan\s+Verbatim|Bukti\s+kutipan\s+langsung|Berikut\s+adalah\s+pemetaan\s+langsung|Berikut\s+adalah\s+bukti\s+validasi)[\s\S]*$', '', text, flags=re.IGNORECASE)
        
        # 5. Remove any lingering HTML anchors, raw link anchors, or mark tags that LLM attempts to output in chat body
        text = re.sub(r'<a\s+id=[\'"][^\'"]*[\'"]\s*>\s*(?:</a>)?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<a\s+href=[\'"]#[^\'"]*[\'"]\s*>([\s\S]*?)</a>', r'\1', text, flags=re.IGNORECASE)
        
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
        # Strip punctuation and collapse spaces
        t = re.sub(r'[^\w\s]', '', text.lower()).strip()
        tokens = t.split()
        if len(tokens) == 0 or len(tokens) > 6:
            return False
            
        greetings_exact = {
            "halo", "hai", "hi", "hello", "hey", "hei", "pagi", "siang", "sore", "malam",
            "good morning", "good afternoon", "good evening", "good night",
            "terima kasih", "makasih", "thanks", "thank you", "siapa kamu", "who are you",
            "bisa apa", "kamu siapa", "what can you do", "tes", "test", "ping", "bisa bantu apa",
            "woi", "oy", "p", "bro", "bos", "min", "apa kabar", "how are you", "how are you doing",
            "hows it going", "how is it going", "sup", "whats up",
            "gimana kabarnya", "kabar apa", "sehat", "apa kabarmu", "apa kabarmu bro",
            "piye kabare", "piye kabare mas", "piye kabare mbak", "sugeng enjang", "sugeng siang", "sugeng sonten", "sugeng dalu", "matur nuwun",
            "hola", "buenos dias", "buenas tardes", "buenas noches", "como estas", "que tal", "hola como estas", "gracias",
            "안녕하세요", "안녕", "어떻게 지내세요", "어떻게 지내", "반갑습니다", "고마워", "감사합니다", "테스트",
            "konnichiwa", "arigato", "ohayo", "ohayou", "ohayou gozaimasu", "kombanwa"
        }
        
        # Strip Spanish accents/marks for normalization
        t_clean = t.replace("¿", "").replace("?", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
        
        if t in greetings_exact or t_clean in greetings_exact:
            return True
            
        # Check prefix/suffix combinations
        clean_prefix = re.sub(r'^(halo|hai|hi|hello|hey|hei|woi|oy|p|bro|bos|min|assalamualaikum|mas|mbak|pak|bu|hola)\s+', '', t_clean).strip()
        clean_suffix = re.sub(r'\s+(mas|mbak|pak|bu|bro|bos|min|ya|dong|gan|rek)$', '', t_clean).strip()
        clean_both = re.sub(r'\s+(mas|mbak|pak|bu|bro|bos|min|ya|dong|gan|rek)$', '', clean_prefix).strip()
        
        return clean_prefix in greetings_exact or clean_suffix in greetings_exact or clean_both in greetings_exact

    def is_technical_discussion(text: str) -> bool:
        """Identifies queries asking about NotbookLM system internals, RAG, databases, embeddings, or conceptual discussion."""
        t = text.lower().strip()
        tech_triggers = [
            "pake rag", "pakai rag", "sistem rag", "cara kerja", "arsitektur",
            "database apa", "vector database", "database vektor", "gimana sistemnya",
            "gimana cara kerja", "masuk ke database", "disimpan di mana", "data disimpan",
            "bisa fetch apa", "bisa akses apa", "paywall", "open access kah", "cara lo dapet",
            "dapetin papernya gimana", "punya database sendiri", "apakah ada database",
            "gimana lu", "gimana lo", "bagaimana kamu", "apakah kamu", "kenapa kamu"
        ]
        return any(tr in t for tr in tech_triggers)

    def is_sources_meta_query(text: str) -> bool:
        t = text.lower().strip()
        # Do not capture if user explicitly asks to delete / remove
        if any(dt in t for dt in ["hapus", "hapusin", "remove", "delete", "bersihkan", "buang", "drop"]):
            return False
        meta_phrases = [
            "berapa dokumen", "berapa file", "berapa banyak dokumen", "berapa jumlah dokumen",
            "berapa total dokumen", "jumlah dokumen", "daftar dokumen", "ada berapa dokumen",
            "ada dokumen apa", "dokumen apa saja", "list dokumen", "sebutkan dokumen",
            "dokumen yang diupload", "dokumen yang diimpor", "berapa source", "jumlah source",
            "berapa referensi", "daftar referensi", "ada referensi apa", "berapa doang", "berapa yang",
            "yang mana saja", "relevan berapa", "yang cocok berapa"
        ]
        return any(p in t for p in meta_phrases)

    async def execute_agent(target_llm, timeout_sec=60.0):
        # 1. First, let the LLM semantically classify what the user wants
        async def classify_user_intent(user_query: str, has_docs: bool) -> str:
            system_intent_prompt = f"""You are the Master Intent Classifier for NotbookLM research workspace.
Current Workspace Status: {'Contains ' + str(len(local_docs)) + ' imported documents' if has_docs else 'No documents imported yet'}.

Analyze the user's latest prompt carefully and determine their true intention. Choose strictly ONE of the following 4 categories:

1. 'REMOVE_SOURCES':
   - ONLY when the user is giving an EXPLICIT, DIRECT COMMAND to delete or remove documents from their sources (e.g. 'tolong hapus 12 paper tadi', 'hapusin paper yang ga relevan', 'delete paper A, B, C', 'buang dokumen yang tidak cocok').
   - DO NOT choose this if the user is merely asking a question or seeking evaluation (e.g. 'apakah ada yang ga relevan?', 'ada berapa paper yang tidak cocok?').

2. 'SEARCH_NEW':
   - When the user is asking to find, discover, search, fetch, or recommend NEW academic papers or literature from the internet (e.g. 'cariin 50 paper tentang rainfall', 'find papers about machine learning', 'tambah 20 paper lagi', 'rekomendasiin paper terkini').
   - DO NOT choose this if the user is asking about the documents already inside their workspace (e.g. 'ada berapa paper di sources?', 'apakah di dokumen saya ada paper Indo?').

3. 'ANALYZE_WORKSPACE':
   - When the user is asking questions about, crosschecking, synthesizing, summarizing, comparing, or listing the documents ALREADY inside their workspace (e.g. 'ada berapa paper indo di sources?', 'analisis perbandingan metode dari dokumen ini', 'buat ringkasan bab 1', 'apakah ada dokumen yang tidak relevan di sources saya?').

4. 'GENERAL_CHAT':
   - For greetings, casual questions, thanking, testing, system explanations, or general knowledge questions.

User Prompt: "{user_query}"

Respond with ONLY the exact category name (REMOVE_SOURCES, SEARCH_NEW, ANALYZE_WORKSPACE, or GENERAL_CHAT) without quotes or explanations."""
            try:
                resp = await target_llm.acomplete(system_intent_prompt)
                raw_intent = resp.text.strip().upper().replace("'", "").replace('"', "").replace("`", "")
                for valid in ["REMOVE_SOURCES", "SEARCH_NEW", "ANALYZE_WORKSPACE", "GENERAL_CHAT"]:
                    if valid in raw_intent:
                        return valid
            except Exception as e:
                logger.debug(f"[Intent Classifier Error]: {e}")

            if has_docs:
                return "ANALYZE_WORKSPACE"
            return "GENERAL_CHAT"

        intent = await classify_user_intent(query, has_local_docs)
        print(f"[RAG Engine] LLM Semantic Intent: {intent}")

        # 1. Handle General Conversational & Technical Discussion
        if intent == "GENERAL_CHAT":
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, an intelligent, transparent, and friendly AI research assistant (like Google NotebookLM).\n"
                        "LANGUAGE RULE (CRITICAL):\n"
                        "- Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese -> Basa Jawa, Spanish -> Spanish).\n"
                        "- If asked about capabilities or system workings, explain clearly that you are connected to verified academic APIs (OpenAlex, Europe PMC, Crossref) and Qdrant RAG vector database."
                    )
                ),
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

            eval_prompt = (
                "You are an AI Document Management Assistant.\n"
                f"User Deletion Request: \"{query}\"\n\n"
                "List of loaded documents in this workspace:\n" + "\n".join(doc_summaries) + "\n\n"
                "Task: Identify STRICTLY the specific document IDs that match the user's explicit deletion instruction.\n"
                "If the user named specific papers (e.g. 'hapus paper a, b, c' or 'hapus yang tidak relevan'), identify ONLY those matching IDs.\n"
                "Return ONLY a valid JSON object matching:\n"
                "{\n"
                "  \"remove_doc_ids\": [1, 2, 3],\n"
                "  \"reason\": \"Summary reason for removal\"\n"
                "}"
            )
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

            synthesis_prompt = (
                "You are NotbookLM, an intelligent, proactive, and structured research curator & academic synthesis assistant (Google NotebookLM style).\n\n"
                "LANGUAGE RULE (CRITICAL):\n"
                "- Match the exact language of the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese/Basa Jawa -> Basa Jawa, Spanish -> Spanish, etc.).\n\n"
                f"User Request: \"{query}\"\n\n"
                f"Verified Academic Search Results: Successfully retrieved and filtered {len(papers)} verified and reputable Open Access papers.\n\n"
                f"Core Paper Samples:\n{papers_context}\n\n"
                "RESPONSE STRUCTURE TO FOLLOW:\n"
                "1. Friendly Opening & Realistic Context:\n"
                "   - If the user requested a massive quantity (e.g. 50-100 papers), politely explain that presenting dozens of raw papers all at once in text is counterproductive for in-depth analysis. State that the system has curated the top {len(papers)} most relevant, high-impact papers published in the last 5 years.\n"
                "2. Research Trends & Thematic Clusters (3-4 Key Themes):\n"
                "   - Provide insightful thematic clusters synthesizing the landscape (e.g. architecture evolution, multimodal sentiment, domain applications, low-resource languages).\n"
                "   - Highlight key methodologies, models, and findings.\n"
                "3. Call-to-Action & Sources Report:\n"
                "   - Inform the user that all {len(papers)} papers with metadata, DOI links, and summaries are ready in the interactive Source Card below for one-click import into the workspace panel.\n"
                "4. NEVER be passive or tell the user to manually search Google Scholar."
            )

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

            for i, fname in enumerate(local_docs):
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
                            # If it contains our fallback archive header or file is small, it's an abstract brief
                            if "NOTBOOKLM SCHOLARLY ARCHIVE" in parsed_text or fsize < 35000:
                                is_full_paper = False
                            else:
                                is_full_paper = True
                            # Dynamic allocation: keep rich content without blowing context limits
                            max_chars = 2500 if len(local_docs) > 20 else 6000
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

                full_docs_context_parts.append(
                    f"--- DOKUMEN [{i+1}] ---\n"
                    f"Nomor Dokumen: [{i+1}]\n"
                    f"Judul Publikasi: {doc_display_title}\n"
                    f"Nama File: {fname}\n"
                    f"Status Naskah: {status_header}\n"
                    f"Teks Dokumen:\n{content_snippet}\n"
                )
            
            full_docs_context = "\n\n".join(full_docs_context_parts)
            
            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "You are NotbookLM, an advanced AI research assistant and academic literature specialist.\n\n"
                    "LANGUAGE RULE (CRITICAL):\n"
                    "- Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese/Basa Jawa -> Basa Jawa, Spanish -> Spanish, etc.).\n\n"
                    f"This chat session has {len(local_docs)} imported reference documents in the workspace.\n"
                    "Use ALL document data to answer the user's query comprehensively, accurately, and with clear structure.\n\n"
                    "SOURCE INTEGRITY RULE (CRITICAL):\n"
                    "- Every document in the workspace (whether full manuscript or publication brief/abstract) is a 100% valid, verified academic source.\n"
                    "- NEVER make excuses such as 'naskah tidak lengkap', 'hanya abstrak', 'paywalled', 'HTTP 403', or 'fitur highlight nonaktif'. All sources are fully supported by the system's evidence highlighting engine.\n\n"
                    "CITATION & TABLE RULES (CRITICAL - STRICT GROUNDING & MANDATORY CITATIONS):\n"
                    "- Every reference document in workspace has a permanent Global Reference Number: [1], [2], [3], etc. as written in its header.\n"
                    "- MANDATORY CITATIONS ON ALL CLAIMS, ESSAYS, DRAFTS, & TABLES:\n"
                    "  Whenever discussing, comparing, listing, drafting papers/chapters (e.g. Bab 1 Pendahuluan), or synthesizing information from workspace documents, you MUST explicitly attach bracketed citations [1], [2], [3] directly to EVERY factual statement, method, algorithm, finding, and metric.\n"
                    "- MASTER COMPARISON TABLE ARCHITECTURE (When requested/applicable):\n"
                    "  1. When comparing documents or presenting synthesis tables, ALWAYS output strictly ONE single Master Table encompassing all documents (1 row = 1 document).\n"
                    "  2. Standard columns: `Dokumen / Judul | Metode yang Dipakai | Temuan Utama | Limitasi | Rekomendasi`.\n"
                    "  3. STRICTLY FORBIDDEN: NEVER create separate sub-tables per document.\n"
                    "  4. IN EVERY TABLE CELL: Attach bracketed citations [1], [2], etc. directly beside EVERY claim and metric.\n"
                    "- ZERO MANUAL QUOTE DUMP RULE:\n"
                    "  1. DO NOT dump raw manual quotes or write static location text (e.g. NEVER write 'Halaman X, Paragraf Y' or 'Abstrak Baris Z' in the chat body).\n"
                    "  2. Provide the synthesized answer/draft/table with [1], [2], [3] citations. The user clicks [X] to view highlighted proof in the sidebar.\n"
                    "  3. Store the exact verbatim sentences in the hidden <!-- CITATION_MAP --> block for precision highlighting.\n\n"
                    "AI CITATION GROUNDING MAP (CRITICAL REQUIREMENT - MANDATORY ON EVERY RESPONSE WITH CITATIONS):\n"
                    "At the VERY END of your response, you MUST ALWAYS append a hidden JSON metadata block.\n"
                    "For EACH cited document number [X] appearing in your response (in tables, essay paragraphs, draft chapters, or bullet points), extract the EXACT verbatim sentence(s) from that document that contain the specific claim, method, algorithm, or metric you cited.\n\n"
                    "Format strictly as:\n"
                    "<!-- CITATION_MAP: {\n"
                    "  \"1\": [\"The authors use tweets from President Candidates of Indonesia (Jokowi and Prabowo), and tweets from relevant hashtags for sentiment analysis gathered from March to July 2018 to predict Indonesian Presidential election result.\"],\n"
                    "  \"2\": [\"Selanjutnya akan melalui beberapa tahapan dalam melaukan analisis sentimen, antara lain adalah tahap pengumpulan data, data correction, preprocessing data, dan klasifikasi menggunakan Naïve Bayes Classifier serta dilakukan asosiasi teks.\"],\n"
                    "  \"3\": [\"Analisis sentimen mengungkapkan persepsi publik yang dominan positif terhadap kebijakan MBG, meskipun bias model hadir karena ketidakseimbangan data.\"]\n"
                    "} -->\n\n"
                    "Ensure EVERY cited document number in your response has at least one verbatim excerpt in CITATION_MAP."
                )
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
            system_prompt=(
                "You are NotbookLM, a powerful, proactive AI research assistant.\n"
                "LANGUAGE RULE: Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English, Indonesian, Javanese, Spanish).\n"
                "Always maintain conversation context from the chat history.\n"
                f"{doc_context_info}\n"
                "- If the user requests data, paper search, analysis, or summaries, perform it directly using tools.\n"
                "- MANDATORY CITATION RULE: Whenever referring to local workspace documents, always cite using square brackets [1], [2], [3] directly on every factual claim, method, finding, and metric.\n"
                "- ZERO QUOTE DUMP RULE: Never dump raw manual quotes into the chat text. The user inspects evidence by clicking [X] buttons which highlight text directly in the document.\n"
                "- Never output internal thoughts or monologues. Output only the final response."
            )
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
