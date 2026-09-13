import json
import logging
import urllib.request
import urllib.parse
import re
from typing import Optional, Dict, Any, List

from utils.text_processing import (
    clean_academic_abstract,
    is_valid_abstract_content,
    extract_abstract_from_html,
    is_title_match,
    reconstruct_inverted_index,
)

logger = logging.getLogger("uvicorn.error")

SCHOLAR_USER_AGENT = "NotbookLM/1.0 (mailto:dev@notbooklm.local)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def fetch_openalex_metadata_by_doi(clean_doi: str, expected_title: str = "") -> Optional[Dict[str, Any]]:
    """Fetches structured scholarly metadata for a work from OpenAlex via DOI."""
    if not clean_doi:
        return None
    try:
        oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
        req = urllib.request.Request(oa_url, headers={"User-Agent": SCHOLAR_USER_AGENT})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            cand_title = data.get("title") or ""

            if expected_title and cand_title and not is_title_match(cand_title, expected_title):
                logger.debug(f"[OpenAlex DOI] Rejecting mismatched DOI {clean_doi}: '{cand_title}' vs '{expected_title}'")
                return None

            loc = data.get("primary_location") or {}
            src = loc.get("source") or {}
            
            issns: List[str] = []
            if src.get("issn_l"):
                issns.append(src.get("issn_l"))
            if src.get("issn"):
                if isinstance(src.get("issn"), list):
                    issns.extend(src.get("issn"))
                else:
                    issns.append(str(src.get("issn")))

            authors = [
                (a.get("author") or {}).get("display_name")
                for a in (data.get("authorships") or [])
                if (a.get("author") or {}).get("display_name")
            ]

            landing = loc.get("landing_page_url") or data.get("doi") or f"https://doi.org/{clean_doi}"
            pdf_url = loc.get("pdf_url") or (landing if landing and ".pdf" in landing else "")

            abstract = ""
            abstract_type = "official"
            idx = data.get("abstract_inverted_index")
            if idx:
                cand_abs = clean_academic_abstract(reconstruct_inverted_index(idx))
                if is_valid_abstract_content(cand_abs):
                    abstract = cand_abs
                    abstract_type = "official"

            return {
                "title": cand_title,
                "publication_date": data.get("publication_date") or "",
                "year": str(data.get("publication_year") or ""),
                "authors": authors,
                "journal": src.get("display_name") or "",
                "issns": issns,
                "src_type": src.get("type") or data.get("type", "journal"),
                "host_org": src.get("host_organization_name", ""),
                "citations": data.get("cited_by_count", 0),
                "landing": landing,
                "pdf_url": pdf_url,
                "is_oa": loc.get("is_oa", False),
                "abstract": abstract,
                "abstract_type": abstract_type,
            }
    except Exception as e:
        logger.debug(f"[OpenAlex DOI] Failed fetching {clean_doi}: {e}")
        return None

def search_openalex_metadata_by_title(title: str) -> Optional[Dict[str, Any]]:
    """Searches OpenAlex by title query to discover metadata when DOI is missing."""
    if not title:
        return None
    try:
        clean_search_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)[:120].strip()
        oa_search_url = f"https://api.openalex.org/works?search={urllib.parse.quote(clean_search_title)}&per_page=5"
        req = urllib.request.Request(oa_search_url, headers={"User-Agent": SCHOLAR_USER_AGENT})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for w in data.get("results", []):
                cand_title = w.get("title", "")
                if is_title_match(cand_title, title):
                    authors = [
                        (a.get("author") or {}).get("display_name")
                        for a in (w.get("authorships") or [])
                        if (a.get("author") or {}).get("display_name")
                    ]
                    journal = w.get("primary_location", {}).get("source", {}).get("display_name", "")
                    pub_year = str(w.get("publication_year") or "")
                    citations = w.get("cited_by_count", 0)
                    landing = w.get("doi") or ""

                    abstract = ""
                    abstract_type = "official"
                    idx = w.get("abstract_inverted_index")
                    if idx:
                        cand_abs = clean_academic_abstract(reconstruct_inverted_index(idx))
                        if is_valid_abstract_content(cand_abs):
                            abstract = cand_abs
                            abstract_type = "official"

                    return {
                        "title": cand_title,
                        "authors": authors,
                        "journal": journal,
                        "year": pub_year,
                        "citations": citations,
                        "landing": landing,
                        "abstract": abstract,
                        "abstract_type": abstract_type,
                    }
    except Exception as e:
        logger.debug(f"[OpenAlex Title Search] Error searching for '{title}': {e}")
    return None

def fetch_crossref_metadata_by_doi(clean_doi: str, expected_title: str = "") -> Optional[Dict[str, Any]]:
    """Fetches scholarly metadata from Crossref REST API via DOI."""
    if not clean_doi:
        return None
    try:
        cr_url = f"https://api.crossref.org/works/{clean_doi}"
        req = urllib.request.Request(cr_url, headers={"User-Agent": SCHOLAR_USER_AGENT})
        with urllib.request.urlopen(req, timeout=3) as resp:
            c_data = json.loads(resp.read().decode("utf-8"))
            msg = c_data.get("message", {})
            title_list = msg.get("title", [])
            cr_cand_title = title_list[0] if title_list else ""

            if expected_title and cr_cand_title and not is_title_match(cr_cand_title, expected_title):
                logger.debug(f"[Crossref DOI] Rejecting mismatched DOI {clean_doi}: '{cr_cand_title}' vs '{expected_title}'")
                return None

            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in msg.get("author", [])
                if a.get("family") or a.get("given")
            ]
            container = msg.get("container-title", [])
            journal = container[0] if container else ""

            date_info = (
                msg.get("issued")
                or msg.get("published-print")
                or msg.get("published-online")
                or msg.get("created")
                or {}
            )
            date_parts = date_info.get("date-parts")
            pub_year = str(date_parts[0][0]) if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0 else ""
            citations = msg.get("is-referenced-by-count", 0)
            landing = msg.get("URL", f"https://doi.org/{clean_doi}")

            abstract = ""
            abstract_type = "official"
            raw_abstract = msg.get("abstract", "")
            if raw_abstract:
                cand_abs = clean_academic_abstract(raw_abstract)
                if is_valid_abstract_content(cand_abs):
                    abstract = cand_abs
                    abstract_type = "official"

            return {
                "title": cr_cand_title,
                "authors": authors,
                "journal": journal,
                "year": pub_year,
                "citations": citations,
                "landing": landing,
                "abstract": abstract,
                "abstract_type": abstract_type,
            }
    except Exception as e:
        logger.debug(f"[Crossref Fallback] Error resolving DOI {clean_doi}: {e}")
        return None

def fetch_semantic_scholar_metadata_by_doi(clean_doi: str, expected_title: str = "") -> Optional[Dict[str, Any]]:
    """Fetches citation count, abstract, and open-access PDF info from Semantic Scholar."""
    if not clean_doi:
        return None
    try:
        s2_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}?fields=abstract,authors,title,venue,year,citationCount,openAccessPdf"
        req = urllib.request.Request(s2_url, headers={"User-Agent": SCHOLAR_USER_AGENT})
        with urllib.request.urlopen(req, timeout=3) as resp:
            s2_data = json.loads(resp.read().decode("utf-8"))
            s2_title = s2_data.get("title") or ""
            if expected_title and s2_title and not is_title_match(s2_title, expected_title):
                logger.debug(f"[S2 DOI] Rejecting mismatched DOI {clean_doi}: '{s2_title}' vs '{expected_title}'")
                return None

            authors = [a.get("name") for a in s2_data.get("authors", []) if a.get("name")]
            pub_year = str(s2_data.get("year") or "")
            citations = s2_data.get("citationCount", 0)
            pdf_url = (s2_data.get("openAccessPdf") or {}).get("url") or ""

            abstract = ""
            abstract_type = "official"
            s2_abs = s2_data.get("abstract")
            if s2_abs:
                cand_abs = clean_academic_abstract(s2_abs)
                if is_valid_abstract_content(cand_abs):
                    abstract = cand_abs
                    abstract_type = "official"

            return {
                "title": s2_title,
                "authors": authors,
                "year": pub_year,
                "citations": citations,
                "pdf_url": pdf_url,
                "abstract": abstract,
                "abstract_type": abstract_type,
            }
    except Exception as e:
        logger.debug(f"[Semantic Scholar] Error resolving DOI {clean_doi}: {e}")
        return None

def scrape_doi_landing_page_metadata(clean_doi: str) -> Dict[str, Any]:
    """Scrapes publisher landing page HTML meta tags for title, authors, journal, and abstract."""
    result = {
        "raw_html": "",
        "abstract": "",
        "abstract_type": "official",
        "authors": [],
        "journal": "",
    }
    if not clean_doi:
        return result
    try:
        doi_landing_url = f"https://doi.org/{clean_doi}"
        req = urllib.request.Request(doi_landing_url, headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw_html_content = resp.read().decode("utf-8", errors="ignore")
            result["raw_html"] = raw_html_content

            extracted = extract_abstract_from_html(raw_html_content)
            if extracted and is_valid_abstract_content(extracted):
                result["abstract"] = extracted
                result["abstract_type"] = "official"

            author_tags = re.findall(
                r'<meta\s+[^>]*?name=["\'](?:citation_author|dc\.creator)["\'][^>]*?content=["\'](.*?)["\']',
                raw_html_content,
                re.I
            )
            if author_tags:
                result["authors"] = [a.strip() for a in author_tags if a.strip()]

            j_match = re.search(
                r'<meta\s+[^>]*?name=["\'](?:citation_journal_title|citation_conference_title|dc\.source)["\'][^>]*?content=["\'](.*?)["\']',
                raw_html_content,
                re.I
            )
            if j_match:
                result["journal"] = j_match.group(1).strip()
    except Exception as e:
        logger.debug(f"[DOI Scraper] Error scraping landing page for {clean_doi}: {e}")

    return result
