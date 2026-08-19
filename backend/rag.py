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

def normalize_title_str(t: str) -> str:
    """Normalizes a title by stripping extensions, punctuation, and collapsing whitespace."""
    if not t:
        return ""
    t = re.sub(r'\.pdf$', '', t, flags=re.I)
    t = re.sub(r'[^a-zA-Z0-9\s]', ' ', t).lower()
    return " ".join(t.split())

def get_existing_notebook_sources_signatures(chat_id: str) -> dict:
    """
    Scans all existing documents in this chat (from DB and disk) and returns
    comprehensive signatures (DOIs, full titles, filenames, token sets)
    to prevent recommending or importing duplicate papers.
    """
    from database import SessionLocal, Document as DBDocument
    db = SessionLocal()
    titles = set()
    dois = set()
    filenames = set()
    token_signatures = []

    try:
        db_docs = db.query(DBDocument).filter(DBDocument.chat_id == chat_id).all()
        for doc in db_docs:
            filenames.add(doc.filename)
            clean_fn = doc.filename.replace(".pdf", "").strip()
            titles.add(clean_fn)
    finally:
        db.close()

    # Also inspect actual file headers on disk for full titles & DOIs
    UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploads"))
    if os.path.exists(UPLOADS_DIR):
        for fn in filenames:
            fpath = os.path.join(UPLOADS_DIR, f"{chat_id}_{fn}")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        header = fp.readline().strip()
                        if header.startswith("# "):
                            full_t = re.sub(r'^\#\s*', '', header).strip()
                            full_t = re.sub(r'\s*\(\d{4}\)$', '', full_t).strip()
                            if full_t:
                                titles.add(full_t)
                        # Read next 2 lines for DOI
                        first_block = header + " " + fp.readline() + " " + fp.readline()
                        doi_m = re.search(r'(?:DOI:|\*\*DOI:\*\*|doi\.org/)\s*(10\.\d{4,9}/[^\s\)]+)', first_block, re.I)
                        if doi_m:
                            clean_d = doi_m.group(1).lower().strip()
                            dois.add(clean_d)
                except Exception:
                    pass

    for t in titles:
        norm = normalize_title_str(t)
        if norm:
            token_signatures.append((norm, set(norm.split())))

    return {
        "titles": titles,
        "dois": dois,
        "filenames": filenames,
        "token_signatures": token_signatures
    }

def is_paper_duplicate(
    candidate_title: str, 
    candidate_doi: str, 
    existing_signatures: dict
) -> bool:
    """
    Intelligently checks if a candidate paper is already present in the notebook sources
    via DOI, normalized title, prefix substring, or token overlap similarity.
    """
    if not existing_signatures:
        return False

    # 1. DOI Matching (100% Exact)
    if candidate_doi:
        c_doi = candidate_doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
        for ex_doi in existing_signatures.get("dois", set()):
            e_doi = ex_doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
            if c_doi and e_doi and c_doi == e_doi:
                return True

    # 2. Title Matching
    c_norm = normalize_title_str(candidate_title)
    if not c_norm:
        return False
    c_tokens = set(c_norm.split())

    for ex_norm, ex_tokens in existing_signatures.get("token_signatures", []):
        # Exact normalized match
        if c_norm == ex_norm:
            return True
        # Prefix / substring match for truncated titles (min 20 chars)
        if len(ex_norm) >= 20 and (c_norm.startswith(ex_norm) or ex_norm.startswith(c_norm)):
            return True
        # Token Jaccard / Overlap match
        intersection = c_tokens.intersection(ex_tokens)
        min_overlap = len(intersection) / min(len(c_tokens), len(ex_tokens)) if min(len(c_tokens), len(ex_tokens)) > 0 else 0
        if min_overlap >= 0.75 and len(intersection) >= 3:
            return True

    return False

def search_academic_papers_planned(
    plan: dict, 
    existing_signatures: dict = None,
    exclude_titles: set = None
) -> List[dict]:
    """
    Stage 2 & 3: Parallel Academic Retrieval & Quality Filtering (OpenAlex + Crossref)
    Executes multi-source scholarly search based on the AI Query Plan with adaptive counts and intelligent deduplication.
    """
    results = []
    seen_dois = set()
    seen_token_signatures = []

    # Initialize seen signatures with existing notebook sources
    if existing_signatures:
        seen_dois.update(existing_signatures.get("dois", set()))
        seen_token_signatures.extend(existing_signatures.get("token_signatures", []))
    
    if exclude_titles:
        for t in exclude_titles:
            norm = normalize_title_str(t)
            if norm:
                seen_token_signatures.append((norm, set(norm.split())))

    limit = plan.get("target_count", 15)
    en_query = plan.get("en_query", "")
    id_query = plan.get("id_query", "")
    lang_pref = plan.get("language_preference", "mixed")
    headers = {"User-Agent": "NotbookLM/1.0 (mailto:research@notbooklm.app)"}

    min_year = plan.get("min_year")
    min_citations = int(plan.get("min_citations") or 0)
    
    def is_candidate_duplicate(title: str, doi: str) -> bool:
        c_norm = normalize_title_str(title)
        if not c_norm:
            return True
        if doi:
            c_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
            if c_doi in seen_dois:
                return True
        c_tokens = set(c_norm.split())
        for ex_norm, ex_tokens in seen_token_signatures:
            if c_norm == ex_norm:
                return True
            if len(ex_norm) >= 20 and (c_norm.startswith(ex_norm) or ex_norm.startswith(c_norm)):
                return True
            intersection = c_tokens.intersection(ex_tokens)
            min_overlap = len(intersection) / min(len(c_tokens), len(ex_tokens)) if min(len(c_tokens), len(ex_tokens)) > 0 else 0
            if min_overlap >= 0.75 and len(intersection) >= 3:
                return True
        return False

    def mark_candidate_seen(title: str, doi: str):
        c_norm = normalize_title_str(title)
        if c_norm:
            seen_token_signatures.append((c_norm, set(c_norm.split())))
        if doi:
            c_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
            seen_dois.add(c_doi)

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
                        doi = work.get("doi", "")
                        if not title or not is_valid_academic_title(title):
                            continue
                        if is_candidate_duplicate(title, doi):
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
                            
                        mark_candidate_seen(title, doi)
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
                        doi = item.get("DOI", "")
                        if not title or not is_valid_academic_title(title):
                            continue
                        if is_candidate_duplicate(title, doi):
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
                            
                        url_link = item.get("URL", f"https://doi.org/{doi}" if doi else "")
                        
                        raw_abstract = item.get("abstract", "")
                        if raw_abstract:
                            clean_abs = re.sub(r"<[^>]+>", " ", raw_abstract)
                            snippet = re.sub(r"\s+", " ", clean_abs).strip()
                        else:
                            snippet = f"Scholarly publication ({year}) indexed in Crossref. DOI: {doi}"
                        
                        if not is_matching_topic(title, snippet):
                            continue
                            
                        mark_candidate_seen(title, doi)
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
    # 6. Strip redundant leading "Abstract" or "Overview" headers
    cleaned = re.sub(r'^\s*(?:abstract|abstract\s*&\s*overview|overview)\s*[:\-\.]?\s*', '', cleaned, flags=re.I)
    return cleaned.strip()

def is_valid_abstract_content(text: str) -> bool:
    """Validates whether a candidate string is an authentic academic abstract or just taxonomy/boilerplate."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) < 50:
        return False
        
    t_low = t.lower()
    # Taxonomy discipline labels or generic single lines
    invalid_exact = {
        "social and behavioral sciences", "social sciences", "behavioral sciences",
        "medicine and health", "medical sciences", "engineering and computer science",
        "computer science", "physical sciences", "humanities", "arts and humanities",
        "business and economics", "life sciences", "biological sciences", "decision sciences"
    }
    if t_low in invalid_exact:
        return False
        
    boilerplate_phrases = [
        "publikasi ilmiah", "terindeks crossref", "scholarly publication", 
        "indexed in international", "no abstract available", "abstract not available",
        "preview this article", "full text is available", "an abstract is not available"
    ]
    if any(b in t_low for b in boilerplate_phrases) and len(t) < 250:
        return False
        
    return True

def extract_abstract_from_html(html_text: str) -> str:
    """Extracts authentic academic abstract from HTML meta tags and semantic container elements across scholarly publishers."""
    if not html_text:
        return ""
        
    # 1. Meta tag extraction (Standard Highwire, Dublin Core, OpenGraph)
    meta_patterns = [
        r'<meta\s+[^>]*?(?:name|property)=["\'](?:citation_abstract|dc\.description)["\'][^>]*?content=["\'](.*?)["\']',
        r'<meta\s+[^>]*?content=["\'](.*?)["\'][^>]*?(?:name|property)=["\'](?:citation_abstract|dc\.description)["\']',
        r'<meta\s+[^>]*?(?:name|property)=["\'](?:og:description|description)["\'][^>]*?content=["\'](.*?)["\']'
    ]
    for pattern in meta_patterns:
        for m in re.findall(pattern, html_text, re.I | re.DOTALL):
            candidate = clean_academic_abstract(m)
            if is_valid_abstract_content(candidate) and "cookie" not in candidate.lower() and "javascript" not in candidate.lower():
                return candidate
                
    # 2. Semantic HTML container extraction (OJS, SportRxiv, PubMed, arXiv, ScienceDirect, Springer, Wiley)
    semantic_patterns = [
        r'<section[^>]*?class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        r'<div[^>]*?(?:class|id)=["\'][^"\']*\b(?:item\s+abstract|abstract-content|article-abstract|abstractText|abstract_content|abstract)\b[^"\']*["\'][^>]*>([\s\S]*?)</div>',
        r'<blockquote[^>]*?class=["\'][^"\']*\babstract\b[^"\']*["\'][^>]*>([\s\S]*?)</blockquote>',
        r'<section[^>]*?id=["\']abstract["\'][^>]*>([\s\S]*?)</section>',
        r'<div[^>]*?id=["\']abstract["\'][^>]*>([\s\S]*?)</div>'
    ]
    for pattern in semantic_patterns:
        for m in re.findall(pattern, html_text, re.I):
            candidate = clean_academic_abstract(m)
            if is_valid_abstract_content(candidate):
                return candidate
                
    return ""

def is_title_match(t1: str, t2: str) -> bool:
    """Checks if two academic paper titles match with high fuzzy similarity (>= 65%)."""
    if not t1 or not t2:
        return False
    c1 = re.sub(r'[^a-zA-Z0-9\s]', '', t1).lower().strip()
    c2 = re.sub(r'[^a-zA-Z0-9\s]', '', t2).lower().strip()
    if c1 == c2 or c1 in c2 or c2 in c1:
        return True
    import difflib
    ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
    return ratio >= 0.65

def is_ai_synthesized_overview(text: str) -> bool:
    """Detects if an abstract text is an AI-generated fallback summary template rather than authentic author text."""
    if not text:
        return False
    t_low = text.lower()
    return any(p in t_low for p in [
        "this scholarly publication investigates",
        "this scholarly article investigates",
        "the research presents methodology, analytical framework",
        "the research presents methodology, computational framework",
        "indexed in international academic databases",
        "indexed in international academic indexing services"
    ])

def audit_paper_metadata_with_ai(
    paper_title: str,
    raw_authors: List[str],
    raw_journal: str,
    raw_year: str,
    raw_doi: str,
    raw_citations: int,
    raw_abstract_or_html: str,
    is_oa: bool = False
) -> dict:
    """
    AI Research Auditor & Quality Judge:
    Uses Gemini / active LLM to audit candidate metadata, extract the true abstract,
    filter out garbage category names, and determine Scopus/SINTA quartile and quality_tier.
    """
    # 1. Primary AI Academic Knowledge Auditor (Evaluates any of the 45,000+ journals, conferences, SINTA, or preprints)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("models/gemini-flash-latest")
            
            prompt = f"""
You are an expert Senior Academic Research Indexer and Metadata Auditor (like Scopus, Web of Science, Consensus.app, and SINTA).

Audit and extract the most authentic, precise academic metadata for this scientific paper:
- Candidate Title: {paper_title}
- Candidate Authors: {raw_authors}
- Candidate Venue/Journal: {raw_journal}
- Publication Year: {raw_year}
- DOI: {raw_doi}
- Citations: {raw_citations}
- Raw Page Content / Snippet / Abstract text:
{raw_abstract_or_html[:2500]}

Rigorous Global Academic Indexing Rules:
1. TITLE: Exact official title.
2. AUTHORS: List of real author names (clean full names only).
3. YEAR: 4-digit publication year.
4. JOURNAL: Exact journal, conference proceedings, or preprint server name.
5. INDEXING & REPUTATION (journal_metric):
   - CONFERENCE PROCEEDINGS (Any IEEE, ACM, Springer, or international conference/symposium/workshop): MUST be labeled as Conference Proceedings (e.g. "IEEE Conference Proceedings", "ACM Conference Proceedings", "Conference Proceedings (Indexed)"). Conferences DO NOT have Q1/Q2/Q3/Q4.
   - PREPRINT REPOSITORIES (arXiv, SportRxiv, bioRxiv, medRxiv, SSRN, Research Square, OSF, RePEc): "Preprint (Non-Peer-Reviewed)".
   - INDONESIAN NATIONAL JOURNALS (SINTA): Identify if accredited (e.g. "SINTA 2 Accredited" or "SINTA Accredited").
   - INTERNATIONAL PEER-REVIEWED JOURNALS: Use your scholarly knowledge base of world journals. If it is a top-quartile journal in its domain, use "Scopus Q1 (SJR)". If high-tier, use "Scopus Q2 (SJR)". If mid-tier, use "Scopus Q3 (SJR)". If regular indexed or open access, use "Scopus Q4 / Indexed" or "DOAJ Open Access".
6. ABSTRACT:
   - Extract authentic original abstract paragraph written by the authors.
   - REJECT any subject taxonomy categories (like "Social and Behavioral Sciences", "Medicine", "Engineering"), cookie disclaimers, or license notices.
   - If genuine authentic abstract found: set abstract_type = "official".
   - If strictly paywalled or missing and you synthesize a summary: set abstract_type = "ai_summary".

Output ONLY valid JSON matching:
{{
  "title": "...",
  "authors": ["..."],
  "year": "...",
  "journal": "...",
  "journal_metric": "...",
  "abstract": "...",
  "abstract_type": "official" or "ai_summary"
}}
"""
            res = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 5}
            )
            if res.text:
                parsed = json.loads(res.text)
                if parsed.get("abstract"):
                    if is_ai_synthesized_overview(parsed.get("abstract")):
                        parsed["abstract_type"] = "ai_summary"
                    elif is_valid_abstract_content(parsed.get("abstract")):
                        if not parsed.get("abstract_type"):
                            parsed["abstract_type"] = "official"
                    return parsed
        except Exception:
            pass

    # 2. Deterministic Fallback if Offline / LLM Unavailable
    j_low = (raw_journal or "").lower()
    if any(p in j_low for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf", "repec", "research square", "preprint"]):
        metric = "Preprint (Non-Peer-Reviewed)"
    elif any(c in j_low for c in ["conference", "proceedings", "symposium", "workshop", "congress"]):
        metric = "Conference Proceedings (Indexed)"
    elif any(s in j_low for s in ["sinta", "garuda"]):
        metric = "SINTA Accredited"
    elif is_oa:
        metric = "Open Access Journal"
    else:
        metric = "Peer-Reviewed Publication"

    return {
        "title": paper_title,
        "authors": raw_authors,
        "year": raw_year,
        "journal": raw_journal or "Peer-reviewed Publication",
        "journal_metric": metric,
        "abstract": clean_academic_abstract(raw_abstract_or_html),
        "abstract_type": "official" if is_valid_abstract_content(raw_abstract_or_html) else "ai_summary"
    }

import journal_indexer

_PAPER_METADATA_CACHE: Dict[str, dict] = {}

def resolve_paper_metadata_by_doi(doi: str, title_fallback: str = "", fast_only: bool = False) -> Optional[dict]:
    """
    Fetches complete Consensus-style academic metadata from OpenAlex, Crossref, HTML meta/semantic tags,
    Semantic Scholar, SCImago Master DB, and AI Academic Auditor with a multi-tier fallback engine and caching.
    """
    if not doi and not title_fallback:
        return None
    clean_doi = doi.replace("https://doi.org/", "").strip() if doi else ""
    cache_key = (clean_doi or title_fallback).strip().lower()
    if cache_key in _PAPER_METADATA_CACHE:
        return _PAPER_METADATA_CACHE[cache_key]
    
    # Fast offline path for high-throughput batch operations (0.01ms)
    if fast_only:
        t_low = (title_fallback or "").lower()
        d_low = clean_doi.lower()
        metric = "Peer-Reviewed"
        journal_name = title_fallback

        if "10.1109/access" in d_low or "ieee access" in t_low:
            metric = "Scopus Q2 (SJR)"
            journal_name = "IEEE Access"
        elif any(c in t_low or c in d_low for c in ["proceedings", "conference", "symposium", "workshop", "10.1609/aaai", "10.1109/ic", "10.1145"]):
            metric = "Conference Proceedings (Indexed)"
        elif any(p in t_low or p in d_low for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf", "preprint"]):
            metric = "Preprint (Non-Peer-Reviewed)"
        elif any(s in t_low or s in d_low for s in ["sinta", "indonesia", "edumatic", "multilateral"]):
            metric = "SINTA Accredited"
        elif "procs" in d_low or "procedia" in t_low:
            metric = "Scopus Q2 (SJR)"
            journal_name = "Procedia Computer Science"
        elif "10.1007/s10994" in d_low or "machine learning (springer)" in t_low:
            metric = "Scopus Q1 (SJR)"
            journal_name = "Machine Learning (Springer)"
        elif "10.1249/mss" in d_low:
            metric = "Scopus Q1 (SJR)"
            journal_name = "Medicine & Science in Sports & Exercise"
        elif "10.1016/j.aci" in d_low:
            metric = "Scopus Q1 (SJR)"
            journal_name = "Applied Computing and Informatics"
        elif "10.1177/17479541" in d_low:
            metric = "Scopus Q2 (SJR)"
            journal_name = "International Journal of Sports Science & Coaching"
        elif "10.1186/s40634" in d_low:
            metric = "Scopus Q2 (SJR)"
            journal_name = "Journal of Experimental Orthopaedics"
        elif any(k in d_low for k in ["10.1016", "10.1007", "10.1038", "10.1111"]):
            metric = "Scopus Indexed Journal"

        fast_result = {
            "title": title_fallback,
            "authors": [],
            "publication_date": "",
            "year": "",
            "journal": journal_name,
            "journal_metric": metric,
            "quality_tier": 1 if "q1" in metric.lower() else (2 if "q2" in metric.lower() else 3),
            "citations": 0,
            "doi": clean_doi,
            "url": f"https://doi.org/{clean_doi}" if clean_doi else "",
            "pdf_url": "",
            "abstract": "",
            "abstract_type": "official"
        }
        _PAPER_METADATA_CACHE[cache_key] = fast_result
        return fast_result
    
    title = title_fallback.strip()
    authors = []
    pub_date = ""
    pub_year = ""
    journal = "Peer-reviewed Publication"
    journal_metric = "Peer-Reviewed"
    quality_tier = 4
    citations = 0
    landing = f"https://doi.org/{clean_doi}" if clean_doi else ""
    pdf_url = ""
    abstract = ""
    abstract_type = "official"
    is_oa = False
    issns = []
    src_type = "journal"
    host_org = ""
    
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
                if src.get("issn_l"):
                    issns.append(src.get("issn_l"))
                if src.get("issn"):
                    if isinstance(src.get("issn"), list): issns.extend(src.get("issn"))
                    else: issns.append(str(src.get("issn")))
                src_type = src.get("type") or data.get("type", "journal")
                host_org = src.get("host_organization_name", "")
                
                citations = data.get("cited_by_count", 0)
                landing = loc.get("landing_page_url") or data.get("doi") or landing
                pdf_url = loc.get("pdf_url") or (landing if landing and ".pdf" in landing else "")
                is_oa = loc.get("is_oa", False)
                    
                idx = data.get("abstract_inverted_index")
                if idx:
                    pos = []
                    for w, p in idx.items():
                        for x in p: pos.append((x, w))
                    pos.sort()
                    cand_abs = clean_academic_abstract(" ".join([w[1] for w in pos]).strip())
                    if is_valid_abstract_content(cand_abs):
                        abstract = cand_abs
                        abstract_type = "official"
        except Exception:
            pass

    # 2. OpenAlex by Title Search (ONLY if DOI lookup did not find authors/paper)
    if not authors and (title or title_fallback):
        try:
            clean_search_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', (title or title_fallback))[:120].strip()
            oa_search_url = f"https://api.openalex.org/works?search={urllib.parse.quote(clean_search_title)}&per_page=5"
            req = urllib.request.Request(oa_search_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for w in data.get("results", []):
                    cand_title = w.get("title", "")
                    if is_title_match(cand_title, (title or title_fallback)):
                        if not title:
                            title = cand_title
                        if not authors and w.get("authorships"):
                            authors = [a.get("author", {}).get("display_name") for a in w.get("authorships", []) if a.get("author", {}).get("display_name")]
                        if (not journal or journal == "Peer-reviewed Publication") and w.get("primary_location", {}).get("source", {}).get("display_name"):
                            journal = w.get("primary_location", {}).get("source", {}).get("display_name")
                        if not pub_year and w.get("publication_year"):
                            pub_year = str(w.get("publication_year"))
                        if not citations and w.get("cited_by_count"):
                            citations = w.get("cited_by_count", 0)
                        if not landing and w.get("doi"):
                            landing = w.get("doi")
                            
                        idx = w.get("abstract_inverted_index")
                        if idx and not abstract:
                            pos = []
                            for k, v in idx.items():
                                for p in v: pos.append((p, k))
                            pos.sort()
                            cand_abs = clean_academic_abstract(" ".join([x[1] for x in pos]).strip())
                            if is_valid_abstract_content(cand_abs):
                                abstract = cand_abs
                                abstract_type = "official"
                        break
        except Exception:
            pass

    # 3. Crossref Fallback (Only if missing abstract, authors, or journal)
    if clean_doi and (not authors or not journal or journal == "Peer-reviewed Publication" or not abstract):
        try:
            cr_url = f"https://api.crossref.org/works/{clean_doi}"
            req = urllib.request.Request(cr_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
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
                        cand_abs = clean_academic_abstract(raw_abstract)
                        if is_valid_abstract_content(cand_abs):
                            abstract = cand_abs
                            abstract_type = "official"
        except Exception:
            pass

    # 4. Semantic Scholar API Fallback (Only if still missing abstract)
    if clean_doi and not abstract:
        try:
            s2_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}?fields=abstract,authors,title,venue,year,citationCount,openAccessPdf"
            req = urllib.request.Request(s2_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                s2_data = json.loads(resp.read().decode("utf-8"))
                if not authors and s2_data.get("authors"):
                    authors = [a.get("name") for a in s2_data.get("authors", []) if a.get("name")]
                if not pub_year and s2_data.get("year"):
                    pub_year = str(s2_data.get("year"))
                if not citations and s2_data.get("citationCount"):
                    citations = s2_data.get("citationCount", 0)
                if not pdf_url and s2_data.get("openAccessPdf", {}).get("url"):
                    pdf_url = s2_data.get("openAccessPdf", {}).get("url")
                s2_abs = s2_data.get("abstract")
                if s2_abs and not abstract:
                    cand_abs = clean_academic_abstract(s2_abs)
                    if is_valid_abstract_content(cand_abs):
                        abstract = cand_abs
                        abstract_type = "official"
        except Exception:
            pass

    # 5. DOI Landing Page HTML Meta & Semantic Element Scraper (Only if still missing abstract)
    raw_html_content = ""
    if clean_doi and (not abstract or not authors or not journal or journal == "Peer-reviewed Publication"):
        try:
            doi_landing_url = f"https://doi.org/{clean_doi}"
            req = urllib.request.Request(doi_landing_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            with urllib.request.urlopen(req, timeout=3) as resp:
                raw_html_content = resp.read().decode("utf-8", errors="ignore")
                if not abstract:
                    extracted = extract_abstract_from_html(raw_html_content)
                    if extracted and is_valid_abstract_content(extracted):
                        abstract = extracted
                        abstract_type = "official"
                if not authors:
                    author_tags = re.findall(r'<meta\s+[^>]*?name=["\'](?:citation_author|dc\.creator)["\'][^>]*?content=["\'](.*?)["\']', raw_html_content, re.I)
                    if author_tags:
                        authors = [a.strip() for a in author_tags if a.strip()]
                if not journal or journal == "Peer-reviewed Publication":
                    j_match = re.search(r'<meta\s+[^>]*?name=["\'](?:citation_journal_title|citation_conference_title|dc\.source)["\'][^>]*?content=["\'](.*?)["\']', raw_html_content, re.I)
                    if j_match:
                        journal = j_match.group(1).strip()
        except Exception:
            pass

    # 6. Empirical SCImago / Scopus Database Indexing Resolution
    empirical_idx = journal_indexer.lookup_journal_index(issns, journal, venue_type=src_type, publisher=host_org)

    # 7. AI Academic Research Auditor (Judge & Indexation Resolver)
    audit_input_content = abstract or raw_html_content or ""
    audited = audit_paper_metadata_with_ai(
        paper_title=title or clean_doi,
        raw_authors=authors,
        raw_journal=journal,
        raw_year=pub_year,
        raw_doi=clean_doi,
        raw_citations=citations,
        raw_abstract_or_html=audit_input_content,
        is_oa=is_oa
    )

    final_title = audited.get("title") or title or clean_doi
    final_authors = audited.get("authors") or authors
    final_year = audited.get("year") or pub_year
    final_journal = audited.get("journal") or journal
    
    # Prioritize empirical SCImago / Scopus registry match, fallback to AI Auditor
    if empirical_idx and empirical_idx.get("journal_metric") and empirical_idx.get("journal_metric") != "Peer-Reviewed Journal":
        final_metric = empirical_idx["journal_metric"]
        final_tier = empirical_idx.get("quality_tier", 4)
    else:
        final_metric = audited.get("journal_metric") or "Peer-Reviewed"
        final_tier = audited.get("quality_tier", 4)

    final_abstract = clean_academic_abstract(audited.get("abstract") or abstract)
    if is_ai_synthesized_overview(final_abstract):
        final_abstract_type = "ai_summary"
    else:
        final_abstract_type = audited.get("abstract_type") or abstract_type or "official"

    result = {
        "title": final_title,
        "authors": final_authors,
        "publication_date": pub_date or final_year,
        "year": final_year,
        "journal": final_journal,
        "journal_metric": final_metric,
        "quality_tier": final_tier,
        "citations": citations,
        "doi": clean_doi,
        "url": landing,
        "pdf_url": pdf_url,
        "abstract": final_abstract,
        "abstract_type": final_abstract_type
    }
    _PAPER_METADATA_CACHE[cache_key] = result
    return result

def fetch_full_abstract_by_doi(doi: str) -> str:
    """Fetches the full, authentic academic abstract from OpenAlex / Crossref / Semantic Scholar / Landing HTML using DOI."""
    if not doi:
        return ""
    clean_doi = doi.replace("https://doi.org/", "").strip()
    
    # 1. Try OpenAlex by DOI
    try:
        oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
        req = urllib.request.Request(oa_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            inverted_index = data.get("abstract_inverted_index")
            if inverted_index:
                word_positions = []
                for word, positions in inverted_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                cand = " ".join([w[1] for w in word_positions]).strip()
                if is_valid_abstract_content(cand):
                    return cand
    except Exception:
        pass
        
    # 2. Try Crossref by DOI
    try:
        cr_url = f"https://api.crossref.org/works/{clean_doi}"
        req = urllib.request.Request(cr_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            c_data = json.loads(resp.read().decode("utf-8"))
            msg = c_data.get("message", {})
            raw_abstract = msg.get("abstract", "")
            if raw_abstract:
                clean_abs = clean_academic_abstract(raw_abstract)
                if is_valid_abstract_content(clean_abs):
                    return clean_abs
    except Exception:
        pass

    # 3. Try Semantic Scholar
    try:
        s2_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}?fields=abstract"
        req = urllib.request.Request(s2_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:dev@notbooklm.local)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            s2_data = json.loads(resp.read().decode("utf-8"))
            s2_abs = s2_data.get("abstract")
            if s2_abs:
                cand = clean_academic_abstract(s2_abs)
                if is_valid_abstract_content(cand):
                    return cand
    except Exception:
        pass

    # 4. Try DOI Landing Page HTML Scraper
    try:
        doi_landing_url = f"https://doi.org/{clean_doi}"
        req = urllib.request.Request(doi_landing_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
            extracted = extract_abstract_from_html(html_text)
            if extracted and is_valid_abstract_content(extracted):
                return extracted
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


async def query_chat(
    chat_id: str, 
    query: str, 
    chat_history: list = None,
    status_callback: Optional[Callable[[str], Any]] = None
):
    """
    Queries the vector store via a ReAct Agent or Direct RAG Synthesis with real-time status callbacks.
    The Agent has access to the RAG Query Engine (for uploaded/saved docs)
    and the Web Search tool (to fetch new info autonomously).
    Automatically falls back between Gemini and Groq if quota/rate limits occur.
    """
    from database import SessionLocal, Document as DBDocument
    from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
    import inspect
    
    async def report_status(text: str):
        if status_callback:
            try:
                res = status_callback(text)
                if inspect.isawaitable(res):
                    await res
            except Exception:
                pass

    await report_status("Analyzing query intent & research parameters...")
    
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
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
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

    # Load all imported / uploaded document texts for this chat with verified journal & quartile metrics
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
                            # Extract DOI to resolve verified ground-truth metadata & quartile
                            doi_m = re.search(r'(?:DOI:|\*\*DOI:\*\*|doi\.org/)\s*(10\.\d{4,9}/[^\s\)]+)', content[:500], re.I)
                            doi_str = doi_m.group(1).lower().strip() if doi_m else ""
                            clean_fn = fname.replace(".pdf", "").strip()
                            meta = resolve_paper_metadata_by_doi(doi_str, title_fallback=clean_fn, fast_only=True)
                            metric_tag = meta.get("journal_metric", "Peer-Reviewed") if meta else "Peer-Reviewed"
                            journal_name = meta.get("journal", "") if meta else ""
                            
                            meta_header = f"**Jurnal/Venue:** {journal_name}  \n**Status Indeksasi:** {metric_tag}" if journal_name else f"**Status Indeksasi:** {metric_tag}"
                            doc_texts.append(f"### Dokumen: {fname}\n{meta_header}\n\n{content}")
                except Exception as e:
                    print(f"[RAG] Error reading doc file {fpath}: {e}")
            else:
                doc_texts.append(f"### Dokumen: {fname}\n(File terdaftar sebagai referensi)")
                
        full_docs_context = "\n\n".join(doc_texts)

    async def execute_agent(target_llm, timeout_sec=30.0):
        # 1. Fast-path for sources capacity / max limits questions (100% Instant & Clear)
        if is_sources_capacity_query(query):
            await report_status("Inspecting notebook source limits...")
            return (
                f"Kapasitas batas maksimal sumber referensi (*sources*) adalah **250 sumber per percakapan (notebook)**.\n\n"
                f"Saat ini terdapat **{len(local_docs)} / 250 sumber** yang telah diimpor ke dalam percakapan ini.\n\n"
                f"💡 *Catatan: Untuk setiap 1 kali pencarian paper (fetch), sistem dapat mencari hingga **100 makalah ilmiah** sekaligus.*"
            )

        # 2. Fast-path for sources count & metadata questions (100% Accurate & Instant)
        if is_sources_meta_query(query):
            await report_status("Checking imported source list...")
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
            await report_status("Responding...")
            greetings = [
                f"Halo! Ada yang bisa saya bantu terkait riset atau analisis dokumen ilmiah hari ini?",
                f"Hai! Saya siap membantu Anda menganalisis dokumen referensi, mencari paper baru, atau merangkum literatur ilmiah.",
                f"Halo! Silakan beri tahu saya topik riset yang sedang Anda kaji atau dokumen yang ingin dianalisis."
            ]
            import random
            return random.choice(greetings)

        # 3. Dynamic Intent Classification
        async def judge_intent_with_ai(user_query: str, has_docs: bool) -> str:
            clean_q = user_query.lower()
            
            # Fast-path A: Obvious local synthesis / summary queries
            if any(p in clean_q for p in [
                "format tabular", "tabel perbandingan", "buatkan tabel", "bikin tabel", 
                "buat tabel", "bentuk tabel", "susun tabel", "bikin rangkuman tabular",
                "rangkum", "rangkuman", "ringkasan", "bedah paper", "penjelasan terkait paper",
                "metode apa", "temuan apa", "kesimpulan apa", "analisis dokumen", "fokus"
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
                "2. 'LOCAL_RAG': The user wants you to summarize, create tables, explain, analyze, compare, extract research gaps, or ask questions about papers/documents that are ALREADY in the notebook/sources, or asking conceptual questions, or conversing, or expressing feedback / complaints.\n\n"
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

        await report_status("Determining optimal research workflow...")
        ai_intent = await judge_intent_with_ai(query, has_local_docs)
        print(f"[AI Intent Router Decision]: '{ai_intent}' for query: {query[:80]}")

        if ai_intent == "SEARCH_PAPERS":
            print(f"[RAG Direct] Planning & executing AI-powered paper search for: {query}")
            await report_status("Formulating optimal academic search queries...")
            
            # Stage 1: LLM-Powered Query Planner (Consensus.app style)
            search_plan = await plan_academic_search(query, formatted_history, target_llm)
            terms_preview = ", ".join(search_plan.get("search_queries", [])[:2])
            await report_status(f"Querying OpenAlex & Crossref databases for: '{terms_preview or 'scientific literature'}'...")
            
            # Stage 2 & 3: Parallel Scholarly Retrieval & Quality Filter with Smart Multi-Attribute Deduplication
            existing_sigs = get_existing_notebook_sources_signatures(chat_id)
            academic_papers = search_academic_papers_planned(search_plan, existing_signatures=existing_sigs)
            found_count = len(academic_papers)
            
            await report_status(f"Auditing Scopus & SINTA metrics across {found_count} discovered papers...")
            
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

            await report_status("Synthesizing key research findings & trends...")
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
            
            # Check if user query has a dedicated focused document tag
            focus_doc_match = re.search(r'\[(?:Focused Document|Fokus Dokumen|Fokus Sumber):\s*"(.*?)"\]', query, re.I)
            target_focus_title = focus_doc_match.group(1).strip() if focus_doc_match else None
            
            focus_instruction = ""
            if target_focus_title:
                await report_status(f"Focusing analysis on '{target_focus_title[:45]}...'")
                focus_instruction = (
                    f"\n\n🎯 PERHATIAN KHUSUS (DEDICATED SOURCE FOCUS):\n"
                    f"Pengguna secara spesifik menanyakan pertanyaan ini KHUSUS terkait dokumen referensi: \"{target_focus_title}\".\n"
                    f"Fokuskan analisis, metodologi, temuan, dan jawabanmu 100% secara tuntas dan mendalam berdasarkan dokumen tersebut!"
                )
            else:
                await report_status(f"Reading & analyzing methodologies across {len(local_docs)} imported documents...")

            system_msg = LlamaChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    "Kamu adalah NotbookLM, asisten riset ilmiah AI yang sangat analitis, mendalam, profesional, dan adaptif. "
                    "Selalu sesuaikan bahasa responmu mengikuti bahasa dan konteks yang digunakan oleh pengguna (jika pengguna menggunakan bahasa Indonesia jawab dalam bahasa Indonesia, jika bahasa Inggris jawab dalam bahasa Inggris, dsb). "
                    "Kamu memiliki akses penuh ke seluruh teks, abstrak, dan data dari dokumen referensi yang diimpor pengguna di bawah ini. "
                    "Gunakan SELURUH data dokumen ini untuk menjawab instruksi pengguna secara lengkap, terstruktur, dan mendalam."
                    f"{focus_instruction}\n\n"
                    "ATURAN STATUS INDEKSASI & KUARTIL JURNAL (SANGAT KETAT):\n"
                    "- Selalu gunakan data status indeksasi resmi yang tertera pada header dokumen (**Status Indeksasi** dan **Jurnal/Venue**).\n"
                    "- JANGAN PERNAH melabeli 'Conference Proceedings' sebagai Jurnal Q1/Q2/Q3/Q4 (karena kuartil Q Scopus/SJR hanya berlaku untuk jurnal berkala, bukan prosiding konferensi).\n"
                    "- Jika suatu jurnal terdaftar sebagai 'Scopus Q2 (SJR)', sebutlah secara akurat sebagai Q2. Jangan mengubahnya menjadi Q1 berdasarkan ingatan/asumsi sendiri.\n\n"
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


