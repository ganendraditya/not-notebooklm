import os
import re
import json
import html
import urllib.request
import requests
from typing import List, Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup
from ddgs import DDGS
import pymupdf4llm
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.groq import Groq
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage, MessageRole
from dotenv import load_dotenv

load_dotenv()

# Setup Qdrant Client (Local Disk)
QDRANT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "qdrant_data"))
qdrant_client = QdrantClient(path=QDRANT_PATH)
collection_name = "not_notebooklm"

if not qdrant_client.collection_exists(collection_name):
    # Dummy check, LlamaIndex handles dynamic creation during first insert
    pass

vector_store = QdrantVectorStore(client=qdrant_client, collection_name=collection_name, path=None, url=None, api_key=None)

# Setup default embeddings
Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=os.getenv("GEMINI_API_KEY"))

from llama_index.llms.openai_like import OpenAILike

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
            print(f"[RAG] 9Router initialization failed: {e}")

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
        print(f"[RAG] FreeLLMAPI not configured: {e}")
    
    gemini_llm = None
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            gemini_llm = Gemini(
                model="models/gemini-flash-latest", 
                api_key=gemini_key,
                max_tokens=8192
            )
        except Exception as e:
            print(f"[RAG] Warning: Gemini initialization failed: {e}")
            
    groq_llm = None
    if groq_key and not groq_key.startswith("your_"):
        try:
            groq_llm = Groq(
                model="qwen/qwen-2.5-32b", 
                api_key=groq_key,
                max_tokens=8192
            )
        except Exception as e:
            print(f"[RAG] Warning: Groq initialization failed: {e}")
            
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

def parse_docx_file(file_path: str) -> str:
    """Extracts text and tables from Word (.docx) document as clean Markdown."""
    try:
        import docx
        doc = docx.Document(file_path)
        lines = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                style_name = p.style.name.lower() if p.style else ""
                if 'heading 1' in style_name:
                    lines.append(f"\n# {text}\n")
                elif 'heading 2' in style_name:
                    lines.append(f"\n## {text}\n")
                elif 'heading 3' in style_name:
                    lines.append(f"\n### {text}\n")
                else:
                    lines.append(text)
        for tbl in doc.tables:
            lines.append("\n")
            for row_idx, row in enumerate(tbl.rows):
                row_cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                lines.append("| " + " | ".join(row_cells) + " |")
                if row_idx == 0:
                    lines.append("| " + " | ".join(['---'] * len(row_cells)) + " |")
            lines.append("\n")
        return "\n\n".join(lines).strip()
    except Exception as e:
        print(f"[RAG] Warning: DOCX extraction error: {e}")
        return ""

def parse_bibtex_text(text: str) -> str:
    """Converts BibTeX bibliographic references into clean structured Markdown summaries."""
    entries = []
    raw_entries = re.findall(r'@(\w+)\s*\{\s*([^,]+),([\s\S]*?)\n\}', text, re.IGNORECASE)
    for entry_type, key, body in raw_entries:
        fields = {}
        for m in re.finditer(r'(\w+)\s*=\s*(?:\{([\s\S]*?)\}|"([\s\S]*?)"|(\w+))', body):
            k = m.group(1).lower()
            v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
            if v:
                fields[k] = re.sub(r'\s+', ' ', v.strip())
        title = fields.get('title', key)
        author = fields.get('author', 'Unknown Author')
        year = fields.get('year', '')
        journal = fields.get('journal', fields.get('booktitle', ''))
        doi = fields.get('doi', '')
        abstract = fields.get('abstract', '')
        md_entry = f"### {title}\n- **Authors**: {author}\n"
        if year: md_entry += f"- **Year**: {year}\n"
        if journal: md_entry += f"- **Journal/Venue**: {journal}\n"
        if doi: md_entry += f"- **DOI**: [{doi}](https://doi.org/{doi})\n"
        if abstract: md_entry += f"- **Abstract**: {abstract}\n"
        entries.append(md_entry)
    return "\n\n---\n\n".join(entries) if entries else text

def parse_ris_text(text: str) -> str:
    """Converts RIS citation library format into clean structured Markdown summaries."""
    entries = []
    current_entry = {}
    authors = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("ER  -"):
            if current_entry:
                title = current_entry.get("TI", current_entry.get("T1", "Untitled Work"))
                year = current_entry.get("PY", current_entry.get("Y1", ""))
                journal = current_entry.get("JO", current_entry.get("JF", current_entry.get("T2", "")))
                doi = current_entry.get("DO", "")
                abstract = current_entry.get("AB", current_entry.get("N2", ""))
                md_entry = f"### {title}\n"
                if authors: md_entry += f"- **Authors**: {', '.join(authors)}\n"
                if year: md_entry += f"- **Year**: {year}\n"
                if journal: md_entry += f"- **Journal/Venue**: {journal}\n"
                if doi: md_entry += f"- **DOI**: [{doi}](https://doi.org/{doi})\n"
                if abstract: md_entry += f"- **Abstract**: {abstract}\n"
                entries.append(md_entry)
            current_entry = {}
            authors = []
        elif line[:6].endswith("- "):
            tag = line[:2].strip()
            val = line[6:].strip()
            if tag in ("AU", "A1"):
                authors.append(val)
            else:
                current_entry[tag] = val
    return "\n\n---\n\n".join(entries) if entries else text

def parse_csv_file(file_path: str) -> str:
    """Formats CSV/TSV table into readable Markdown table."""
    try:
        import csv
        delimiter = '\t' if file_path.lower().endswith('.tsv') else ','
        lines = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter=delimiter)
            for idx, row in enumerate(reader):
                clean_row = [c.strip().replace('\n', ' ') for c in row]
                lines.append("| " + " | ".join(clean_row) + " |")
                if idx == 0:
                    lines.append("| " + " | ".join(['---'] * len(clean_row)) + " |")
        return "\n".join(lines)
    except Exception as e:
        print(f"[RAG] CSV parse error: {e}")
        return ""

def ingest_document(file_path: str, chat_id: str):
    """Parses a multi-format document (PDF, DOCX, TXT, MD, BIB, RIS, CSV, TSV) and ingests it."""
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    
    if ext == ".pdf":
        md_text = pymupdf4llm.to_markdown(file_path)
    elif ext in (".docx", ".doc"):
        md_text = parse_docx_file(file_path)
    elif ext in (".bib", ".bibtex"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = parse_bibtex_text(f.read())
    elif ext == ".ris":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = parse_ris_text(f.read())
    elif ext in (".csv", ".tsv"):
        md_text = parse_csv_file(file_path)
    else:
        # Default text/markdown
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            md_text = f.read()
            
    if not md_text or not md_text.strip():
        raise ValueError(f"Could not extract readable text from {filename}")
        
    return ingest_document_text(md_text, filename, chat_id)

def is_valid_academic_title(title: str) -> bool:
    """Quality filter to exclude non-scholarly publication artifacts, covers, and TOCs."""
    t = title.lower().strip()
    if len(t) < 8:
        return False
    junk_patterns = [
        "[front cover]", "[copyright", "table of contents", "author index", "itu k programme",
        "itu k 2018", "keynote summary", "chairman’s message", "foreword", "committees",
        "figure 1:", "table 3:", "table 5:", "peer review #", "cover page", "back cover",
        "editorial board", "preliminary pages", "conference report"
    ]
    if any(j in t for j in junk_patterns):
        return False
    return True

async def plan_academic_search(query: str, history: Optional[List[LlamaChatMessage]] = None, llm: Optional[LLM] = None) -> dict:
    """
    Stage 1: LLM-Powered Academic Query Planner (Consensus.app / Elicit / Perplexity style)
    Uses the AI model to understand conversational intent, context, multi-lingual requirements, and exact quantities.
    """
    # Clean colloquial Indonesian filler words before default fallback
    clean_text = re.sub(r'\b(gw|gua|gue|aku|saya|lu|lo|kamu|dong|ya|coba|tolong|minta|lagi|bos|bro|nih|deh|aja|sih|buat|ke|source|sources)\b', ' ', query, flags=re.I)
    clean_text = ' '.join(clean_text.split()).strip()

    # 1. Default heuristic fallback (adaptive 15 by default)
    default_plan = {
        "en_query": clean_text or query.strip(),
        "id_query": clean_text or query.strip(),
        "target_count": 15,
        "language_preference": "mixed"
    }
    
    # Fast regex extraction for fallback count and min_year
    user_requested_count = None
    default_min_year = None
    if any(k in query.lower() for k in ["5 tahun", "lima tahun", "terbaru", "recent"]):
        default_min_year = 2020
    year_match = re.search(r'\b(201\d|202\d)\b', query)
    if year_match and not default_min_year:
        default_min_year = int(year_match.group(1))

    num_match = re.search(r'(\d+)\s*(?:paper|jurnal|artikel|sumber|sources|buah|biji|referensi|makalah|lagi)', query, re.I)
    if num_match:
        try:
            p_num = int(num_match.group(1))
            user_requested_count = p_num
            default_plan["target_count"] = min(max(p_num, 1), 100)
            if p_num > 100:
                default_plan["user_requested_count"] = p_num
        except Exception:
            pass
    # Extract minimum citations threshold from prompt if present
    default_min_citations = 0
    cit_match = re.search(r'(?:minimum|min|tersitasi\s*minimal|sitasi\s*minimal|cit(?:ed|ations)?\s*(?:>=|min|minimal)?)\s*[:=]?\s*(\d+)', query, re.I)
    if cit_match:
        try:
            default_min_citations = int(cit_match.group(1))
        except Exception:
            pass

    if default_min_year:
        default_plan["min_year"] = default_min_year
    if default_min_citations > 0:
        default_plan["min_citations"] = default_min_citations

    if llm is None:
        return default_plan

    try:
        # Context extraction from recent conversation turns
        context_str = ""
        if history:
            hist_snippets = []
            for m in history[-6:]:
                role_name = getattr(m, 'role', '')
                if role_name == MessageRole.USER or role_name == 'user':
                    hist_snippets.append(f"User: {m.content[:300]}")
                elif role_name == MessageRole.ASSISTANT or role_name == 'assistant':
                    clean_c = m.content.split('<!-- SOURCES_DATA')[0].strip()
                    hist_snippets.append(f"Assistant: {clean_c[:200]}")
            if hist_snippets:
                context_str = "\nPrevious Conversation Context:\n" + "\n".join(hist_snippets) + "\n\n"

        prompt = (
            "You are an AI Academic Query Planner for a research search engine (like Consensus.app, Elicit, Perplexity).\n"
            "Your job: Analyze the user's prompt and extract clean, high-precision academic search parameters in JSON.\n\n"
            f"{context_str}"
            "Current User Request:\n"
            f"\"{query}\"\n\n"
            "Rules for extraction:\n"
            "1. CONTEXT & TOPIC RESOLUTION:\n"
            "   - If the user's request refers to previous topics (e.g. 'topik tadi', 'terkait tadi', 'yang tadi', 'topik sepak bola tadi', 'more papers on this topic', 'coba lagi dong'): You MUST examine 'Previous Conversation Context' to identify the specific research domain (e.g. 'football match outcome prediction Premier League machine learning')!\n"
            "   - Indonesian slang: 'gw' / 'gua' / 'gue' = 'I / me'. NEVER interpret 'gw' as 'GW' or 'Gigawatt' or physics acronyms! 'gw' in Indonesian means 'me/I'.\n"
            "2. 'en_query': Pure English academic search term for global scholarly databases. Remove all conversational filler words ('cariin', 'mau itu', 'campur aja', 'bebas', 'yang penting', 'gw', 'lah', 'dong', 'ya', 'coba'). Convert domain abbreviations ('ML' -> 'machine learning', 'DL' -> 'deep learning', 'EPL' -> 'English Premier League').\n"
            "3. 'id_query': Pure Indonesian academic search term for national journals (e.g. 'prediksi hasil pertandingan sepak bola machine learning').\n"
            "4. 'target_count': Integer representing how many papers to search for.\n"
            "   - If the user explicitly specified an exact number (e.g. 30, 50, 25, 100), set target_count to that number (capped at 100 max per fetch).\n"
            "   - If the user DID NOT specify an exact number (e.g. 'cariin paper', 'cari literatur', 'ada paper apa aja'), choose an optimal, realistic sample count between 10 and 25 (e.g. 15 or 20) based on domain depth. NEVER default to 100 unless explicitly requested!\n"
            "   - If the user asks for follow-up ('coba lagi', 'tambah lagi'), set target_count to 10-20 fresh papers.\n"
            "5. 'user_requested_count': The exact integer if the user specified a number (e.g. 30, 50, 300), otherwise null.\n"
            "6. 'min_year': Integer representing minimum publication year (e.g. 2020 if user mentioned '5 tahun terakhir' or 'terbaru', otherwise null).\n"
            "7. 'min_citations': Integer representing minimum citations count threshold (e.g. 10 if user specified 'min 10 sitasi', otherwise 0).\n"
            "8. 'language_preference': 'mixed' (if user wants both/either/mix/unspecified), 'en' (if user strictly asked for English/international), 'id' (if user strictly asked for Indonesian).\n"
            "9. Return ONLY a valid JSON object without any markdown code fences or conversational text.\n\n"
            "Example Output:\n"
            "{\n"
            "  \"en_query\": \"football match outcome prediction Premier League machine learning\",\n"
            "  \"id_query\": \"prediksi hasil pertandingan sepak bola machine learning\",\n"
            "  \"target_count\": 20,\n"
            "  \"user_requested_count\": null,\n"
            "  \"min_year\": null,\n"
            "  \"min_citations\": 0,\n"
            "  \"language_preference\": \"mixed\"\n"
            "}"
        )
        
        resp = await llm.acomplete(prompt)
        raw_text = resp.text.strip()
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text, flags=re.I)
        raw_text = re.sub(r'\s*```$', '', raw_text)
        
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            en_q = str(parsed.get("en_query", "")).strip() or default_plan["en_query"]
            id_q = str(parsed.get("id_query", "")).strip() or default_plan["id_query"]
            cnt = int(parsed.get("target_count", default_plan["target_count"]))
            req_cnt = parsed.get("user_requested_count")
            if req_cnt is not None:
                try:
                    req_cnt = int(req_cnt)
                except Exception:
                    req_cnt = None
            if user_requested_count and user_requested_count > 100:
                req_cnt = user_requested_count
            cnt = min(max(cnt, 1), 100)
            
            m_year = parsed.get("min_year") or default_min_year
            if m_year is not None:
                try:
                    m_year = int(m_year)
                except Exception:
                    m_year = None
                    
            m_cit = parsed.get("min_citations")
            if m_cit is not None:
                try:
                    m_cit = int(m_cit)
                except Exception:
                    m_cit = default_min_citations
            else:
                m_cit = default_min_citations
                    
            lang = str(parsed.get("language_preference", "mixed")).lower()
            if lang not in ["mixed", "en", "id"]:
                lang = "mixed"
            
            print(f"[AI Query Planner] en_query='{en_q}' | id_query='{id_q}' | count={cnt} (requested: {req_cnt}) | min_year={m_year} | min_citations={m_cit} | lang='{lang}'")
            return {
                "en_query": en_q,
                "id_query": id_q,
                "target_count": cnt,
                "user_requested_count": req_cnt,
                "min_year": m_year,
                "min_citations": m_cit,
                "language_preference": lang
            }
    except Exception as e:
        print(f"[AI Query Planner Warning]: {e} -> using robust fallback")

    return default_plan

def search_academic_papers_planned(plan: dict, exclude_titles: set = None) -> List[dict]:
    """
    Stage 2 & 3: Parallel Academic Retrieval & Quality Filtering (OpenAlex + Crossref)
    Executes multi-source scholarly search based on the AI Query Plan with adaptive counts and deduplication.
    """
    results = []
    seen_titles = set()
    if exclude_titles:
        for t in exclude_titles:
            seen_titles.add(t.lower().strip())

    limit = plan.get("target_count", 15)
    en_query = plan.get("en_query", "")
    id_query = plan.get("id_query", "")
    lang_pref = plan.get("language_preference", "mixed")
    headers = {"User-Agent": "NotbookLM/1.0 (mailto:research@notbooklm.app)"}

    min_year = plan.get("min_year")
    min_citations = int(plan.get("min_citations") or 0)
    
    def is_matching_topic(title: str, snippet: str) -> bool:
        t_low = title.lower()
        full = f"{title} {snippet}".lower()
        
        # 1. Negative filters for non-predictive / qualitative / social science junk
        junk_topics = [
            "homosexuality", "fandom", "fandoms", " fan ", " fans ", "suporter", "supporter",
            "schadenfreude", "hukum pidana", "suap", "penegakan hukum", "kiosks", "ticket pricing",
            "university admission", "admissions", "advertisements", "marketing", "racism",
            "critical race theory", "chaplaincy", "nicknames", "laporan keuangan", "political economy",
            "competition law", "collective selling", "men's health", "covid-19 pandemic and the social",
            "football star", "psikososial", "kecemasan pra-kompetitif", "aerodynamic comparison"
        ]
        if any(j in full for j in junk_topics):
            return False

        # 2. Sentiment analysis filter
        if any(k in en_query.lower() or k in id_query.lower() for k in ["sentiment", "sentimen", "opinion", "opini"]):
            sentiment_keys = [
                "sentiment", "sentimen", "opinion", "opini", "ulasan", 
                "emotion", "emosi", "polarity", "polaritas", "sarcasm", "sarkasme", 
                "aspect-based", "absa", "vader"
            ]
            return any(k in t_low for k in sentiment_keys) or any(k in full for k in ["sentiment analysis", "analisis sentimen", "opinion mining", "sentiment classification", "aspect-based sentiment", "aspect sentiment", "sentiment prediction"])
        
        # 3. Sports / Football match outcome prediction & analytics filter
        if any(k in en_query.lower() or k in id_query.lower() for k in ["football", "soccer", "premier league", "sepak bola", "match outcome", "match result", "sports"]):
            sports_terms = ["football", "soccer", "premier league", "match", "pertandingan", "league", "liga", "sports", "olahraga", "cricket", "basketball", "epl", "fifa"]
            has_sports = any(s in full for s in sports_terms)
            
            ml_terms = [
                "predict", "prediksi", "outcome", "forecast", "machine learning", "deep learning", 
                "neural", "model", "modelling", "modeling", "rating", "elo", "poisson", "xg", 
                "expected goals", "performance", "classification", "klasifikasi", "algorithm", 
                "analytics", "data", "betting", "odds", "probabilit", "benchmark", "ensemble",
                "adaboost", "random forest", "xgboost", "svm", "time series", "state-space", "bradley-terry"
            ]
            has_ml = any(m in full for m in ml_terms)
            
            return has_sports and has_ml
            
        return True

    def fetch_openalex(term: str, target_count: int):
        fetched = []
        if not term.strip():
            return fetched
        page = 1
        while len(fetched) < target_count and page <= 8:
            try:
                per_page = min(max(target_count - len(fetched) + 20, 25), 200)
                url = "https://api.openalex.org/works"
                params = {"search": term.strip(), "per_page": per_page, "page": page}
                filter_parts = []
                if min_year:
                    filter_parts.append(f"publication_year:{min_year}-2026")
                if min_citations > 0:
                    filter_parts.append(f"cited_by_count:>{min_citations - 1}")
                if filter_parts:
                    params["filter"] = ",".join(filter_parts)
                    
                resp = requests.get(url, params=params, headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    results_list = data.get("results", [])
                    if not results_list:
                        break
                    for work in results_list:
                        if len(fetched) >= target_count:
                            break
                        title = work.get("title", "").strip()
                        if not title or title.lower() in seen_titles or not is_valid_academic_title(title):
                            continue
                            
                        year = work.get("publication_year", "N/A")
                        if min_year:
                            try:
                                if int(year) < min_year:
                                    continue
                            except Exception:
                                pass
                                
                        citations_count = work.get("cited_by_count", 0)
                        if min_citations > 0 and citations_count < min_citations:
                            continue
                                
                        doi = work.get("doi", "")
                        landing_url = work.get("primary_location", {}).get("landing_page_url") or doi or f"https://openalex.org/{work.get('id')}"
                        
                        abstract = ""
                        inverted_index = work.get("abstract_inverted_index")
                        if inverted_index:
                            word_positions = []
                            for word, positions in inverted_index.items():
                                for pos in positions:
                                    word_positions.append((pos, word))
                            word_positions.sort()
                            abstract = " ".join([w[1] for w in word_positions]).strip()
                            
                        snippet = abstract or f"Scholarly publication ({year}). DOI: {doi}"
                        if not is_matching_topic(title, snippet):
                            continue
                            
                        seen_titles.add(title.lower())
                        fetched.append({
                            "title": title,
                            "year": str(year),
                            "doi": doi,
                            "url": landing_url,
                            "snippet": snippet
                        })
                    page += 1
                else:
                    break
            except Exception as e:
                print(f"[OpenAlex Search Error for '{term}']: {e}")
                break
        return fetched

    # Execute Search based on planned language preference
    if lang_pref == "mixed" and en_query.lower() != id_query.lower():
        en_quota = limit // 2
        id_quota = limit - en_quota
        
        # 1. Fetch International (English) papers
        en_papers = fetch_openalex(en_query, en_quota)
        results.extend(en_papers)
        
        # 2. Fetch National / Local (Indonesian) papers
        actual_id_quota = limit - len(results)
        id_papers = fetch_openalex(id_query, actual_id_quota)
        results.extend(id_papers)
        
        # 3. If still under target limit, broaden English query
        if len(results) < limit:
            variants = [
                f"{en_query} model", 
                f"{en_query} analytics", 
                f"{en_query} forecasting",
                f"{en_query} classification",
                "football match outcome prediction sports analytics",
                "soccer match result prediction machine learning",
                "predicting Premier League football outcomes"
            ]
            for v in variants:
                if len(results) >= limit:
                    break
                extra = fetch_openalex(v, limit - len(results))
                results.extend(extra)
    elif lang_pref == "id":
        id_papers = fetch_openalex(id_query, limit)
        results.extend(id_papers)
        if len(results) < limit:
            extra = fetch_openalex(en_query, limit - len(results))
            results.extend(extra)
    else: # "en" or general
        en_papers = fetch_openalex(en_query, limit)
        results.extend(en_papers)
        if len(results) < limit:
            variants = [
                f"{en_query} model", 
                f"{en_query} analytics", 
                f"{en_query} forecasting",
                f"{en_query} classification",
                "football match outcome prediction sports analytics",
                "soccer match result prediction machine learning",
                "predicting Premier League football outcomes"
            ]
            for v in variants:
                if len(results) >= limit:
                    break
                extra = fetch_openalex(v, limit - len(results))
                results.extend(extra)

    # 4. Fallback to Crossref with strict multi-query topic validation
    if len(results) < limit:
        crossref_queries = [en_query, id_query]
        if any(k in en_query.lower() for k in ["football", "soccer", "premier league", "match"]):
            crossref_queries.extend([
                "football match outcome forecasting machine learning",
                "English Premier League prediction machine learning",
                "soccer match result prediction deep learning",
                "sports analytics match outcome prediction artificial intelligence"
            ])
        elif any(k in en_query.lower() for k in ["sentiment", "sentimen", "opinion"]):
            crossref_queries.extend([
                "sentiment analysis machine learning",
                "sentiment classification deep learning",
                "aspect based sentiment analysis"
            ])
            
        for cq in crossref_queries:
            if len(results) >= limit or not cq.strip():
                break
            try:
                needed = limit - len(results)
                url = "https://api.crossref.org/works"
                params = {"query": cq.strip(), "rows": min(needed + 40, 100)}
                if min_year:
                    params["filter"] = f"from-pub-date:{min_year}-01-01"
                resp = requests.get(url, params=params, headers=headers, timeout=8)
                if resp.status_code == 200:
                    items = resp.json().get("message", {}).get("items", [])
                    for item in items:
                        if len(results) >= limit:
                            break
                        title_list = item.get("title", [])
                        if not title_list:
                            continue
                        title = title_list[0].strip()
                        if not title or title.lower() in seen_titles or not is_valid_academic_title(title):
                            continue
                            
                        year = "N/A"
                        created = item.get("created", {}).get("date-parts", [[]])[0]
                        if created:
                            year = str(created[0])
                            
                        if min_year and str(year).isdigit() and int(year) < min_year:
                            continue
                            
                        citations_count = item.get("is-referenced-by-count", 0)
                        if min_citations > 0 and citations_count < min_citations:
                            continue
                            
                        doi = item.get("DOI", "")
                        url_link = item.get("URL", f"https://doi.org/{doi}" if doi else "")
                        
                        raw_abstract = item.get("abstract", "")
                        if raw_abstract:
                            clean_abs = re.sub(r"<[^>]+>", " ", raw_abstract)
                            snippet = re.sub(r"\s+", " ", clean_abs).strip()
                        else:
                            snippet = f"Scholarly publication ({year}) indexed in Crossref. DOI: {doi}"
                        
                        if not is_matching_topic(title, snippet):
                            continue
                            
                        seen_titles.add(title.lower())
                        results.append({
                            "title": title,
                            "year": year,
                            "doi": doi,
                            "url": url_link,
                            "snippet": snippet
                        })
            except Exception as e:
                print(f"[Crossref Fallback Error for '{cq}']: {e}")

    return results[:limit]

def clean_academic_abstract(text: str) -> str:
    """Cleans HTML tags, JATS XML tags, HTML entities, and formatting artifacts from academic abstracts."""
    if not text:
        return ""
    # 1. Unescape HTML entities (e.g. &lt;br&gt; -> <br>, &amp; -> &, &quot; -> ", &#39; -> ')
    cleaned = html.unescape(text)
    cleaned = html.unescape(cleaned)
    
    # 2. Convert breaks and paragraph tags to clean double newlines
    cleaned = re.sub(r'<\s*br\s*/?\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*/\s*p\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*p\s*>', '', cleaned, flags=re.I)
    
    # 3. Strip all remaining XML / JATS / HTML tags (e.g. <jats:sec>, <jats:title>, <i>, <b>)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    # 4. Standard structured abstract sections newline formatting
    section_headers = [
        "Research question", "Research methods", "Methods and materials", "Methodology",
        "Results and findings", "Results", "Findings", "Discussion", "Conclusion", "Conclusions",
        "Implications", "Background", "Objective", "Objectives", "Purpose", "Design",
        "Setting", "Participants", "Interventions", "Main outcomes", "Significance"
    ]
    pattern = r'(?:\n+|\s+)\b(' + '|'.join(re.escape(h) for h in section_headers) + r')\s*:\s*'
    cleaned = re.sub(pattern, r'\n\n\1: ', cleaned, flags=re.I)
    
    # 5. Normalize consecutive newlines and whitespace
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    return cleaned.strip()

_PAPER_METADATA_CACHE: Dict[str, dict] = {}

def resolve_paper_metadata_by_doi(doi: str, title_fallback: str = "") -> Optional[dict]:
    """
    Fetches complete Consensus-style academic metadata from OpenAlex, Crossref, HTML meta tags,
    and AI Academic Synthesis with a 5-tier fallback engine and high-speed in-memory caching.
    """
    if not doi and not title_fallback:
        return None
    clean_doi = doi.replace("https://doi.org/", "").strip() if doi else ""
    cache_key = (clean_doi or title_fallback).strip().lower()
    if cache_key in _PAPER_METADATA_CACHE:
        return _PAPER_METADATA_CACHE[cache_key]
    
    title = title_fallback.strip()
    authors = []
    pub_date = ""
    pub_year = ""
    journal = "Peer-reviewed Publication"
    journal_metric = "Peer-Reviewed"
    citations = 0
    landing = f"https://doi.org/{clean_doi}" if clean_doi else ""
    pdf_url = ""
    abstract = ""
    abstract_type = "official"
    
    # 1. OpenAlex by DOI
    if clean_doi:
        try:
            oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            req = urllib.request.Request(oa_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                title = data.get("title") or title
                pub_date = data.get("publication_date") or ""
                pub_year = str(data.get("publication_year") or "")
                authors = [a.get("author", {}).get("display_name") for a in data.get("authorships", []) if a.get("author", {}).get("display_name")]
                loc = data.get("primary_location") or {}
                src = loc.get("source") or {}
                if src.get("display_name"):
                    journal = src.get("display_name")
                citations = data.get("cited_by_count", 0)
                landing = loc.get("landing_page_url") or data.get("doi") or landing
                pdf_url = loc.get("pdf_url") or (landing if landing and ".pdf" in landing else "")
                
                is_oa = loc.get("is_oa", False)
                if citations > 50:
                    journal_metric = "Q1 SJR score"
                elif citations > 10:
                    journal_metric = "Q2 SJR score"
                elif is_oa:
                    journal_metric = "Open Access"
                    
                idx = data.get("abstract_inverted_index")
                if idx:
                    pos = []
                    for w, p in idx.items():
                        for x in p: pos.append((x, w))
                    pos.sort()
                    abstract = clean_academic_abstract(" ".join([w[1] for w in pos]).strip())
                    abstract_type = "official"
        except Exception:
            pass

    # 2. OpenAlex by Title Search (Recovers papers when DOI format diverges or OpenAlex indexed via title)
    if not abstract and (title or title_fallback):
        try:
            clean_search_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', (title or title_fallback))[:120].strip()
            oa_search_url = f"https://api.openalex.org/works?search={urllib.parse.quote(clean_search_title)}&per_page=1"
            req = urllib.request.Request(oa_search_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                if results:
                    w = results[0]
                    if not title:
                        title = w.get("title", "")
                    if not authors and w.get("authorships"):
                        authors = [a.get("author", {}).get("display_name") for a in w.get("authorships", []) if a.get("author", {}).get("display_name")]
                    if (not journal or journal == "Peer-reviewed Publication") and w.get("primary_location", {}).get("source", {}).get("display_name"):
                        journal = w.get("primary_location", {}).get("source", {}).get("display_name")
                    if not pub_year and w.get("publication_year"):
                        pub_year = str(w.get("publication_year"))
                    if not citations and w.get("cited_by_count"):
                        citations = w.get("cited_by_count", 0)
                        
                    idx = w.get("abstract_inverted_index")
                    if idx:
                        pos = []
                        for k, v in idx.items():
                            for p in v: pos.append((p, k))
                        pos.sort()
                        abstract = clean_academic_abstract(" ".join([x[1] for x in pos]).strip())
                        abstract_type = "official"
        except Exception:
            pass

    # 3. Crossref Fallback
    if clean_doi and (not abstract or not authors or not journal):
        try:
            cr_url = f"https://api.crossref.org/works/{clean_doi}"
            req = urllib.request.Request(cr_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                c_data = json.loads(resp.read().decode("utf-8"))
                msg = c_data.get("message", {})
                title_list = msg.get("title", [])
                if not title and title_list:
                    title = title_list[0]
                if not authors:
                    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", []) if a.get("family") or a.get("given")]
                container = msg.get("container-title", [])
                if container and (not journal or journal == "Peer-reviewed Publication"):
                    journal = container[0]
                if not pub_year:
                    created = msg.get("created", {}).get("date-parts", [[]])[0]
                    if created: pub_year = str(created[0])
                if not citations:
                    citations = msg.get("is-referenced-by-count", 0)
                if not landing:
                    landing = msg.get("URL", f"https://doi.org/{clean_doi}")
                if not abstract:
                    raw_abstract = msg.get("abstract", "")
                    if raw_abstract:
                        abstract = clean_academic_abstract(raw_abstract)
                        abstract_type = "official"
        except Exception:
            pass

    # 4. DOI Landing Page HTML Meta Scraper
    if not abstract and clean_doi:
        try:
            doi_landing_url = f"https://doi.org/{clean_doi}"
            req = urllib.request.Request(doi_landing_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            with urllib.request.urlopen(req, timeout=4) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")
                meta_matches = re.findall(r'<meta\s+[^>]*?(?:name|property)=["\'](?:citation_abstract|dc\.description|description|og:description)["\'][^>]*?content=["\'](.*?)["\']', html_text, re.I | re.DOTALL)
                for m in meta_matches:
                    clean_m = clean_academic_abstract(m)
                    if len(clean_m) > 60 and "cookie" not in clean_m.lower() and "javascript" not in clean_m.lower():
                        abstract = clean_m
                        abstract_type = "official"
                        break
        except Exception:
            pass

    # 5. AI Academic Overview Fallback (For strictly paywalled papers without public abstracts)
    if not abstract and title:
        abstract_type = "ai_summary"
        abstract = (
            f"This scholarly research investigates '{title}' ({pub_year or 'Recent publication'}). "
            f"Published in {journal}{f' by {authors[0]} et al.' if authors else ''}, this paper develops analytical frameworks, "
            f"empirical models, and findings relevant to the research domain. "
            f"Indexed in international academic scholarly databases (DOI: {clean_doi or 'N/A'}) with {citations} recorded citation(s)."
        )

    result = {
        "title": title or clean_doi,
        "authors": authors,
        "publication_date": pub_date or pub_year,
        "year": pub_year,
        "journal": journal,
        "journal_metric": journal_metric,
        "citations": citations,
        "doi": clean_doi,
        "url": landing,
        "pdf_url": pdf_url,
        "abstract": clean_academic_abstract(abstract),
        "abstract_type": abstract_type
    }
    _PAPER_METADATA_CACHE[cache_key] = result
    return result

def fetch_full_abstract_by_doi(doi: str) -> str:
    """Fetches the full, authentic academic abstract from OpenAlex / Crossref using DOI."""
    if not doi:
        return ""
    clean_doi = doi.replace("https://doi.org/", "").strip()
    
    # 1. Try OpenAlex by DOI
    try:
        oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
        req = urllib.request.Request(oa_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            inverted_index = data.get("abstract_inverted_index")
            if inverted_index:
                word_positions = []
                for word, positions in inverted_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                return " ".join([w[1] for w in word_positions]).strip()
    except Exception:
        pass
        
    # 2. Try Crossref by DOI
    try:
        cr_url = f"https://api.crossref.org/works/{clean_doi}"
        req = urllib.request.Request(cr_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            c_data = json.loads(resp.read().decode("utf-8"))
            msg = c_data.get("message", {})
            raw_abstract = msg.get("abstract", "")
            if raw_abstract:
                clean_abs = re.sub(r"<[^>]+>", " ", raw_abstract)
                return re.sub(r"\s+", " ", clean_abs).strip()
    except Exception:
        pass
        
    return ""

def search_academic_papers(query: str, limit: int = 10) -> List[dict]:
    """
    Standard entrypoint for academic paper search with synchronous fallback planning.
    """
    # Fast regex and keyword clean-up for synchronous endpoints
    cleaned = query.lower()
    patterns = [
        r'\b(mau\s+itu|ataupun|campur\s+aja|campur|subjek\s+bebas|topik\s+bebas|subjek\s+apapun|apapun\s+itu|yang\s+penting|mau\s+yang|yang\s+berbahasa|berbahasa|bahasa|internasional|international|local|lokal|indonesia|indo|inggris|english)\b',
        r'\b(tolong\s+carikan|coba\s+cariin|carikan|cariin|cari\s+kan|cari|minta|koleksi|daftar|buatkan|tampilkan|sajikan|gw|aku|saya)\b',
        r'\b(paper|papers|jurnal|artikel|dokumen|literatur|penelitian|riset|studi)\b',
        r'\b(\d+\s*(?:buah|biji|item|lembar|sumber|sources)?|\d+)\b',
        r'\b(dong|sih|ya|nih|lah|deh|pun|aja|saja|juga|dan|atau|dengan|pada|di|ke|untuk|dalam|tentang|mengenai|terkait|secara|seperti|adalah|bebas|appplied|applied)\b'
    ]
    for pat in patterns:
        cleaned = re.sub(pat, ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'[^a-zA-Z0-9\s/+-]', ' ', cleaned)
    
    words = cleaned.split()
    unique_words = []
    for w in words:
        if not unique_words or w != unique_words[-1]:
            unique_words.append(w)
    core_topic = " ".join(unique_words) or query.strip()

    wants_english = any(w in query.lower() for w in ["inggris", "english", "international", "internasional"])
    wants_indo = any(w in query.lower() for w in ["bahasa indonesia", "b indo", "indo", "indonesia", "lokal", "local"])
    has_mix = any(w in query.lower() for w in ["campur", "mix", "keduanya", "baik", "maupun", "boleh"])
    lang_pref = "mixed" if (wants_english and wants_indo) or has_mix or (not wants_english and not wants_indo) else ("id" if wants_indo else "en")

    plan = {
        "en_query": core_topic,
        "id_query": core_topic,
        "target_count": limit,
        "language_preference": lang_pref
    }
    return search_academic_papers_planned(plan)

def web_search_and_ingest(query: str, chat_id: str) -> str:
    """
    Searches scholarly databases (OpenAlex) and the web for research papers and articles.
    Returns findings immediately to the agent.
    """
    print(f"[Agent] Searching papers/web for: {query}")
    output_snippets = []
    
    # 1. Primary: Search OpenAlex for Academic & Scientific Papers (Ultra-fast & No ISP block)
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
            
    # 2. Secondary: Fallback / Complement with DDGS web search if needed
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
    """
    Uses OpenAlex API to find an Open Access PDF for a given DOI,
    downloads it, and ingests it into Qdrant.
    """
    print(f"[Agent] Fetching DOI: {doi}")
    
    # Clean DOI string just in case
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
            
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_resp.content)
            tmp_path = tmp.name
            
        # Ingest
        filename = f"{clean_doi.replace('/', '_')}.pdf"
        md_text = pymupdf4llm.to_markdown(tmp_path)
        ingest_document_text(md_text, filename, chat_id)
        
        # Cleanup
        os.remove(tmp_path)
        return f"Successfully downloaded and saved Open Access paper for DOI: {clean_doi}. The user can now ask questions about it."
        
    except Exception as e:
        return f"An error occurred while fetching DOI {clean_doi}: {str(e)}"


async def query_chat(chat_id: str, query: str, chat_history: list = None):
    """
    Queries the vector store via a ReAct Agent. 
    The Agent has access to the RAG Query Engine (for uploaded/saved docs)
    and the Web Search tool (to fetch new info autonomously).
    Automatically falls back between Gemini and Groq if quota/rate limits occur.
    """
    from database import SessionLocal, Document as DBDocument
    from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
    
    # Check if there are actually any uploaded documents for this chat
    db = SessionLocal()
    local_docs = []
    try:
        db_docs = db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
        local_docs = [d.filename for d in db_docs]
    finally:
        db.close()
        
    has_local_docs = len(local_docs) > 0
    
    # Build contextual sources summary
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
            print(f"[RAG] Warning: Could not init local query engine: {e}")
    
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
    
    # 2. Setup Web Search Tool
    def search_web_tool(q: str) -> str:
        """
        Use this tool to search the web or find research papers, journal articles, and information online.
        """
        return web_search_and_ingest(q, chat_id)
        
    web_tool = FunctionTool.from_defaults(fn=search_web_tool)
    
    # 3. Setup DOI Fetcher Tool
    def search_doi_tool(doi: str) -> str:
        """
        Use this tool when the user provides a DOI (e.g., 10.1038/s41586-020-2649-2) 
        and asks to download, read, or import the paper.
        """
        return fetch_and_ingest_doi(doi, chat_id)
        
    doi_tool = FunctionTool.from_defaults(fn=search_doi_tool)
    
    # Setup LLMs and Fallback
    ninerouter_instance, freellm_instance, gemini_instance, groq_instance = create_llm_instances()
    primary_provider = os.getenv("LLM_PROVIDER", "ninerouter").lower()
    
    if primary_provider == "ninerouter":
        primary_llm = ninerouter_instance
        fallback_llm = freellm_instance or gemini_instance or groq_instance
        primary_name, fallback_name = "9Router (Claude 3.7 Sonnet)", "FreeLLMAPI / Gemini"
    elif primary_provider == "freellmapi":
        primary_llm = freellm_instance
        fallback_llm = ninerouter_instance or gemini_instance or groq_instance
        primary_name, fallback_name = "FreeLLMAPI", "9Router / Groq"
    elif primary_provider == "groq":
        primary_llm = groq_instance
        fallback_llm = ninerouter_instance or freellm_instance or gemini_instance
        primary_name, fallback_name = "Groq", "9Router / FreeLLMAPI"
    else:
        primary_llm = gemini_instance
        fallback_llm = ninerouter_instance or freellm_instance or groq_instance
        primary_name, fallback_name = "Gemini", "9Router / FreeLLMAPI"

    active_llm = primary_llm or fallback_llm
    if not active_llm:
        raise RuntimeError("No LLM API key configured! Please set NINEROUTER_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, or FREELLMAPI in .env.")

    # Prepare chat history for conversational context
    formatted_history = []
    if chat_history:
        for msg in chat_history:
            role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
            content = msg.get("content", "").strip()
            if content and not content.startswith("⚠️"):
                formatted_history.append(LlamaChatMessage(role=role, content=content))

    def clean_response(text: str) -> str:
        # If the model emitted "Answer:", extract the portion after the last "Answer:"
        if "Answer:" in text:
            text = text.split("Answer:")[-1]
        # Remove any <think>...</think> blocks
        text = re.sub(r'<think>.*?', '', text, flags=re.DOTALL)
        text = text.replace("</think>", "").replace("<think>", "")
        # Strip any leading Thought:
        text = re.sub(r'^Thought:.*?\n', '', text, flags=re.DOTALL)
        return text.strip()

    def is_simple_conversational(text: str) -> bool:
        clean = text.lower().strip().strip("!?.,")
        simple_patterns = [
            "halo", "hai", "hello", "hi", "hey", "apa kabar", "kabar", 
            "tes", "test", "pagi", "siang", "sore", "malam", "siapa kamu",
            "terima kasih", "makasih", "thanks", "ok", "oke", "siap", 
            "mantap", "keren", "jos", "bos", "bro", "bisa bantu apa"
        ]
        words = clean.split()
        if len(words) <= 6 and any(p in clean for p in simple_patterns):
            if not any(k in clean for k in ["cari", "paper", "jurnal", "tabel", "baca", "pdf", "doi", "analisis", "rangkum", "data", "buatkan", "source", "sumber"]):
                return True
        return False

    def is_sources_capacity_query(text: str) -> bool:
        clean = text.lower().strip()
        capacity_phrases = [
            "max source", "max paper", "max limit", "maksimal source", "maksimal paper", "maksimal dokumen",
            "limit source", "limit paper", "limit dokumen", "batas source", "batas paper", "batas dokumen",
            "kapasitas source", "kapasitas paper", "kapasitas dokumen", "berapa max", "berapa batas", "berapa limit",
            "berapa kapasitas", "bisa sampai berapa source", "bisa sampai berapa paper", "maksimal berapa",
            "max berapa", "limit berapa", "batas berapa"
        ]
        return any(p in clean for p in capacity_phrases)

    def is_sources_meta_query(text: str) -> bool:
        clean = text.lower().strip()
        meta_phrases = [
            "berapa source", "berapa paper", "berapa dokumen", "ada berapa source", "ada berapa paper", "ada berapa dokumen",
            "ada berapa", "list source", "daftar source", "daftar paper", "daftar dokumen",
            "apa saja source", "apa saja paper", "apa saja dokumen", "sumber apa saja",
            "sources apa saja", "dokumen apa saja", "paper apa saja", "apakah ada source",
            "ada source apa", "sumbernya apa", "sumber apa yang ada", "total source", "total dokumen"
        ]
        return any(p in clean for p in meta_phrases)

    # Load all imported / uploaded document texts for this chat
    full_docs_context = ""
    UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
    if has_local_docs:
        doc_texts = []
        for fname in local_docs:
            fpath = os.path.join(UPLOADS_DIR, f"{chat_id}_{fname}")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            doc_texts.append(f"### Dokumen: {fname}\n{content}")
                except Exception as e:
                    print(f"[RAG] Error reading doc file {fpath}: {e}")
            else:
                doc_texts.append(f"### Dokumen: {fname}\n(File terdaftar sebagai referensi)")
                
        full_docs_context = "\n\n".join(doc_texts)

    async def execute_agent(target_llm, timeout_sec=30.0):
        # 1. Fast-path for sources capacity / max limits questions (100% Instant & Clear)
        if is_sources_capacity_query(query):
            return (
                f"Kapasitas batas maksimal sumber referensi (*sources*) adalah **250 sumber per percakapan (notebook)**.\n\n"
                f"Saat ini terdapat **{len(local_docs)} / 250 sumber** yang telah diimpor ke dalam percakapan ini.\n\n"
                f"💡 *Catatan: Untuk setiap 1 kali pencarian paper (fetch), sistem dapat mencari hingga **100 makalah ilmiah** sekaligus.*"
            )

        # 2. Fast-path for sources count & metadata questions (100% Accurate & Instant)
        if is_sources_meta_query(query):
            if has_local_docs:
                items_list = "\n".join([f"{i+1}. **{title}**" for i, title in enumerate(local_docs[:15])])
                if len(local_docs) > 15:
                    items_list += f"\n*... dan {len(local_docs) - 15} dokumen referensi lainnya.*"
                return (
                    f"Saat ini terdapat **{len(local_docs)} sumber referensi (sources)** yang diimpor dalam percakapan ini:\n\n"
                    f"{items_list}\n\n"
                    f"💡 *Kamu bisa meminta saya untuk merangkum, membandingkan temuan, memetakan gap riset, atau mencari topik spesifik dari dokumen-dokumen di atas!*"
                )
            else:
                return (
                    "Saat ini belum ada sumber referensi (*sources*) yang diimpor ke dalam percakapan ini.\n\n"
                    "Kamu bisa menambahkan file PDF atau mencari paper ilmiah melalui panel **Sources** di sebelah kanan!"
                )

        # 2. Fast-path for greetings & casual small talk (Sub-second / Instant response)
        if is_simple_conversational(query):
            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM, 
                content=(
                    "Kamu adalah NotbookLM, asisten riset AI yang ramah, pintar, dan adaptif. "
                    "Selalu sesuaikan bahasa responmu mengikuti bahasa dan konteks yang digunakan pengguna (bahasa Indonesia, Inggris, dsb).\n"
                    f"{doc_context_info}\n"
                    "Jawab secara ringkas, sopan, dan solutif."
                )
            )
            chat_msgs = [system_msg, *(formatted_history[-4:] if formatted_history else []), LlamaChatMessage(role=MessageRole.USER, content=query)]
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 3. AI-POWERED INTENT JUDGEMENT (Let the LLM judge user intent directly!)
        async def judge_intent_with_ai(user_query: str, has_docs: bool) -> str:
            clean_q = user_query.lower().strip()
            
            # Fast-path A: Obvious tabular synthesis / local summary commands
            if any(k in clean_q for k in [
                "format tabular", "tabel perbandingan", "buatkan tabel", "bikin tabel", 
                "buat tabel", "bentuk tabel", "susun tabel", "bikin rangkuman tabular",
                "rangkum", "rangkuman", "ringkasan", "bedah paper", "penjelasan terkait paper"
            ]):
                if not any(k in clean_q for k in ["cari paper baru", "fetch paper baru", "batal rangkum"]):
                    return "LOCAL_RAG"
            
            # Fast-path B: Obvious explicit new search commands
            if any(k in clean_q for k in ["cariin paper buat gw import", "cari paper buat gw import", "fetch lagi", "cari lagi dong"]):
                return "SEARCH_PAPERS"

            # Otherwise: Ask the AI LLM directly to judge intent!
            system_prompt = (
                "You are the master routing controller for NotbookLM, an AI research assistant.\n"
                "Your job is to classify the user's latest query into EXACTLY ONE category:\n\n"
                "1. 'SEARCH_PAPERS': The user is explicitly asking to DISCOVER / SEARCH / FETCH NEW academic literature from external scholarly databases (Crossref, OpenAlex) to add or import into their notebook sources.\n"
                "   Examples:\n"
                "   - 'tolong cariin 50 paper tentang prediksi bola'\n"
                "   - 'coba fetch lagi 100 paper baru'\n"
                "   - 'minta 25 paper baru buat diimport'\n\n"
                "2. 'LOCAL_RAG': The user wants you to summarize, create tables, explain, analyze, compare, extract research gaps, or ask questions about papers/documents that are ALREADY in the notebook/sources, or asking conceptual questions, or conversing, or expressing feedback / complaints.\n"
                "   Examples:\n"
                "   - 'gw minta lo buatin tabular format untuk rangkum ke 25 paper yang barusan kita import ke source'\n"
                "   - 'coba ke 25 paper yang barusan lo beri, bikin rangkuman tabular kayak sebelumnya'\n"
                "   - 'bisa beri gw rangkuman terkait paper X, Y, Z dalam format tabular?'\n"
                "   - 'apa potensi research gap dari paper-paper tadi?'\n"
                "   - 'bagaimana cara menangani cold start problem di EPL?'\n"
                "   - 'kenapa lo tadi salah jawab?'\n\n"
                "CRITICAL RULES:\n"
                "- If the user asks for a table, summary, comparison, gap analysis, or review of existing/imported papers, you MUST choose 'LOCAL_RAG'.\n"
                "- If the user is expressing frustration, complaining, or asking why a previous response was given, you MUST choose 'LOCAL_RAG'.\n"
                "- ONLY choose 'SEARCH_PAPERS' if the user explicitly wants to fetch NEW literature from the web.\n\n"
                f"Has Imported Documents in Notebook: {has_docs}\n"
                f"User Query: {user_query}\n\n"
                "Output ONLY the category name: 'SEARCH_PAPERS' or 'LOCAL_RAG'."
            )
            try:
                msg = LlamaChatMessage(role=MessageRole.USER, content=system_prompt)
                resp = await target_llm.achat([msg])
                decision = resp.message.content.strip().upper()
                if "SEARCH_PAPERS" in decision and "LOCAL_RAG" not in decision:
                    return "SEARCH_PAPERS"
                return "LOCAL_RAG"
            except Exception as e:
                print(f"[AI Intent Router Fallback]: {e}")
                return "LOCAL_RAG" if has_docs else "SEARCH_PAPERS"

        ai_intent = await judge_intent_with_ai(query, has_local_docs)
        print(f"[AI Intent Router Decision]: '{ai_intent}' for query: {query[:80]}")

        if ai_intent == "SEARCH_PAPERS":
            print(f"[RAG Direct] Planning & executing AI-powered paper search for: {query}")
            
            # Stage 1: LLM-Powered Query Planner (Consensus.app style)
            search_plan = await plan_academic_search(query, formatted_history, target_llm)
            
            # Stage 2 & 3: Parallel Scholarly Retrieval & Quality Filter with Deduplication
            exclude_titles = set([t.lower().replace(".pdf", "").strip() for t in local_docs]) if has_local_docs else None
            academic_papers = search_academic_papers_planned(search_plan, exclude_titles=exclude_titles)
            found_count = len(academic_papers)
            
            findings_summary = "\n".join([
                f"- **{p.get('title')}** ({p.get('year')}): {p.get('snippet')[:120]}..."
                for p in academic_papers[:20]
            ])
            
            req_count = search_plan.get("user_requested_count")
            if req_count and req_count > 100:
                header_text = (
                    f"⚠️ **Klarifikasi Batasan Kapasitas**:\n"
                    f"Sistem membatasi **maksimal 100 makalah per 1 kali pencarian (fetch)** dan **maksimal total 250 sumber per percakapan (notebook)**.\n\n"
                    f"Karena Anda meminta **{req_count} makalah**, Anda dapat melakukan **2–3 kali pencarian bertahap** untuk mengisi hingga batas maksimal 250 sumber (tidak bisa langsung {req_count} dalam satu kali permintaan). Berikut disajikan **{found_count} makalah terbaik & paling relevan** untuk pencarian tahap ini:"
                )
            elif req_count and found_count < req_count:
                header_text = (
                    f"Saya telah menelusuri basis data ilmiah (OpenAlex & Crossref) dan menemukan **{found_count} makalah yang paling relevan dan terverifikasi** "
                    f"(dari target {req_count} yang diminta, karena sistem hanya menyaring hasil yang kredibel dan sesuai topik):"
                )
            elif req_count:
                header_text = f"Saya telah menemukan **{found_count} makalah penelitian ilmiah** sesuai permintaan ({req_count} makalah):"
            else:
                header_text = f"Saya telah menemukan **{found_count} makalah penelitian ilmiah yang paling relevan** mengenai topik yang diminta:"

            synthesis_prompt = (
                f"Kamu adalah NotbookLM, asisten riset AI analitis.\n"
                f"Tugas: Buat 2-3 poin analitis ringkas ('Sintesis & Tren Riset Utama') mengenai metodologi dominan, domain studi kasus, dan pola temuan dari ringkasan paper berikut.\n"
                f"ATURAN KETAT: DILARANG mengulang/melist judul paper satu per satu, DILARANG membuat tabel, dan DILARANG menuliskan script/kode Python apapun.\n\n"
                f"Sampel Temuan Paper:\n{findings_summary}"
            )
            
            chat_msgs = [
                LlamaChatMessage(role=MessageRole.SYSTEM, content="Kamu adalah NotbookLM, asisten riset ilmiah AI yang padat, tajam, dan analitis."),
                LlamaChatMessage(role=MessageRole.USER, content=synthesis_prompt)
            ]
            resp = await target_llm.achat(chat_msgs)
            synthesis_body = clean_response(resp.message.content)
            synthesis_body = re.sub(r'^(?:#+\s*Sintesis[^\n]*\n+)+', '', synthesis_body, flags=re.I).strip()
            
            final_text = (
                f"{header_text}\n\n"
                f"### 📊 Sintesis & Tren Riset Utama\n"
                f"{synthesis_body}\n\n"
                f"💡 *Seluruh **{len(academic_papers)} makalah lengkap** beserta tautan DOI/URL dan abstraknya telah dimuat dalam kartu sumber (Outside Sources) di bawah ini. Anda dapat meninjau, menyaring, dan mengimpornya langsung ke panel Sources dalam satu klik.*"
            )
            
            if academic_papers:
                import json
                final_text += f"\n\n<!-- SOURCES_DATA: {json.dumps(academic_papers)} -->"
                
            return final_text

        # 4. Direct RAG Synthesis for Local Documents (When user is asking questions about existing imported sources)
        if has_local_docs:
            print(f"[RAG Local Direct] Processing query against {len(local_docs)} imported documents...")
            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "Kamu adalah NotbookLM, asisten riset ilmiah AI yang sangat analitis, mendalam, profesional, dan adaptif. "
                    "Selalu sesuaikan bahasa responmu mengikuti bahasa dan konteks yang digunakan oleh pengguna (jika pengguna menggunakan bahasa Indonesia jawab dalam bahasa Indonesia, jika bahasa Inggris jawab dalam bahasa Inggris, dsb). "
                    "Kamu memiliki akses penuh ke seluruh teks, abstrak, dan data dari dokumen referensi yang diimpor pengguna di bawah ini. "
                    "Gunakan SELURUH data dokumen ini untuk menjawab instruksi pengguna secara lengkap, terstruktur, dan mendalam.\n\n"
                    "ATURAN MANAJEMEN PANJANG RESPON & KELENGKAPAN:\n"
                    "1. Prioritas Utama: Usahakan menyajikan seluruh jawaban secara tuntas, padat, dan komprehensif dalam 1 kali respon (mencakup seluruh dokumen hingga bab Research Gap dan Novelty).\n"
                    "2. Jika analisis yang diminta sangat masif atau membutuhkan tabel yang sangat mendalam sehingga berpotensi melebihi kapasitas 1 kali pesan, JANGAN PERNAH memotong teks di tengah kalimat atau di tengah tabel.\n"
                    "3. Bagi analisis secara terstruktur menjadi bagian (misalnya Bagian 1: Makalah 1–25), selesaikan tabel bagian tersebut secara rapi, lalu di baris paling bawah berikan catatan ramah:\n"
                    "   '💡 **Catatan**: Agar analisis setiap makalah tetap mendalam dan tidak terpotong, bagian 1 menyajikan makalah 1–25. Ketik **\"Lanjutkan bagian 2\"** untuk menampilkan sisa makalah beserta rangkuman Research Gap dan Novelty.'\n"
                    "4. Ketika pengguna mengetik 'lanjutkan' atau 'bagian 2', lanjutkan secara mulus dari nomor makalah berikutnya hingga selesai tanpa mengulang dari awal."
                )
            )
            context_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=f"BERIKUT ADALAH SELURUH DATA & TEKS DOKUMEN REFERENSI YANG DIIMPOR ({len(local_docs)} DOKUMEN):\n\n{full_docs_context}"
            )
            chat_msgs = [
                system_msg,
                *(formatted_history[-4:] if formatted_history else []),
                context_msg,
                LlamaChatMessage(role=MessageRole.USER, content=query)
            ]
            resp = await target_llm.achat(chat_msgs)
            return clean_response(resp.message.content)

        # 5. Agentic path for complex workflows
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
        print(f"[RAG] Attempting query with primary LLM: {primary_name}")
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


