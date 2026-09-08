import logging
from typing import Optional
from collections import OrderedDict

from utils.text_processing import (
    clean_doi as _clean_doi,
    clean_academic_abstract,
    is_ai_synthesized_overview,
    GENERIC_TITLE_BLACKLIST,
)
from providers.academic import (
    fetch_openalex_metadata_by_doi,
    search_openalex_metadata_by_title,
    fetch_crossref_metadata_by_doi,
    fetch_semantic_scholar_metadata_by_doi,
    scrape_doi_landing_page_metadata,
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
        
        venue_type = "journal"
        if any(c in t_low or c in d_low for c in ["proceedings", "conference", "symposium", "workshop"]):
            venue_type = "conference"
        elif any(p in t_low or p in d_low for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf", "preprint"]):
            venue_type = "preprint"

        idx_info = journal_indexer.lookup_journal_index(
            journal_title=title_fallback,
            venue_type=venue_type
        )
        metric = idx_info.get("journal_metric") or "Peer-Reviewed"
        quality_tier = idx_info.get("quality_tier", 4)

        fast_result = {
            "title": title_fallback,
            "authors": [],
            "publication_date": "",
            "year": "",
            "journal": title_fallback or "Peer-reviewed Publication",
            "journal_metric": metric,
            "quality_tier": quality_tier,
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
    raw_html_content = ""
    
    # 1. OpenAlex by DOI
    if clean_doi:
        oa_data = fetch_openalex_metadata_by_doi(clean_doi, expected_title=title or title_fallback)
        if oa_data:
            title = oa_data.get("title") or title
            pub_date = oa_data.get("publication_date") or ""
            pub_year = oa_data.get("year") or ""
            authors = oa_data.get("authors") or []
            if oa_data.get("journal"):
                journal = oa_data["journal"]
            issns.extend(oa_data.get("issns") or [])
            src_type = oa_data.get("src_type") or "journal"
            host_org = oa_data.get("host_org") or ""
            citations = oa_data.get("citations", 0)
            landing = oa_data.get("landing") or landing
            pdf_url = oa_data.get("pdf_url") or pdf_url
            is_oa = oa_data.get("is_oa", False)
            if oa_data.get("abstract"):
                abstract = oa_data["abstract"]
                abstract_type = oa_data.get("abstract_type", "official")

    # 2. OpenAlex by Title Search Fallback
    if not authors and (title or title_fallback):
        oa_title_data = search_openalex_metadata_by_title(title or title_fallback)
        if oa_title_data:
            if not title and oa_title_data.get("title"):
                title = oa_title_data["title"]
            if not authors and oa_title_data.get("authors"):
                authors = oa_title_data["authors"]
            if (not journal or journal == "Peer-reviewed Publication") and oa_title_data.get("journal"):
                journal = oa_title_data["journal"]
            if not pub_year and oa_title_data.get("year"):
                pub_year = oa_title_data["year"]
            if not citations and oa_title_data.get("citations"):
                citations = oa_title_data["citations"]
            if not landing and oa_title_data.get("landing"):
                landing = oa_title_data["landing"]
            if not abstract and oa_title_data.get("abstract"):
                abstract = oa_title_data["abstract"]
                abstract_type = oa_title_data.get("abstract_type", "official")

    # 3. Crossref Fallback
    if clean_doi and (not authors or not journal or journal == "Peer-reviewed Publication" or not abstract):
        cr_data = fetch_crossref_metadata_by_doi(clean_doi, expected_title=title or title_fallback)
        if cr_data:
            if not title and cr_data.get("title"):
                title = cr_data["title"]
            if not authors and cr_data.get("authors"):
                authors = cr_data["authors"]
            if (not journal or journal == "Peer-reviewed Publication") and cr_data.get("journal"):
                journal = cr_data["journal"]
            if not pub_year and cr_data.get("year"):
                pub_year = cr_data["year"]
            if not citations and cr_data.get("citations"):
                citations = cr_data["citations"]
            if not landing and cr_data.get("landing"):
                landing = cr_data["landing"]
            if not abstract and cr_data.get("abstract"):
                abstract = cr_data["abstract"]
                abstract_type = cr_data.get("abstract_type", "official")

    # 4. Semantic Scholar API Fallback
    if clean_doi and not abstract:
        s2_data = fetch_semantic_scholar_metadata_by_doi(clean_doi, expected_title=title or title_fallback)
        if s2_data:
            if not authors and s2_data.get("authors"):
                authors = s2_data["authors"]
            if not pub_year and s2_data.get("year"):
                pub_year = s2_data["year"]
            if not citations and s2_data.get("citations"):
                citations = s2_data["citations"]
            if not pdf_url and s2_data.get("pdf_url"):
                pdf_url = s2_data["pdf_url"]
            if not abstract and s2_data.get("abstract"):
                abstract = s2_data["abstract"]
                abstract_type = s2_data.get("abstract_type", "official")

    # 5. DOI Landing Page HTML Scraper
    if clean_doi and (not abstract or not authors or not journal or journal == "Peer-reviewed Publication"):
        scraped = scrape_doi_landing_page_metadata(clean_doi)
        raw_html_content = scraped.get("raw_html", "")
        if not abstract and scraped.get("abstract"):
            abstract = scraped["abstract"]
            abstract_type = scraped.get("abstract_type", "official")
        if not authors and scraped.get("authors"):
            authors = scraped["authors"]
        if (not journal or journal == "Peer-reviewed Publication") and scraped.get("journal"):
            journal = scraped["journal"]

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
    if final_title and final_title.lower().strip() in GENERIC_TITLE_BLACKLIST:
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
