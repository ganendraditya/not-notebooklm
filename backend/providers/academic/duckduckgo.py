import re
import html
import base64
import logging
import warnings
from typing import List, Optional, Callable
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

# Suppress harmless upstream package rename warning
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*renamed to.*")

logger = logging.getLogger("uvicorn.error")

IGNORED_DOMAINS = {
    "youtube.com", "m.youtube.com", "youtu.be",
    "facebook.com", "m.facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com",
    "reddit.com",
    "pinterest.com",
    "ebay.com",
    "amazon.com",
    "netflix.com",
    "spotify.com"
}

KNOWN_ACADEMIC_VENUES = {
    "arxiv.org": "arXiv",
    "biorxiv.org": "bioRxiv",
    "medrxiv.org": "medRxiv",
    "sciencedirect.com": "ScienceDirect",
    "nature.com": "Nature",
    "ieee.org": "IEEE Xplore",
    "ieeexplore.ieee.org": "IEEE Xplore",
    "acm.org": "ACM Digital Library",
    "dl.acm.org": "ACM Digital Library",
    "springer.com": "SpringerLink",
    "link.springer.com": "SpringerLink",
    "wiley.com": "Wiley Online Library",
    "onlinelibrary.wiley.com": "Wiley Online Library",
    "tandfonline.com": "Taylor & Francis",
    "frontiersin.org": "Frontiers",
    "mdpi.com": "MDPI",
    "ncbi.nlm.nih.gov": "PubMed / NCBI",
    "pubmed.ncbi.nlm.nih.gov": "PubMed",
    "semanticscholar.org": "Semantic Scholar",
    "researchgate.net": "ResearchGate",
    "jstor.org": "JSTOR",
    "ssrn.com": "SSRN",
    "academia.edu": "Academia.edu",
    "scispace.com": "SciSpace",
    "semanticscholar.org": "Semantic Scholar"
}

OPEN_ACCESS_DOMAINS = {
    "arxiv.org", "biorxiv.org", "medrxiv.org", "ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov", "semanticscholar.org", "zenodo.org", "doaj.org",
    "plos.org", "frontiersin.org", "mdpi.com"
}

def clean_web_title(raw_title: str) -> str:
    """Cleans SERP title strings, unescaping HTML and removing portal/site suffixes."""
    t = html.unescape(raw_title).strip()
    t = re.sub(r'<[^>]+>', '', t).strip()
    # Strip media/type labels
    t = re.sub(r'^\[(?:PDF|DOC|DOCX|HTML|BOOK)\]\s*', '', t, flags=re.I).strip()
    # Strip trailing site attribution suffixes
    t = re.sub(
        r'\s*[-|–—:]\s*(?:arXiv(?:\.org)?|ScienceDirect|ResearchGate|PubMed|NCBI|IEEE(?:\s+Xplore)?|SpringerLink|Semantic\s+Scholar|Nature|Wiley(?:\s+Online\s+Library)?|Taylor\s+&\s+Francis(?:\s+Online)?|ACM(?:\s+Digital\s+Library)?|MDPI|Frontiers|JSTOR|SSRN|Wikipedia).*$',
        '',
        t,
        flags=re.I
    ).strip()
    # Strip leading bracketed publication indicators like [1706.03762]
    t = re.sub(r'^\[\d{4,5}\.\d{4,5}(?:v\d+)?\]\s*', '', t).strip()
    # Strip URL breadcrumb prefix if mistakenly captured (e.g. "domain.comhttps://domain.com › path")
    t = re.sub(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}https?://\S+\s*', '', t).strip()
    return t

def extract_authors_from_snippet(snippet: str) -> List[str]:
    """Heuristically extracts author names from search snippet or returns a fallback descriptor."""
    by_match = re.search(
        r'\b(?:by|authors?[:\-])\s+([A-Z][a-zA-Z\s,.-]+?)(?:\s*[-–—|•·]|\s*\d{4}|\s*Abstract|\.|$)',
        snippet,
        re.I
    )
    if by_match:
        cand_str = by_match.group(1).strip()
        parts = [p.strip() for p in re.split(r'[,&]|\band\b', cand_str) if len(p.strip().split()) in (2, 3, 4)]
        if parts:
            return parts[:4]
    return ["Web Scholar Source"]

def extract_venue_from_url(url: str) -> str:
    """Extracts human-readable academic venue or publisher from hostname."""
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for k, v in KNOWN_ACADEMIC_VENUES.items():
        if k in domain:
            return v
    return domain.capitalize() if domain else "Academic Web"

def unwrap_bing_redirect(href: str) -> str:
    """Unwraps Bing SERP redirect links (/ck/a?...) into target destination URLs."""
    if href.startswith("https://www.bing.com/ck/a?"):
        try:
            u = parse_qs(urlparse(href).query).get("u", [""])[0]
            if u.startswith("a1"):
                b = u[2:]
                padded = b + "=" * ((-len(b)) % 4)
                decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
                if decoded.startswith("http"):
                    return decoded
        except Exception:
            pass
    return href

def fetch_duckduckgo_fallback(
    term: str,
    target_count: int,
    min_year: Optional[int],
    open_access_only: bool,
    is_valid_academic_title_fn: Callable[[str], bool],
    is_candidate_duplicate_fn: Callable[[str, str], bool],
    is_matching_topic_fn: Callable[[str, str], bool],
    mark_candidate_seen_fn: Callable[[str, str], None],
) -> List[dict]:
    """
    Stage 3 Fallback: DuckDuckGo / Web Scholarly Search.
    Discovers academic papers and research publications when primary scholarly APIs
    (Europe PMC, OpenAlex, Crossref) return insufficient or empty results.
    """
    fetched = []
    clean_query = term.strip()
    if not clean_query or target_count <= 0:
        return fetched

    raw_items = []

    # Attempt 1: Query using duckduckgo_search official client
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            # Query with academic literature modifiers for high scholarly signal
            academic_query = f"{clean_query} (research paper OR journal OR arxiv OR doi OR pdf)"
            ddg_results = ddgs.text(academic_query, max_results=target_count * 2)
            if not ddg_results:
                ddg_results = ddgs.text(clean_query, max_results=target_count * 2)
            
            for item in ddg_results or []:
                raw_items.append({
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", "")
                })
    except Exception as e:
        logger.debug(f"[DDGS Text Search Notice]: {e}")

    # Attempt 2: Resilient SERP Parser Fallback if DDGS returned 0 results
    if not raw_items:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                search_q = f"{clean_query} research paper OR journal OR arxiv"
                resp = ddgs._get_url("GET", "https://www.bing.com/search", params={"q": search_q})
                if resp and resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for li in soup.find_all("li", class_="b_algo"):
                        h2 = li.find("h2")
                        if not h2:
                            continue
                        a = h2.find_parent("a") or h2.find("a")
                        if not a or not a.get("href"):
                            continue
                        
                        href = unwrap_bing_redirect(a.get("href", ""))
                        title_text = h2.get_text().strip()
                        p = li.find("p")
                        body_text = p.get_text().strip() if p else ""
                        
                        raw_items.append({
                            "title": title_text,
                            "href": href,
                            "body": body_text
                        })
        except Exception as serp_err:
            logger.debug(f"[Web Search SERP Parser Notice]: {serp_err}")

    # Process and sanitize raw items into standardized PaperCandidate dicts
    for item in raw_items:
        if len(fetched) >= target_count:
            break

        raw_title = item.get("title", "")
        href = unwrap_bing_redirect(item.get("href", "")).strip()
        body = item.get("body", "").strip()

        if not raw_title or not href:
            continue

        domain = urlparse(href).netloc.lower().replace("www.", "")
        if not domain or any(ign in domain for ign in IGNORED_DOMAINS):
            continue

        title = clean_web_title(raw_title)
        if not title:
            continue

        # Extract DOI if present in URL or body
        doi_m = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', href + " " + body)
        doi = doi_m.group(0).rstrip(".;,)") if doi_m else ""

        if not is_valid_academic_title_fn(title) or is_candidate_duplicate_fn(title, doi):
            continue

        # Extract publication year
        year_m = re.search(r'\b(19\d{2}|20\d{2})\b', body + " " + title + " " + href)
        year_str = year_m.group(1) if year_m else "N/A"
        if min_year and year_str.isdigit() and int(year_str) < min_year:
            continue

        # Derive authentic PDF link if direct link or arXiv
        pdf_url = ""
        if href.lower().endswith(".pdf"):
            pdf_url = href
        elif "arxiv.org/abs/" in href:
            arxiv_id_match = re.search(r'arxiv\.org/abs/([0-9]+\.[0-9]+(?:v[0-9]+)?)', href, re.I)
            if arxiv_id_match:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id_match.group(1)}.pdf"

        # Determine Open Access status
        is_oa = bool(pdf_url) or any(oa_d in domain for oa_d in OPEN_ACCESS_DOMAINS)
        if open_access_only and not is_oa:
            continue

        venue = extract_venue_from_url(href)
        authors = extract_authors_from_snippet(body)
        snippet = body if body else f"Scholarly literature discovered via Web Scholar Search from {venue}."

        if not is_matching_topic_fn(title, snippet):
            continue

        mark_candidate_seen_fn(title, doi)
        fetched.append({
            "title": title,
            "year": year_str,
            "doi": doi,
            "url": href,
            "snippet": snippet,
            "authors": authors,
            "venue": venue,
            "pdf_url": pdf_url,
            "is_oa": is_oa,
            "journal_metric": "Web Search Fallback",
            "citations": 0
        })

    return fetched
