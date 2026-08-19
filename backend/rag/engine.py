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

collection_name = "not_notebooklm"

vector_store = QdrantVectorStore(client=qdrant_client, collection_name=collection_name, path=None, url=None, api_key=None)

# Setup default embeddings
Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=os.getenv("GEMINI_API_KEY"))

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
            if role == MessageRole.ASSISTANT and "<!-- SOURCES_DATA" in content:
                content = content.split("<!-- SOURCES_DATA")[0].strip()
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
        meta_phrases = [
            "berapa dokumen", "berapa file", "berapa banyak dokumen", "berapa jumlah dokumen",
            "berapa total dokumen", "jumlah dokumen", "daftar dokumen", "ada berapa dokumen",
            "ada dokumen apa", "dokumen apa saja", "list dokumen", "sebutkan dokumen",
            "dokumen yang diupload", "dokumen yang diimpor", "berapa source", "jumlah source",
            "berapa referensi", "daftar referensi", "ada referensi apa", "berapa doang", "berapa yang",
            "yang mana saja", "yang relevan", "relevan berapa", "yang cocok berapa"
        ]
        return any(p in t for p in meta_phrases)

    async def execute_agent(target_llm, timeout_sec=60.0):
        # 1. Handle casual conversational messages
        if is_simple_conversational(query):
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, an intelligent, friendly, and adaptive AI research assistant (like Google NotebookLM).\n"
                        "LANGUAGE RULE (CRITICAL):\n"
                        "- Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese/Basa Jawa -> Basa Jawa, Spanish -> Spanish, etc.).\n"
                        "- Keep your tone natural, helpful, and concise.\n"
                        "- State that you are ready to search academic papers, analyze uploaded documents, or extract research insights."
                    )
                ),
                *(formatted_history if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Thinking...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 2. Handle Technical / Conceptual / System Mechanism Discussion (Fast Direct Synthesis)
        if is_technical_discussion(query):
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, an advanced, transparent, and communicative AI research assistant (Google NotebookLM style).\n"
                        "The user is asking about your internal workings, RAG system, vector database, or capabilities.\n\n"
                        "LANGUAGE RULE (CRITICAL):\n"
                        "- Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese -> Basa Jawa, Spanish -> Spanish).\n\n"
                        "NOTBOOKLM ARCHITECTURE FACTS:\n"
                        "1. Retrieval-Augmented Generation (RAG): Primary system uses Qdrant Vector Database with BAAI/bge-small-en-v1.5 embeddings.\n"
                        "2. Document Storage: Every uploaded/imported document is chunked, vector-embedded, and stored privately per chat session.\n"
                        "3. Paper Search: Connected directly to verified academic APIs: OpenAlex (250M+ papers), Europe PMC, and Crossref.\n"
                        "4. Open Access & Paywalls: Full-text extraction for Open Access papers. For paywalled papers, official abstracts and public metadata are indexed, with guidance to upload manual PDFs if institutional access is available.\n"
                        "5. Citations: Research answers cite document references `[1]`, `[2]` linked directly to document metadata.\n"
                    )
                ),
                *(formatted_history if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Explaining system architecture...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 2. Fast Meta/Capacity Queries (Direct LLM call with metadata list, no agentic loop)
        if is_sources_meta_query(query) and has_local_docs:
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, an intelligent research assistant. "
                        f"{doc_context_info}\n\n"
                        "Task: Answer the user's inquiry regarding the documents imported into this workspace accurately and concisely.\n"
                        "LANGUAGE RULE: Always match the language used by the user in their prompt."
                    )
                ),
                *(formatted_history if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Checking loaded workspace documents...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)
            await report_status("Checking loaded workspace documents...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 3. Handle query routing
        def resolve_intent_fast(user_query: str, has_docs: bool) -> str:
            uq = user_query.lower()
            search_triggers = [
                "cariin", "carikan", "cari paper", "cari jurnal", "search paper", "find paper",
                "tambah paper", "tambah referensi", "more paper", "find more", "paper", "jurnal",
                "artikel", "literatur", "makalah", "rekomendasi", "rekomendasikan", "import ke source",
                "import to source", "masukin ke source", "masukkan ke source", "add to source", "add source",
                "bisa diimport", "bisa di-import", "masuk ke sources", "masuk sources"
            ]
            if any(st in uq for st in search_triggers):
                return "SEARCH_NEW"
            if has_docs:
                return "ANALYZE_WORKSPACE"
            return "GENERAL_CHAT"

        intent = resolve_intent_fast(query, has_local_docs)
        print(f"[RAG Engine] Fast Resolved Intent: {intent}")

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
            
            for i, fname in enumerate(local_docs):
                fpath = os.path.join(uploads_dir, f"{chat_id}_{fname}")
                if not os.path.exists(fpath):
                    fpath = os.path.abspath(os.path.join(os.getcwd(), "uploads", f"{chat_id}_{fname}"))
                    
                content_snippet = ""
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                            raw_text = fp.read()
                            # Efficient context compression when loading large document sets (> 15 docs)
                            max_chars = 1200 if len(local_docs) > 20 else 3000
                            content_snippet = raw_text[:max_chars]
                    except Exception:
                        content_snippet = f"(Nama file: {fname})"
                else:
                    content_snippet = f"(Nama file: {fname})"
                    
                full_docs_context_parts.append(
                    f"--- DOKUMEN [{i+1}] ---\n"
                    f"Nomor Dokumen: [{i+1}]\n"
                    f"Nama File: {fname}\n"
                    f"Isi/Abstrak/Metadata:\n{content_snippet}\n"
                )
            
            full_docs_context = "\n\n".join(full_docs_context_parts)
            
            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "You are NotbookLM, an advanced AI research assistant and academic literature comparison specialist.\n\n"
                    "LANGUAGE RULE (CRITICAL):\n"
                    "- Always respond in the EXACT same language or dialect as the user's latest prompt (e.g. English -> English, Indonesian -> Indonesian, Javanese/Basa Jawa -> Basa Jawa, Spanish -> Spanish, etc.).\n\n"
                    f"This chat session has {len(local_docs)} imported reference documents in the workspace.\n"
                    "Use ALL document data to answer the user's query comprehensively, accurately, and with clear structure.\n\n"
                    "CITATION RULES (IEEE STYLE - VERY IMPORTANT):\n"
                    "- Every reference document has a permanent Global Reference Number: [1], [2], [3], etc. as written in the document header.\n"
                    "- When citing, quoting findings, comparing methods, or building tables, ALWAYS include bracketed number citations, e.g. [1], [2], [3], [1, 2], or [1]-[3].\n"
                    "- Never alter or renumber reference IDs.\n\n"
                    "INDEXING & QUARTILE RULES:\n"
                    "- Rely strictly on the official indexing status in the document headers (**Indexing Status** and **Journal/Venue**).\n"
                    "- Never label 'Conference Proceedings' as Q1/Q2/Q3/Q4 journals.\n\n"
                    "MASSIVE TABLE & LENGTH MANAGEMENT:\n"
                    "1. Never truncate in the middle of sentences or table rows.\n"
                    "2. For large comparison requests (> 20 documents), present up to 20 documents per part and prompt the user to request the next part."
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
