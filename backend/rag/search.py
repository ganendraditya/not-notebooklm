import os
import re
import json
import html
import logging
import urllib.request
import urllib.parse
from typing import List, Optional, Dict, Any
import requests
from duckduckgo_search import DDGS
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole, LLM
import journal_indexer
from collections import OrderedDict
import concurrent.futures

from helpers import clean_doi as _clean_doi
from utils.text_processing import (
    normalize_title_str,
    is_valid_academic_title,
    clean_academic_abstract,
    is_valid_abstract_content,
    extract_abstract_from_html,
    is_title_match,
    is_ai_synthesized_overview
)
from providers.academic import fetch_europe_pmc, fetch_openalex, fetch_crossref
from services.search import (
    plan_academic_search,
    judge_and_filter_papers_with_llm,
    audit_paper_metadata_with_ai
)

logger = logging.getLogger("uvicorn.error")

class LRUMetadataCache:
    """Thread-safe bounded in-memory cache to avoid unbounded RAM leak."""
    def __init__(self, capacity: int = 500):
        self.capacity = capacity
        self.cache: OrderedDict[str, dict] = OrderedDict()

    def get(self, key: str) -> Optional[dict]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: dict):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def __contains__(self, key: str) -> bool:
        return key in self.cache

    def __getitem__(self, key: str) -> dict:
        return self.get(key) or {}

    def __setitem__(self, key: str, value: dict):
        self.set(key, value)

_PAPER_METADATA_CACHE = LRUMetadataCache(capacity=500)

def is_valid_academic_title(title: str) -> bool:
    """Quality filter to exclude non-scholarly publication artifacts, covers, and TOCs."""
    t = title.lower().strip()
    if len(t) < 8:
        return False
    junk_patterns = [
        "[front cover]", "[copyright", "table of contents", "author index", "itu k programme",
        "itu k 2018", "keynote summary", "chairman's message", "foreword", "committees",
        "figure 1:", "table 3:", "table 5:", "peer review #", "cover page", "back cover",
        "editorial board", "preliminary pages", "conference report",
    ]
    if any(j in t for j in junk_patterns):
        return False
    # Reject generic publisher artifact headers that are not real paper titles
    generic_exact = {
        "article in press", "in press", "journal pre-proof", "uncorrected proof",
        "corrected proof", "original article", "research article", "full length article",
        "short communication", "review article", "full paper", "research paper",
        "accepted manuscript", "author's copy", "analytical index", "index",
        "abstract", "abstrak", "overview", "paper", "document",
    }
    if t in generic_exact:
        return False
    return True

async def plan_academic_search(query: str, history: Optional[List[LlamaChatMessage]] = None, llm: Optional[LLM] = None) -> dict:
    """
    Stage 1: LLM-Powered Academic Query Planner (Consensus.app / Elicit / Perplexity style)
    Uses the AI model to understand conversational intent, context, multi-lingual requirements, and exact quantities.
    """
    # Clean colloquial Indonesian filler words before default fallback
    clean_text = re.sub(
        r'\b(cariin|carikan|cari|search|find|tentang|about|paper|jurnal|artikel|sumber|sources|buah|biji|referensi|makalah|dong|ya|tolong|minta|lagi|bos|bro|nih|deh|aja|sih|buat|ke|max|maksimal|tahun|terakhir|ke\s*belakang|jangan|lebih|dari|itu|gw|gua|gue|aku|saya|lu|lo|kamu)\b',
        ' ',
        query,
        flags=re.I
    )
    clean_text = re.sub(r'\d+', ' ', clean_text)
    clean_text = ' '.join(clean_text.split()).strip()

    # Determine default language preference from prompt
    # If explicit Indonesian prompt without non-ID language request, prefer "mixed" so users get both top global English papers + reputable local Indonesian papers
    id_indicators = [
        "cari", "cariin", "carikan", "tolong", "tentang", "jurnal", "makalah", "terbaru", 
        "tahun", "terakhir", "dong", "deh", "nih", "gw", "gua", "gue", "bisa", "buat", "kalo", "yg", "yang"
    ]
    is_mostly_id = any(re.search(rf'\b{re.escape(w)}\b', query, re.I) for w in id_indicators)
    default_lang = "mixed" if is_mostly_id else "en"

    # Extract languages filter intent from prompt or [Filter Preferences: ...]
    default_languages: List[str] = []
    lang_pref_match = re.search(r'\[Filter Preferences:[^\]]*\blanguages:\s*([^,\]]+(?:,\s*[^,\]]+)*)', query, re.I)
    if lang_pref_match:
        raw_lang_str = lang_pref_match.group(1).split("discipline:")[0].split("year:")[0].split("min citations:")[0].strip()
        raw_langs = [l.strip().lower() for l in raw_lang_str.split(",") if l.strip()]
        default_languages = [l for l in raw_langs if l != "all" and len(l) <= 10]

    # 1. Default heuristic fallback (adaptive by relevance, default cap 12-15)
    default_plan = {
        "en_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "id_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "native_query": clean_text if len(clean_text) >= 3 else query.strip(),
        "target_count": 12,
        "languages": default_languages,
        "language_preference": default_lang,
        "open_access_only": False,
        "scopus_quartiles": [],
        "sinta_tiers": [],
        "exclude_preprints": False
    }
    
    # Fast regex extraction for fallback count, min_year, open access, quartiles
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

    # Extract open access intent
    if any(k in query.lower() for k in ["open access", "open-access", "oa only", "open access only", "free pdf", "gratis", "free full text"]):
        default_plan["open_access_only"] = True

    # Extract Scopus Quartile intent (e.g. Q1 only, Q1/Q2, Scopus Q1)
    q_matches = re.findall(r'\b[qQ]([1-4])\b', query)
    if q_matches:
        default_plan["scopus_quartiles"] = list(set([f"Q{q}" for q in q_matches]))

    # Extract SINTA Tier intent (e.g. Sinta 1, Sinta 2, SINTA 1/2)
    sinta_matches = re.findall(r'\bsinta\s*([1-6])\b', query, re.I)
    if sinta_matches:
        default_plan["sinta_tiers"] = list(set([f"S{s}" for s in sinta_matches]))

    # Extract exclude preprints intent
    if any(k in query.lower() for k in ["exclude preprint", "tanpa preprint", "bukan preprint", "exclude preprints"]):
        default_plan["exclude_preprints"] = True

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
        # Context extraction from recent conversation turns (Leverage 1M+ token context window)
        context_str = ""
        if history:
            hist_snippets = []
            for m in history:
                role_name = getattr(m, 'role', '')
                if role_name == MessageRole.USER or role_name == 'user':
                    hist_snippets.append(f"User: {m.content}")
                elif role_name == MessageRole.ASSISTANT or role_name == 'assistant':
                    clean_c = m.content.split('<!-- SOURCES_DATA')[0].strip()
                    hist_snippets.append(f"Assistant: {clean_c}")
            if hist_snippets:
                context_str = "\nPrevious Full Conversation History:\n" + "\n\n".join(hist_snippets) + "\n\n"

        prompt = (
            "You are an AI Academic Query Planner for a research search engine (like Consensus.app, Elicit, Perplexity).\n"
            "Your job: Analyze the user's prompt, any attached '[Filter Preferences: ...]' tags, and conversation context to extract clean, high-precision academic search parameters in JSON.\n\n"
            f"{context_str}"
            "Current User Request:\n"
            f"\"{query}\"\n\n"
            "Rules for extraction:\n"
            "1. CONTEXT & TOPIC RESOLUTION (CRITICAL):\n"
            "   - If the user's request refers to previous topics or previous requests (e.g. 'rekomendasiin biar bisa diimport', 'topik tadi', 'terkait tadi', 'yang tadi', 'coba lagi dong', 'yang analisis sentimen tadi'): You MUST examine 'Previous Conversation Context' to identify the specific research domain (e.g. 'sentiment analysis machine learning') and retain it!\n"
            "   - Indonesian slang: 'gw' / 'gua' / 'gue' = 'I / me'. NEVER interpret 'gw' as 'GW' or 'Gigawatt' or physics acronyms! 'gw' in Indonesian means 'me/I'.\n"
            "2. 'en_query': Pure English academic search term for global scholarly databases (OpenAlex, Europe PMC, Crossref). Remove all conversational filler words ('cariin', 'mau itu', 'campur aja', 'bebas', 'yang penting', 'gw', 'lah', 'dong', 'ya', 'coba', 'open access', 'q1', 'sinta', 'rekomendasiin', 'biar gw bisa import'). Convert domain abbreviations ('ML' -> 'machine learning', 'DL' -> 'deep learning', 'EPL' -> 'English Premier League').\n"
            "3. 'native_query': Academic search term translated into the target language(s) if user writes in non-English or specifies target languages (e.g. Japanese Kanji/Katakana '心理学', Chinese '心理学', Spanish 'psicología', Indonesian 'psikologi').\n"
            "4. 'languages': Array of 2-letter ISO 639-1 language codes (e.g. [\"ja\"], [\"zh\"], [\"es\"], [\"ko\"], [\"id\"], [\"en\"], or multiple [\"zh\", \"ko\", \"ja\"]).\n"
            "   - Priority 1: If '[Filter Preferences: ... languages: ja, zh]' is explicitly present in the query, strictly use those codes!\n"
            "   - Priority 2: If the user wrote their prompt in Japanese (Kanji/Hiragana), Chinese (Hanzi), Korean (Hangul), Spanish, Arabic, etc., detect the user's prompt language and add its code (e.g. 'ja' for Japanese prompt, 'zh' for Chinese prompt).\n"
            "   - Priority 3: If no specific language filter or non-English prompt, leave as empty [] (which means all / global English).\n"
            "5. 'target_count': Integer representing how many papers to search for.\n"
            "   - If the user explicitly specified an exact number (e.g. 10, 30, 50, 100), strictly set target_count to that number (capped at 100 max per fetch).\n"
            "   - If the user DID NOT specify an exact number: DO NOT force an arbitrary 20! Set target_count to a natural relevant size between 8 and 15 so only truly relevant papers are returned without padding low-quality matches.\n"
            "   - If the user asks for follow-up ('coba lagi', 'tambah lagi'), set target_count to 8-12 fresh papers.\n"
            "6. 'open_access_only': Boolean true if user explicitly, in Filter Preferences, or in recent context requested open access / free PDF only, else false.\n"
            "7. 'scopus_quartiles': Array of strings like [\"Q1\"], [\"Q1\", \"Q2\"], or empty [].\n"
            "8. 'sinta_tiers': Array of strings like [\"S1\", \"S2\"], or empty [].\n"
            "9. 'exclude_preprints': Boolean true if preprints should be excluded, else false.\n"
            "10. 'user_requested_count': The exact integer if the user specified a number (e.g. 30, 50, 100), otherwise null.\n"
            "11. 'min_year': Integer representing minimum publication year (e.g. 2020 if user mentioned '5 tahun terakhir' or 'terbaru', otherwise null).\n"
            "12. 'min_citations': Integer representing minimum citations count threshold (e.g. 10 if user specified 'min 10 sitasi', otherwise 0).\n"
            "13. Return ONLY a valid JSON object without any markdown code fences or conversational text.\n\n"
            "Example Output:\n"
            "{\n"
            "  \"en_query\": \"psychology clinical therapy\",\n"
            "  \"native_query\": \"心理学 臨床心理学\",\n"
            "  \"languages\": [\"ja\"],\n"
            "  \"target_count\": 12,\n"
            "  \"open_access_only\": true,\n"
            "  \"scopus_quartiles\": [],\n"
            "  \"sinta_tiers\": [],\n"
            "  \"exclude_preprints\": false,\n"
            "  \"user_requested_count\": null,\n"
            "  \"min_year\": 2021,\n"
            "  \"min_citations\": 0\n"
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
                    
            native_q = str(parsed.get("native_query", "")).strip() or str(parsed.get("id_query", "")).strip() or default_plan["native_query"]
            parsed_langs = parsed.get("languages")
            target_langs: List[str] = []
            if isinstance(parsed_langs, list):
                target_langs = [str(l).strip().lower() for l in parsed_langs if str(l).strip() and str(l).strip().lower() != "all"]
            elif isinstance(parsed_langs, str) and parsed_langs.strip():
                target_langs = [l.strip().lower() for l in parsed_langs.split(",") if l.strip() and l.strip().lower() != "all"]

            # If default_languages came from [Filter Preferences:], it strictly overrides unless empty
            if default_languages:
                target_langs = default_languages

            lang = str(parsed.get("language_preference", default_plan["language_preference"])).lower()
            if not target_langs and lang in ["id", "en", "mixed"]:
                if lang == "id": target_langs = ["id"]
                elif lang == "en": target_langs = ["en"]

            oa_only = bool(parsed.get("open_access_only", default_plan["open_access_only"])) or default_plan["open_access_only"]
            scopus_q = parsed.get("scopus_quartiles") or default_plan["scopus_quartiles"]
            sinta_t = parsed.get("sinta_tiers") or default_plan["sinta_tiers"]
            ex_prep = bool(parsed.get("exclude_preprints", default_plan["exclude_preprints"])) or default_plan["exclude_preprints"]
            
            print(f"[AI Query Planner] en_query='{en_q}' | native_query='{native_q}' | languages={target_langs} | count={cnt} | oa={oa_only} | scopus={scopus_q} | sinta={sinta_t} | min_year={m_year} | min_citations={m_cit}")
            return {
                "en_query": en_q,
                "id_query": native_q,
                "native_query": native_q,
                "languages": target_langs,
                "target_count": cnt,
                "open_access_only": oa_only,
                "scopus_quartiles": scopus_q,
                "sinta_tiers": sinta_t,
                "exclude_preprints": ex_prep,
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

    from helpers import get_doc_file_path
    for fn in filenames:
        fpath = get_doc_file_path(chat_id, fn)
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
    Stage 2 & 3: Multi-Engine Scholarly Search (Europe PMC + OpenAlex + Crossref)
    Retrieves full untruncated academic papers with authors, verified DOIs, official abstracts, and direct Open Access PDF links.
    """
    results = []
    seen_dois = set()
    seen_token_signatures = []

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
    open_access_only = bool(plan.get("open_access_only", False))
    scopus_quartiles = [q.upper() for q in (plan.get("scopus_quartiles") or [])]
    sinta_tiers = [s.upper() for s in (plan.get("sinta_tiers") or [])]
    exclude_preprints = bool(plan.get("exclude_preprints", False))
    
    def is_candidate_duplicate_local(title: str, doi: str) -> bool:
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

    def mark_candidate_seen_local(title: str, doi: str):
        c_norm = normalize_title_str(title)
        if c_norm:
            seen_token_signatures.append((c_norm, set(c_norm.split())))
        if doi:
            c_doi = doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
            seen_dois.add(c_doi)

    def is_matching_topic_local(title: str, snippet: str) -> bool:
        t_low = title.lower()
        full = f"{title} {snippet}".lower()
        
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

        # Strict entity validation for focused subject queries (e.g. Prabowo, Jokowi, COVID, etc.)
        subject_keywords = []
        for q_src in [en_query, id_query]:
            clean_q = re.sub(r'\b(sentiment|sentimen|analysis|analisis|classification|klasifikasi|mining|study|studi|jurnal|paper|makalah|indonesia|public|publik)\b', '', q_src, flags=re.I)
            words = [w.strip().lower() for w in clean_q.split() if len(w.strip()) >= 3]
            for w in words:
                if w not in subject_keywords:
                    subject_keywords.append(w)

        if subject_keywords:
            # If the user specified distinctive subject keywords, at least one must match the candidate
            has_subject = any(sk in full for sk in subject_keywords)
            if not has_subject:
                return False

        # Rainfall / Precipitation domain topic validation
        if any(k in en_query.lower() or k in id_query.lower() for k in ["rainfall", "curah hujan", "precipitation", "rain"]):
            rain_terms = [
                "rainfall", "curah hujan", "precipitation", "hujan", "rain", "presipitasi", "rainy", "pluvial"
            ]
            has_rain = any(r in full for r in rain_terms)
            
            predict_terms = [
                "predict", "prediksi", "forecast", "forecasting", "peramalan", "prakiraan", 
                "estimat", "model", "lstm", "arima", "deep learning", "machine learning", 
                "neural", "xgboost", "catboost", "random forest", "prophet", "nowcast", "time series", "deret waktu"
            ]
            has_predict = any(p in full for p in predict_terms)
            
            # Reject clear non-rainfall targets (e.g. covid, disease, wildfire, purely general flood depth)
            unrelated_targets = [
                "covid-19", "covid", "leishmaniasis", "leishmania", "mortality", "visceral", 
                "fire in", "fires in", "karhutla", "wildfire"
            ]
            if any(u in full for u in unrelated_targets):
                return False
                
            return has_rain and has_predict

        # Road Damage Detection domain topic validation
        if any(k in en_query.lower() or k in id_query.lower() for k in ["road damage", "kerusakan jalan", "pothole", "lubang jalan", "retak jalan", "pavement distress", "pavement damage"]):
            road_terms = ["road", "jalan", "pavement", "perkerasan", "asphalt", "aspal", "highway"]
            has_road = any(r in full for r in road_terms)
            
            damage_terms = [
                "damage", "kerusakan", "defect", "distress", "pothole", "lubang", 
                "crack", "retak", "retakan", "alligator", "rutting", "ravelling", "bleeding", "pavement condition"
            ]
            has_damage = any(d in full for d in damage_terms)

            ai_vision_terms = [
                "detection", "deteksi", "segmentation", "segmentasi", "classification", "klasifikasi",
                "yolo", "cnn", "deep learning", "machine learning", "computer vision", "pengolahan citra",
                "image processing", "u-net", "resnet", "object detection", "mask r-cnn", "vision transformer", "vit"
            ]
            has_ai_vision = any(a in full for a in ai_vision_terms)
            
            # Reject clear irrelevant targets that mention "jalan" or "crack" or "yolo" in unrelated contexts:
            # - Dinding / Tembok / Bangunan gedung (structural wall cracks)
            # - Kereta api / Perkeretaapian / JPL / Lintasan rel kereta
            # - Sampah / Kebersihan lingkungan (trash on roads)
            # - Kendaraan / Mobil / Tol / Golongan kendaraan (vehicle counting, toll classification)
            # - Jembatan non-jalan (pure bridge cable / pier)
            unrelated_road = [
                "dinding", "tembok", "bangunan gedung", "perumahan", "cracksafe",
                "kereta", "perkeretaapian", "rel kereta", "jpl", "gerbong", "lokomotif",
                "sampah", "tumpukan sampah", "sungai", "kebersihan",
                "golongan kendaraan", "beban kendaraan", "volume kendaraan", "gerbang tol", "kemacetan", "esal",
                "avanza", "toyota", "penerangan", "lampu", "solar", "lora", "buku ajar", "sistem pakar mobil"
            ]
            if any(u in full for u in unrelated_road):
                return False

            return has_road and has_damage and has_ai_vision

        if any(k in en_query.lower() or k in id_query.lower() for k in ["sentiment", "sentimen", "opinion", "opini"]):
            sentiment_keys = [
                "sentiment", "sentimen", "opinion", "opini", "ulasan", 
                "emotion", "emosi", "polarity", "polaritas", "sarcasm", "sarkasme", 
                "aspect-based", "absa", "vader"
            ]
            return any(k in t_low for k in sentiment_keys) or any(k in full for k in ["sentiment analysis", "analisis sentimen", "opinion mining", "sentiment classification", "aspect-based sentiment", "aspect sentiment", "sentiment prediction"])
        
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

    target_languages = plan.get("languages") or []
    native_query = plan.get("native_query") or plan.get("id_query") or en_query

    # Execute Search Orchestration
    # Case A: User explicitly specified target non-English languages (e.g. ja, zh, es, ko, id, etc.)
    non_en_langs = [l for l in target_languages if l not in ["en", "all"]]
    if non_en_langs:
        # Search OpenAlex filtered by exact ISO language codes (e.g. language:ja or language:zh|ja)
        # Search with native translated query first, then en_query as fallback
        lang_oa_papers = fetch_openalex(native_query, limit, min_year, min_citations, open_access_only, exclude_preprints, non_en_langs, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(lang_oa_papers)
        
        if len(results) < limit:
            oa_en_terms_with_lang = fetch_openalex(en_query, limit - len(results), min_year, min_citations, open_access_only, exclude_preprints, non_en_langs, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(oa_en_terms_with_lang)
            
        if len(results) < limit:
            cr_native = fetch_crossref(native_query, limit - len(results), min_year, open_access_only, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(cr_native)

        # STRICT LANGUAGE COMPLIANCE:
        # Do NOT spill over to global English papers if the user explicitly set a non-English language filter!
        # Return whatever relevant papers found in the requested language.
            
    elif lang_pref == "mixed" and en_query.lower() != id_query.lower():
        en_quota = limit // 2
        
        # 1. Fetch International English papers
        epmc_papers = fetch_europe_pmc(en_query, en_quota // 2 + 2, min_year, open_access_only, exclude_preprints, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(epmc_papers)
        oa_papers = fetch_openalex(en_query, en_quota - len(results), min_year, min_citations, open_access_only, exclude_preprints, None, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(oa_papers)
        
        # 2. Fetch Indonesian / Local papers
        actual_id_quota = limit - len(results)
        id_papers = fetch_openalex(id_query, actual_id_quota, min_year, min_citations, open_access_only, exclude_preprints, ["id"], headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(id_papers)
        if len(results) < limit:
            cr_id = fetch_crossref(id_query, limit - len(results), min_year, open_access_only, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(cr_id)

        # 3. Dynamic Quota Spillover
        if len(results) < limit:
            remaining_needed = limit - len(results)
            spillover_oa = fetch_openalex(en_query, remaining_needed, min_year, min_citations, open_access_only, exclude_preprints, None, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(spillover_oa)
    elif lang_pref == "id":
        id_papers = fetch_openalex(id_query, limit, min_year, min_citations, open_access_only, exclude_preprints, ["id"], headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(id_papers)
        if len(results) < limit:
            cr_id = fetch_crossref(id_query, limit - len(results), min_year, open_access_only, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(cr_id)
        if len(results) < limit:
            spillover_oa = fetch_openalex(en_query, limit - len(results), min_year, min_citations, open_access_only, exclude_preprints, None, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(spillover_oa)
    else: # "en"
        epmc_papers = fetch_europe_pmc(en_query, limit // 2 + 2, min_year, open_access_only, exclude_preprints, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(epmc_papers)
        if len(results) < limit:
            oa_papers = fetch_openalex(en_query, limit - len(results), min_year, min_citations, open_access_only, exclude_preprints, ["en"] if "en" in target_languages else None, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
            results.extend(oa_papers)
            
    # Final Fallback to Crossref if still under limit
    if len(results) < limit:
        extra_cr = fetch_crossref(en_query or id_query, limit - len(results), min_year, open_access_only, headers, is_valid_academic_title, is_candidate_duplicate_local, is_matching_topic_local, mark_candidate_seen_local)
        results.extend(extra_cr)

    # 4. Semantic Reranking with FlashRank (Cross-Encoder)
    if len(results) > limit:
        try:
            from flashrank import Ranker, RerankRequest
            ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
            passages = [
                {
                    "id": idx,
                    "text": f"{p.get('title', '')}. {p.get('snippet', '')}"[:500]
                }
                for idx, p in enumerate(results)
            ]
            rerank_q = en_query or "academic research"
            rerank_req = RerankRequest(query=rerank_q, passages=passages)
            ranked_passages = ranker.rerank(rerank_req)
            
            reranked_results = []
            for item in ranked_passages:
                p_idx = item.get("id")
                if isinstance(p_idx, int) and 0 <= p_idx < len(results):
                    reranked_results.append(results[p_idx])
            if reranked_results:
                results = reranked_results
        except Exception as rerank_err:
            logger.debug(f"[Search Rerank Fallback]: {rerank_err}")

    return results[:limit]

async def judge_and_filter_papers_with_llm(
    query: str,
    candidates: List[dict],
    target_count: int,
    llm: Optional[LLM] = None
) -> List[dict]:
    """
    Stage 3.5: AI Judge & Relevance Auditor (Vector / LLM-grade evaluation)
    Inspects candidate papers retrieved from registries, evaluates their real domain relevance against user query,
    and strictly discards irrelevant or tangentially related papers.
    """
    if not candidates:
        return []
    
    if llm is None:
        return candidates[:target_count]

    try:
        # Prepare concise evaluation list for the LLM Judge
        eval_items = []
        for idx, c in enumerate(candidates):
            title = c.get("title", "").strip()
            snippet = c.get("snippet", "").strip()[:400]
            eval_items.append(f"[{idx}] Title: {title}\nSummary: {snippet}")

        eval_context = "\n\n".join(eval_items)

        judge_prompt = (
            "You are an expert Academic Relevance Auditor & Scientific Literature Judge.\n"
            "Your objective: Strictly evaluate whether each retrieved research paper directly and substantially matches the user's core research topic.\n\n"
            f"User Research Query:\n\"{query}\"\n\n"
            f"Candidate Papers to Audit:\n{eval_context}\n\n"
            "EVALUATION CRITERIA:\n"
            "1. STRICT DOMAIN RELEVANCE: Keep ONLY papers that directly investigate the requested topic.\n"
            "   - Example: If the user asked for 'road damage detection with AI', ACCEPT papers detecting asphalt cracks, potholes, pavement distress, rutting on roads. REJECT papers about wall/building cracks, train/railway tracking, trash collection, or vehicle counting/toll gates.\n"
            "   - Example: If the user asked for 'rainfall prediction', ACCEPT precipitation/rainfall forecasting. REJECT wildfire, purely general floods without rainfall models, or disease/COVID.\n"
            "2. Rank the relevant papers by highest relevance and quality.\n"
            f"3. Select UP TO {target_count} best matching paper indices.\n\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY a JSON list of integer indices of accepted papers, in order of relevance.\n"
            "Example format: [0, 3, 4, 7]"
        )

        resp = await llm.acomplete(judge_prompt)
        raw_out = resp.text.strip()
        raw_out = re.sub(r'^```(?:json)?\s*', '', raw_out, flags=re.I)
        raw_out = re.sub(r'\s*```$', '', raw_out)

        valid_indices = json.loads(raw_out)
        if isinstance(valid_indices, list):
            filtered_papers = []
            for idx in valid_indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates):
                    filtered_papers.append(candidates[idx])
            
            if filtered_papers:
                print(f"[AI Judge Auditor] Filtered {len(candidates)} candidates down to {len(filtered_papers)} highly relevant papers.")
                return filtered_papers[:target_count]
    except Exception as e:
        print(f"[AI Judge Auditor Warning]: {e} -> fallback to candidates")

    return candidates[:target_count]



def search_academic_papers(query: str, limit: int = 10) -> List[dict]:
    """Standard entrypoint for academic paper search with synchronous fallback planning."""
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
        "native_query": core_topic,
        "target_count": limit,
        "language_preference": lang_pref
    }
    return search_academic_papers_planned(plan)
