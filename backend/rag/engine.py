import os
import re
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
from .search import search_academic_papers

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
    load_dotenv(override=True)
    ninerouter_url = os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
    ninerouter_key = os.getenv("NINEROUTER_API_KEY")
    ninerouter_model = os.getenv("NINEROUTER_MODEL", "ag/claude-sonnet-4-6")
    
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
            print(f"[RAG Engine] 9Router initialization failed: {e}")

    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    freellm_url = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
    freellm_key = os.getenv("FREELLMAPI_API_KEY", "dummy")
    freellm_model = os.getenv("FREELLMAPI_MODEL", "gpt-oss-120b")
    
    freellm_llm = None
    try:
        freellm_llm = OpenAILike(
            api_base=freellm_url,
            api_key=freellm_key or "dummy",
            model=freellm_model or "gpt-4o-mini",
            is_chat_model=True,
            is_function_calling_model=True,
            max_tokens=8192,
            timeout=90.0
        )
    except Exception as e:
        print(f"[RAG Engine] FreeLLMAPI not configured: {e}")
    
    gemini_llm = None
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gemini_llm = Gemini(
                model="models/gemini-flash-latest", 
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            print(f"[RAG Engine] Warning: Gemini initialization failed: {e}")
            
    groq_llm = None
    if groq_key and not groq_key.startswith("your_"):
        try:
            groq_llm = Groq(
                model="qwen/qwen-2.5-32b", 
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            print(f"[RAG Engine] Warning: Groq initialization failed: {e}")
            
    return ninerouter_llm, freellm_llm, gemini_llm, groq_llm

ninerouter_llm, freellm_llm, gemini_llm, groq_llm = create_llm_instances()
Settings.llm = ninerouter_llm or freellm_llm or gemini_llm or groq_llm

def ingest_document_text(text: str, filename: str, chat_id: str):
    """Ingests raw text into the vector database under a specific chat_id."""
    doc = Document(
        text=text,
        metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
    )
    VectorStoreIndex.from_documents([doc], vector_store=vector_store, show_progress=True)
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
        doc_list_str = "\n".join([f"  {i+1}. {fname}" for i, fname in enumerate(local_docs[:20])])
        if len(local_docs) > 20:
            doc_list_str += f"\n  ... dan {len(local_docs) - 20} dokumen lainnya."
        doc_context_info = (
            f"INFORMASI SUMBER REFERENSI SESI INI:\n"
            f"- Sesi chat ini memiliki total {len(local_docs)} dokumen referensi aktif yang diimpor:\n"
            f"{doc_list_str}\n"
            f"- Selalu gunakan fakta ini secara akurat saat menjawab pertanyaan pengguna mengenai jumlah atau daftar dokumen yang tersedia."
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
            
    selected_provider = os.getenv("LLM_PROVIDER", "freellmapi").lower()
    
    if selected_provider == "9router" and ninerouter_llm:
        active_llm = ninerouter_llm
        primary_name = f"9Router ({os.getenv('NINEROUTER_MODEL', 'ag/claude-sonnet-4-6')})"
        fallback_llm = freellm_llm or gemini_llm or groq_llm
        fallback_name = "FreeLLMAPI" if freellm_llm else ("Gemini" if gemini_llm else "Groq")
    elif selected_provider == "freellmapi" and freellm_llm:
        active_llm = freellm_llm
        primary_name = f"FreeLLMAPI ({os.getenv('FREELLMAPI_MODEL', 'gpt-oss-120b')})"
        fallback_llm = ninerouter_llm or gemini_llm or groq_llm
        fallback_name = "9Router" if ninerouter_llm else ("Gemini" if gemini_llm else "Groq")
    elif selected_provider == "groq" and groq_llm:
        active_llm = groq_llm
        primary_name = "Groq (Qwen 2.5 32B)"
        fallback_llm = gemini_llm or freellm_llm or ninerouter_llm
        fallback_name = "Gemini" if gemini_llm else "FreeLLMAPI"
    elif gemini_llm:
        active_llm = gemini_llm
        primary_name = "Google Gemini Flash"
        fallback_llm = freellm_llm or groq_llm or ninerouter_llm
        fallback_name = "FreeLLMAPI" if freellm_llm else "Groq"
    else:
        active_llm = freellm_llm or groq_llm or ninerouter_llm
        primary_name = "Default Fallback"
        fallback_llm = None
        fallback_name = "None"
        
    if not active_llm:
        return "Error: Tidak ada LLM Provider yang terkonfigurasi. Silakan periksa file .env."

    def clean_response(text: str) -> str:
        text = re.sub(r'Thought:[\s\S]*?(?=Action:|Answer:|$)', '', text)
        text = re.sub(r'Action:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'Action Input:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'Observation:[\s\S]*?(?=Answer:|$)', '', text)
        text = re.sub(r'^Answer:\s*', '', text, flags=re.MULTILINE)
        return text.strip()

    def is_simple_conversational(text: str) -> bool:
        t = text.lower().strip()
        greetings = [
            "halo", "hai", "hi", "hello", "pagi", "siang", "sore", "malam",
            "terima kasih", "makasih", "thanks", "thank you", "siapa kamu",
            "bisa apa", "kamu siapa", "tes", "test", "ping", "bisa bantu apa"
        ]
        if any(t == g or t.startswith(g + " ") or t.endswith(" " + g) for g in greetings) and len(t.split()) <= 4:
            return True
        return False

    def is_sources_capacity_query(text: str) -> bool:
        t = text.lower().strip()
        phrases = [
            "berapa dokumen", "berapa file", "berapa banyak dokumen", "berapa jumlah dokumen",
            "berapa total dokumen", "jumlah dokumen", "daftar dokumen", "ada berapa dokumen",
            "ada dokumen apa", "dokumen apa saja", "list dokumen", "sebutkan dokumen",
            "dokumen yang diupload", "dokumen yang diimpor", "berapa source", "jumlah source",
            "berapa referensi", "daftar referensi", "ada referensi apa"
        ]
        return any(p in t for p in phrases)

    def is_sources_meta_query(text: str) -> bool:
        t = text.lower().strip()
        meta_phrases = [
            "apa saja topiknya", "topik apa saja", "analisis topik", "rangkum topik",
            "ringkas topik", "topik dari dokumen", "topik dokumen", "cakupan dokumen",
            "tema dokumen", "tema paper", "variasi topik", "pembagian topik"
        ]
        return any(p in t for p in phrases for phrases in [meta_phrases])

    async def execute_agent(target_llm, timeout_sec=30.0):
        # 1. Handle casual conversational messages
        if is_simple_conversational(query):
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, a helpful, intelligent personal research assistant. "
                        "Respond to greetings politely, warmly, and concisely in Indonesian. "
                        "Inform the user you can help them analyze research papers, find scholarly sources, extract insights, and answer academic questions."
                    )
                ),
                *(formatted_history[-4:] if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Thinking...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 2. Handle meta-capacity queries
        if is_sources_capacity_query(query):
            if not has_local_docs:
                return "Saat ini belum ada dokumen atau paper yang diimpor ke dalam sesi percakapan ini. Anda dapat mengunggah file (PDF, Word, RIS, BibTeX) atau mencari paper melalui panel pencarian di sebelah kanan."
            
            chat_msgs = [
                LlamaChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are NotbookLM, a helpful personal research assistant. "
                        f"{doc_context_info}\n"
                        "The user is asking about the documents/sources currently loaded in this chat session. "
                        "Answer accurately, stating the exact number of documents and listing their filenames neatly in Indonesian."
                    )
                ),
                *(formatted_history[-4:] if formatted_history else []),
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            await report_status("Checking loaded workspace documents...")
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 3. Handle query routing
        async def judge_intent_with_ai(user_query: str, has_docs: bool) -> str:
            judge_prompt = f"""
Analyze this user query in a research assistant workspace:
User Query: "{user_query}"
Workspace has uploaded documents: {has_docs}

Classify into exactly ONE category:
- SEARCH_NEW: User explicitly wants to find NEW papers, search scholarly literature, get more papers.
- ANALYZE_WORKSPACE: User wants to compare, analyze, summarize, make a table, extract methods from existing workspace documents.
- GENERAL_QA: General academic/conceptual question.

Output ONLY the category name.
"""
            try:
                judge_resp = await target_llm.acomplete(judge_prompt)
                category = judge_resp.text.strip().upper()
                if "SEARCH_NEW" in category: return "SEARCH_NEW"
                if "ANALYZE_WORKSPACE" in category: return "ANALYZE_WORKSPACE"
                if "GENERAL_QA" in category: return "GENERAL_QA"
            except Exception as e:
                print(f"[AI Intent Judge Warning]: {e}")
            return "ANALYZE_WORKSPACE" if has_docs else "SEARCH_NEW"

        intent = await judge_intent_with_ai(query, has_local_docs)
        print(f"[RAG Engine] AI Classified Intent: {intent}")

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
                            content_snippet = fp.read()[:4000]
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
                    "Anda adalah NotbookLM, asisten riset dan komparasi literatur ilmiah tingkat tinggi. "
                    "Gunakan BAHASA INDONESIA yang baku, profesional, dan komprehensif.\n\n"
                    f"Sesi percakapan ini memiliki total {len(local_docs)} dokumen referensi aktif yang diimpor.\n"
                    "Gunakan SELURUH data dokumen ini untuk menjawab instruksi pengguna secara lengkap, terstruktur, dan mendalam."
                    "ATURAN SITASI REFERENSI GLOBAL (IEEE STYLE - SANGAT PENTING):\n"
                    "- Setiap dokumen referensi memiliki Nomor Referensi Global tetap: [1], [2], [3], dst yang tertulis di header dokumen.\n"
                    "- Saat mengutip, merujuk temuan, membandingkan metode, atau membuat tabel, SELALU sertakan sitasi bracket nomor yang sesuai, contoh: [1], [2], [3], [1, 2], atau [1]-[3].\n"
                    "- Nomor referensi ini bersifat permanen dan konsisten di seluruh percakapan. Jangan mengubah nomor referensi sebuah dokumen!\n\n"
                    "ATURAN STATUS INDEKSASI & KUARTIL JURNAL (SANGAT KETAT):\n"
                    "- Selalu gunakan data status indeksasi resmi yang tertera pada header dokumen (**Status Indeksasi** dan **Jurnal/Venue**).\n"
                    "- JANGAN PERNAH melabeli 'Conference Proceedings' sebagai Jurnal Q1/Q2/Q3/Q4.\n"
                    "- Jika suatu jurnal terdaftar sebagai 'Scopus Q2 (SJR)', sebutlah secara akurat sebagai Q2. Jangan mengubahnya menjadi Q1.\n\n"
                    "ATURAN MANAJEMEN PANJANG RESPON & TABEL MASIF (SANGAT KETAT):\n"
                    "1. DILARANG KERAS memotong teks di tengah kalimat atau di tengah baris tabel!\n"
                    "2. Jika pengguna meminta format tabel atau analisis mendalam untuk banyak dokumen (> 20 dokumen):\n"
                    "   - Batasi tabel maksimal 20 dokumen per pesan (misalnya Bagian 1: Dokumen 1–20).\n"
                    "   - Selesaikan dan tutup tabel Bagian 1 secara rapi dengan format markdown lengkap.\n"
                    "   - Di baris paling bawah, berikan catatan transparan:\n"
                    "     '💡 **Catatan**: Untuk menjaga kedalaman analisis setiap dokumen dan menghindari keterbatasan panjang teks, Bagian 1 menyajikan dokumen 1–20. Ketik **\"Lanjutkan bagian 2\"** untuk melihat sisa dokumen berikutnya.'\n"
                    "3. Ketika pengguna meminta 'lanjutkan', 'bagian 2', atau 'next', lanjutkan secara mulus dari nomor dokumen berikutnya (misalnya Dokumen 21–35) sampai selesai tuntas."
                )
            )
            context_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=f"BERIKUT ADALAH SELURUH DATA & TEKS DOKUMEN REFERENSI YANG DIIMPOR ({len(local_docs)} DOKUMEN):\n\n{full_docs_context}"
            )
            chat_msgs = [
                system_msg,
                *(formatted_history[-8:] if formatted_history else []),
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
                "You are NotbookLM, a helpful personal research assistant. "
                "Always communicate in Indonesian (Bahasa Indonesia). "
                "Always maintain conversation context from the chat history. "
                f"{doc_context_info}\n"
                "Present the final output directly in the requested format (such as Markdown tables). "
                "Do NOT output internal thoughts or monologues. Output only the final response."
            )
        )
        res = await agent.run(user_msg=query, chat_history=formatted_history if formatted_history else None)
        return clean_response(str(res))

    try:
        print(f"[RAG Engine] Attempting query with primary LLM: {primary_name}")
        return await execute_agent(active_llm, timeout_sec=35.0)
    except Exception as e:
        err_str = str(e)
        if fallback_llm and fallback_llm != active_llm:
            print(f"[RAG Fallback] {primary_name} failed or timed out: {err_str}")
            print(f"[RAG Fallback] -> Automatically falling back to {fallback_name}...")
            try:
                return await execute_agent(fallback_llm, timeout_sec=45.0)
            except Exception as fb_err:
                print(f"[RAG Fallback] {fallback_name} also failed: {fb_err}")
                raise fb_err
        else:
            raise e
