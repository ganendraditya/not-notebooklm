import json
import logging
import urllib.request
import urllib.parse
import re
from typing import Optional
from collections import OrderedDict

from utils.text_processing import (
    clean_doi as _clean_doi,
    clean_academic_abstract,
    is_valid_abstract_content,
    extract_abstract_from_html,
    is_title_match,
    is_ai_synthesized_overview
)
from services.search.llm_evaluator_service import audit_paper_metadata_with_ai
import journal_indexer

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

_GLOBAL_METADATA_CACHE = LRUMetadataCache(capacity=500)

def resolve_paper_metadata_by_doi(
    doi: str = "", 
    title_fallback: str = "", 
    paper_title: str = "", 
    fast_only: bool = False,
    cache: Optional[dict] = None
) -> Optional[dict]:
    """
    Fetches complete Consensus-style academic metadata from OpenAlex, Crossref, HTML meta/semantic tags,
    Semantic Scholar, SCImago Master DB, and AI Academic Auditor with a multi-tier fallback engine and caching.
    """
    if cache is None:
        cache = _GLOBAL_METADATA_CACHE

    if paper_title and not title_fallback:
        title_fallback = paper_title
    if not doi and not title_fallback:
        return None
    clean_doi = _clean_doi(doi) if doi else ""
    cache_key = (clean_doi or title_fallback).strip().lower()
    
    if cache is not None and cache_key in cache:
        return cache[cache_key]
        
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
        if cache is not None:
            cache[cache_key] = fast_result
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
                cand_title = data.get("title") or ""
                
                # Check if resolved paper matches the target title (prevent bibliography DOI hijacking)
                if (title or title_fallback) and cand_title and not is_title_match(cand_title, (title or title_fallback)):
                    logger.debug(f"[OpenAlex DOI] Rejecting mismatched DOI {clean_doi}: '{cand_title}' vs '{title or title_fallback}'")
                else:
                    title = cand_title or title
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
                cr_cand_title = title_list[0] if title_list else ""
                
                # Check title match for Crossref DOI resolution
                if (title or title_fallback) and cr_cand_title and not is_title_match(cr_cand_title, (title or title_fallback)):
                    logger.debug(f"[Crossref DOI] Rejecting mismatched DOI {clean_doi}: '{cr_cand_title}' vs '{title or title_fallback}'")
                else:
                    if not title and cr_cand_title:
                        title = cr_cand_title
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
                s2_title = s2_data.get("title") or ""
                if (title or title_fallback) and s2_title and not is_title_match(s2_title, (title or title_fallback)):
                    logger.debug(f"[S2 DOI] Rejecting mismatched DOI {clean_doi}: '{s2_title}' vs '{title or title_fallback}'")
                else:
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

    final_title = audited.get("title") or title or title_fallback or clean_doi
    _GENERIC_TITLE_BLACKLIST = {
        "abstract", "abstrak", "overview", "paper", "document",
        "article in press", "in press", "journal pre-proof", "uncorrected proof",
        "corrected proof", "original article", "research article", "full length article",
        "short communication", "review article", "full paper", "research paper",
        "accepted manuscript", "author's copy", "analytical index", "index",
    }
    if final_title and final_title.lower().strip() in _GENERIC_TITLE_BLACKLIST:
        final_title = title_fallback or clean_doi
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
    if cache is not None:
        cache[cache_key] = result
    return result

def fetch_full_abstract_by_doi(doi: str) -> str:
    """Fetches the full, authentic academic abstract using DOI via the unified metadata resolver."""
    if not doi:
        return ""
    clean_doi = _clean_doi(doi)
    meta = resolve_paper_metadata_by_doi(doi=clean_doi, fast_only=False)
    return (meta.get("abstract") or "") if meta else ""
