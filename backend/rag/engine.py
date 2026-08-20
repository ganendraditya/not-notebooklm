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
                            # Remove physical file if exists
                            uploads_d = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
                            fp = os.path.join(uploads_d, f"{chat_id}_{dd.filename}")
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

            for i, fname in enumerate(local_docs):
                fpath = os.path.join(uploads_dir, f"{chat_id}_{fname}")
                if not os.path.exists(fpath):
                    fpath = os.path.abspath(os.path.join(os.getcwd(), "uploads", f"{chat_id}_{fname}"))
                    
                content_snippet = ""
                db_record = db_docs_by_filename.get(fname)
                
                # 1. Try reading physical file first
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                            raw_text = fp.read()
                            # If file is real text/markdown, use it
                            if len(raw_text.strip()) >= 150:
                                max_chars = 1200 if len(local_docs) > 20 else 3000
                                content_snippet = raw_text[:max_chars]
                    except Exception:
                        pass
                        
                # 2. If physical file is missing, empty, or short stub: read from DB metadata
                if (not content_snippet or len(content_snippet.strip()) < 150) and db_record:
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
                    "USER INSTRUCTION DISCIPLINE (CRITICAL):\n"
                    "- If the user is ASKING A QUESTION (e.g. 'apakah ada yang ga relevan?', 'sebutkan yang ga cocok', 'crosscheck dong'): ANSWER THE QUESTION FIRST clearly with the list of documents and reasons. DO NOT delete or remove anything autonomously unless the user explicitly commands you with action words (e.g. 'tolong hapus', 'hapusin', 'delete these').\n"
                    "- If the user explicitly asks to delete specific papers, confirm and remove only the requested papers.\n\n"
                    "CAPABILITY REMINDER:\n"
                    "- You have backend access to remove documents when explicitly commanded.\n\n"
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
