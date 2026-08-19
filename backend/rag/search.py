import os
import re
import json
import html
import logging
import urllib.request
import urllib.parse
from typing import List, Optional, Dict, Any
import requests
from ddgs import DDGS
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole, LLM
import journal_indexer

logger = logging.getLogger("uvicorn.error")

_PAPER_METADATA_CACHE: Dict[str, dict] = {}

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
    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    if os.path.exists(uploads_dir):
        for fn in filenames:
            fpath = os.path.join(uploads_dir, f"{chat_id}_{fn}")
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

    # 1. Europe PMC Search
    def fetch_europe_pmc(term: str, target_count: int):
        fetched = []
        if not term.strip(): return fetched
        try:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={urllib.parse.quote(term.strip())}&format=json&pageSize={min(target_count + 10, 50)}&resultType=core"
            resp = requests.get(url, timeout=6)
            if resp.status_code == 200:
                for p in resp.json().get("resultList", {}).get("result", []):
                    if len(fetched) >= target_count: break
                    title = p.get("title", "").strip().rstrip(".")
                    doi = p.get("doi", "")
                    if not title or not is_valid_academic_title(title) or is_candidate_duplicate(title, doi): continue
                    
                    year = str(p.get("pubYear", ""))
                    if min_year and year.isdigit() and int(year) < min_year: continue
                    
                    author_str = p.get("authorString", "")
                    authors = [a.strip() for a in author_str.split(",") if a.strip()]
                    venue = p.get("journalTitle", "")
                    abstract = p.get("abstractText", "")
                    ft_urls = p.get("fullTextUrlList", {}).get("fullTextUrl", [])
                    pdf_urls = [f.get("url") for f in ft_urls if f.get("documentStyle") == "pdf" and f.get("url")]
                    pdf_url = pdf_urls[0] if pdf_urls else ""
                    
                    snippet = abstract if abstract else f"Scholarly research publication in {venue} ({year}). DOI: {doi}"
                    if not is_matching_topic(title, snippet): continue
                    
                    mark_candidate_seen(title, doi)
                    fetched.append({
                        "title": title,
                        "year": str(year),
                        "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                        "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/MED/{p.get('id')}",
                        "snippet": snippet,
                        "authors": authors,
                        "venue": venue,
                        "pdf_url": pdf_url
                    })
        except Exception as e:
            print(f"[Europe PMC Search Error]: {e}")
        return fetched

    # 2. OpenAlex Search
    def fetch_openalex(term: str, target_count: int):
        fetched = []
        if not term.strip(): return fetched
        page = 1
        while len(fetched) < target_count and page <= 5:
            try:
                per_page = min(max(target_count - len(fetched) + 15, 25), 100)
                url = "https://api.openalex.org/works"
                params = {"search": term.strip(), "per_page": per_page, "page": page}
                filter_parts = []
                if min_year: filter_parts.append(f"publication_year:{min_year}-2026")
                if min_citations > 0: filter_parts.append(f"cited_by_count:>{min_citations - 1}")
                if filter_parts: params["filter"] = ",".join(filter_parts)
                    
                resp = requests.get(url, params=params, headers=headers, timeout=6)
                if resp.status_code == 200:
                    results_list = resp.json().get("results", [])
                    if not results_list: break
                    for work in results_list:
                        if len(fetched) >= target_count: break
                        title = work.get("title", "").strip()
                        doi = work.get("doi", "")
                        if not title or not is_valid_academic_title(title) or is_candidate_duplicate(title, doi): continue
                            
                        year = str(work.get("publication_year", "N/A"))
                        if min_year and year.isdigit() and int(year) < min_year: continue
                                
                        citations_count = work.get("cited_by_count", 0)
                        if min_citations > 0 and citations_count < min_citations: continue
                                
                        landing_url = work.get("primary_location", {}).get("landing_page_url") or doi or f"https://openalex.org/{work.get('id')}"
                        oa_pdf = work.get("best_oa_location", {}).get("pdf_url") or work.get("primary_location", {}).get("pdf_url") or ""
                        venue = work.get("primary_location", {}).get("source", {}).get("display_name") if work.get("primary_location", {}).get("source") else ""
                        authors = [a.get("author", {}).get("display_name", "") for a in work.get("authorships", [])]
                        
                        abstract = ""
                        inv = work.get("abstract_inverted_index")
                        if inv:
                            wp = []
                            for word, pos in inv.items():
                                for p in pos: wp.append((p, word))
                            wp.sort()
                            abstract = " ".join([w[1] for w in wp]).strip()
                            
                        snippet = abstract or f"Scholarly publication in {venue} ({year}). DOI: {doi}"
                        if not is_matching_topic(title, snippet): continue
                            
                        mark_candidate_seen(title, doi)
                        fetched.append({
                            "title": title,
                            "year": str(year),
                            "doi": doi,
                            "url": landing_url,
                            "snippet": snippet,
                            "authors": authors,
                            "venue": venue,
                            "pdf_url": oa_pdf
                        })
                    page += 1
                else:
                    break
            except Exception as e:
                print(f"[OpenAlex Search Error]: {e}")
                break
        return fetched

    # 3. Crossref Search
    def fetch_crossref(term: str, target_count: int):
        fetched = []
        if not term.strip(): return fetched
        try:
            url = "https://api.crossref.org/works"
            params = {"query": term.strip(), "rows": min(target_count + 20, 60)}
            if min_year: params["filter"] = f"from-pub-date:{min_year}-01-01"
            resp = requests.get(url, params=params, headers=headers, timeout=6)
            if resp.status_code == 200:
                for item in resp.json().get("message", {}).get("items", []):
                    if len(fetched) >= target_count: break
                    title_list = item.get("title", [])
                    if not title_list: continue
                    title = title_list[0].strip()
                    doi = item.get("DOI", "")
                    if not title or not is_valid_academic_title(title) or is_candidate_duplicate(title, doi): continue
                        
                    year = "N/A"
                    created = item.get("created", {}).get("date-parts", [[]])[0]
                    if created: year = str(created[0])
                    if min_year and year.isdigit() and int(year) < min_year: continue
                        
                    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", [])]
                    venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
                    raw_abs = item.get("abstract", "")
                    clean_abs = re.sub(r"<[^>]+>", " ", raw_abs) if raw_abs else ""
                    snippet = re.sub(r"\s+", " ", clean_abs).strip() if clean_abs else f"Scholarly contribution published in {venue} ({year}). DOI: {doi}"
                    
                    if not is_matching_topic(title, snippet): continue
                        
                    mark_candidate_seen(title, doi)
                    fetched.append({
                        "title": title,
                        "year": str(year),
                        "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                        "url": f"https://doi.org/{doi}" if doi else item.get("URL", ""),
                        "snippet": snippet,
                        "authors": authors,
                        "venue": venue,
                        "pdf_url": ""
                    })
        except Exception as e:
            print(f"[Crossref Search Error]: {e}")
        return fetched

    # Execute Search Orchestration
    if lang_pref == "mixed" and en_query.lower() != id_query.lower():
        en_quota = limit // 2
        
        # 1. Fetch International English papers
        epmc_papers = fetch_europe_pmc(en_query, en_quota // 2 + 2)
        results.extend(epmc_papers)
        oa_papers = fetch_openalex(en_query, en_quota - len(results))
        results.extend(oa_papers)
        
        # 2. Fetch Indonesian / Local papers
        actual_id_quota = limit - len(results)
        id_papers = fetch_openalex(id_query, actual_id_quota)
        results.extend(id_papers)
        if len(results) < limit:
            cr_id = fetch_crossref(id_query, limit - len(results))
            results.extend(cr_id)
    elif lang_pref == "id":
        id_papers = fetch_openalex(id_query, limit)
        results.extend(id_papers)
        if len(results) < limit:
            cr_id = fetch_crossref(id_query, limit - len(results))
            results.extend(cr_id)
    else: # "en"
        epmc_papers = fetch_europe_pmc(en_query, limit // 2 + 2)
        results.extend(epmc_papers)
        if len(results) < limit:
            oa_papers = fetch_openalex(en_query, limit - len(results))
            results.extend(oa_papers)
            
    # Fallback to Crossref if still under limit
    if len(results) < limit:
        extra_cr = fetch_crossref(en_query or id_query, limit - len(results))
        results.extend(extra_cr)

    return results[:limit]

def clean_academic_abstract(text: str) -> str:
    """Cleans HTML tags, JATS XML tags, HTML entities, and formatting artifacts from academic abstracts."""
    if not text:
        return ""
    cleaned = html.unescape(text)
    cleaned = html.unescape(cleaned)
    
    cleaned = re.sub(r'<\s*br\s*/?\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*/\s*p\s*>', '\n\n', cleaned, flags=re.I)
    cleaned = re.sub(r'<\s*p\s*>', '', cleaned, flags=re.I)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    cleaned = re.sub(r'\*\*_([^_*]+)_\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
    cleaned = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', cleaned)
    cleaned = re.sub(r'(?<!\w)_([^_\s][^_]*)_(?!\w)', r'\1', cleaned)
    cleaned = re.sub(r'\*{2,}', '', cleaned)
    cleaned = re.sub(r'(?<!\w)_+(?!\w)', '', cleaned)
    cleaned = re.sub(r'^#{1,6}\s*', '', cleaned, flags=re.MULTILINE)
    
    section_headers = [
        "Research question", "Research methods", "Methods and materials", "Methodology",
        "Results and findings", "Results", "Findings", "Discussion", "Conclusion", "Conclusions",
        "Implications", "Background", "Objective", "Objectives", "Purpose", "Design",
        "Setting", "Participants", "Interventions", "Main outcomes", "Significance"
    ]
    pattern = r'(?:\n+|\s+)\b(' + '|'.join(re.escape(h) for h in section_headers) + r')\s*:\s*'
    cleaned = re.sub(pattern, r'\n\n\1: ', cleaned, flags=re.I)
    
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
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
        except Exception as e:
            logger.debug(f"[AI Auditor] Audit failed for '{paper_title}': {e}")

    # Deterministic Fallback if Offline / LLM Unavailable
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

def resolve_paper_metadata_by_doi(doi: str = "", title_fallback: str = "", paper_title: str = "", fast_only: bool = False) -> Optional[dict]:
    """
    Fetches complete Consensus-style academic metadata from OpenAlex, Crossref, HTML meta/semantic tags,
    Semantic Scholar, SCImago Master DB, and AI Academic Auditor with a multi-tier fallback engine and caching.
    """
    if paper_title and not title_fallback:
        title_fallback = paper_title
    if not doi and not title_fallback:
        return None
    clean_doi = doi.replace("https://doi.org/", "").strip() if doi else ""
    cache_key = (clean_doi or title_fallback).strip().lower()
    if cache_key in _PAPER_METADATA_CACHE:
        return _PAPER_METADATA_CACHE[cache_key]
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
    landing = f"https://doi.org/{clean_doi}" if clean_doi else ""
    pdf_url = ""
    abstract = ""
    abstract_type = "official"
    is_oa = False
    issns = []
    src_type = "journal"
    host_org = ""
    citations = 0
    
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
        except Exception as e:
            logger.debug(f"[OpenAlex DOI] Failed fetching {clean_doi}: {e}")

    # 2. OpenAlex by Title Search
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
        except Exception as e:
            logger.debug(f"[OpenAlex Title Search] Error searching for '{title}': {e}")

    # 3. Crossref Fallback
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
        except Exception as e:
            logger.debug(f"[Crossref Fallback] Error resolving DOI {clean_doi}: {e}")

    # 4. Semantic Scholar API Fallback
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
        except Exception as e:
            logger.debug(f"[Semantic Scholar] Error resolving DOI {clean_doi}: {e}")

    # 5. DOI Landing Page HTML Scraper
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
        except Exception as e:
            logger.debug(f"[DOI Scraper] Error scraping landing page for {clean_doi}: {e}")

    # 6. Empirical SCImago / Scopus Database Indexing Resolution
    empirical_idx = journal_indexer.lookup_journal_index(issns, journal, venue_type=src_type, publisher=host_org)

    # 7. AI Academic Research Auditor
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
    except Exception as e:
        logger.debug(f"[Abstract by DOI - OpenAlex] Error for {clean_doi}: {e}")
        
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
    except Exception as e:
        logger.debug(f"[Abstract by DOI - Crossref] Error for {clean_doi}: {e}")

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
    except Exception as e:
        logger.debug(f"[Abstract by DOI - S2] Error for {clean_doi}: {e}")

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
    except Exception as e:
        logger.debug(f"[Abstract by DOI - HTML] Error for {clean_doi}: {e}")
        
    return ""

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
        "target_count": limit,
        "language_preference": lang_pref
    }
    return search_academic_papers_planned(plan)
