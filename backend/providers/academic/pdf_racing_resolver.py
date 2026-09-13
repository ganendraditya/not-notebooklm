import os
import re
import urllib.parse
import logging
from typing import Optional, List, Callable
import requests
import threading
import concurrent.futures

from utils.pdf_utils import is_authentic_pdf_bytes
from utils.text_processing import clean_doi as normalize_doi
from providers.scrapers.oa_fetcher import try_fetch_open_access_pdf

logger = logging.getLogger("uvicorn.error")

def resolve_arxiv_pdf(clean_doi: str, title: str, direct_url: str, candidate_pdf_url: str) -> Optional[bytes]:
    """Resolves arXiv preprints directly via standard PDF endpoints."""
    all_text = f"{clean_doi} {title} {direct_url} {candidate_pdf_url}".lower()
    m = re.search(r'(?:arxiv[:\s/]|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)', all_text)
    arxiv_id = m.group(1) if m else None
    if not arxiv_id and "arxiv." in clean_doi:
        m2 = re.search(r'(\d{4}\.\d{4,5})', clean_doi)
        if m2:
            arxiv_id = m2.group(1)
    if arxiv_id:
        return try_fetch_open_access_pdf(f"https://arxiv.org/pdf/{arxiv_id}.pdf", timeout_sec=4)
    return None

def resolve_unpaywall_pdf(clean_doi: str) -> Optional[bytes]:
    """Resolves OA PDF through Unpaywall REST API."""
    if not clean_doi:
        return None
    try:
        upw_url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(clean_doi)}?email=research@notbooklm.app"
        resp = requests.get(upw_url, timeout=4.5)
        if resp.status_code == 200:
            upw_data = resp.json()
            best_oa = upw_data.get("best_oa_location") or {}
            oa_pdf_url = best_oa.get("url_for_pdf") or best_oa.get("url")
            if oa_pdf_url:
                return try_fetch_open_access_pdf(oa_pdf_url, timeout_sec=4)
    except Exception:
        pass
    return None

def resolve_openalex_pdf(clean_doi: str) -> Optional[bytes]:
    """Resolves OA PDF through OpenAlex global registry API."""
    if not clean_doi:
        return None
    try:
        oa_url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
        resp = requests.get(oa_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:research@notbooklm.app)"}, timeout=5.0)
        if resp.status_code == 200:
            wdata = resp.json()
            best_loc = wdata.get("best_oa_location") or wdata.get("primary_location") or {}
            p_url = best_loc.get("pdf_url") or best_loc.get("landing_page_url")
            if p_url:
                return try_fetch_open_access_pdf(p_url, timeout_sec=4)
    except Exception:
        pass
    return None

def resolve_europe_pmc_pdf(clean_doi: str, title: str) -> Optional[bytes]:
    """Resolves OA PDF through Europe PMC open repository."""
    if not clean_doi and not title:
        return None
    try:
        q = f"DOI:{urllib.parse.quote(clean_doi)}" if clean_doi else f'TITLE:"{urllib.parse.quote(title)}"'
        epmc_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&format=json&resultType=core&pageSize=1"
        resp = requests.get(epmc_url, timeout=5.0)
        if resp.status_code == 200:
            epmc_data = resp.json()
            results = epmc_data.get("resultList", {}).get("result", [])
            if results:
                ft_urls = results[0].get("fullTextUrlList", {}).get("fullTextUrl", [])
                for ft in ft_urls:
                    if ft.get("documentStyle") == "pdf" and ft.get("url"):
                        data = try_fetch_open_access_pdf(ft.get("url"), timeout_sec=4)
                        if data:
                            return data
    except Exception:
        pass
    return None

def resolve_semantic_scholar_pdf(clean_doi: str) -> Optional[bytes]:
    """Resolves OA PDF through Semantic Scholar Graph API."""
    if not clean_doi:
        return None
    try:
        s2_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{clean_doi}?fields=openAccessPdf"
        resp = requests.get(s2_url, headers={"User-Agent": "NotbookLM/1.0 (mailto:research@notbooklm.app)"}, timeout=4.5)
        if resp.status_code == 200:
            oa_pdf = resp.json().get("openAccessPdf", {}).get("url")
            if oa_pdf:
                return try_fetch_open_access_pdf(oa_pdf, timeout_sec=4)
    except Exception:
        pass
    return None

def resolve_landing_page_pdf(clean_doi: str, direct_url: str) -> Optional[bytes]:
    """Inspects publisher landing page meta tags and OJS links."""
    landing_target = direct_url or (f"https://doi.org/{clean_doi}" if clean_doi else "")
    if not landing_target or not landing_target.startswith("http"):
        return None
    try:
        resp = requests.get(landing_target, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }, timeout=5.0, allow_redirects=True)
        if resp.status_code == 200:
            html = resp.text
            final_url = resp.url

            # A. Citation meta tags
            meta_matches = re.findall(
                r'<meta\s+[^>]*?name=["\'](?:citation_pdf_url|eprints\.document_url)["\'][^>]*?content=["\'](.*?)["\']', 
                html, re.I
            )
            for m_pdf in meta_matches:
                m_pdf = m_pdf.strip()
                if m_pdf.startswith("http"):
                    data = try_fetch_open_access_pdf(m_pdf, timeout_sec=4)
                    if data:
                        return data

            # B. OJS / Galley patterns
            candidate_urls = []
            seen_cand = set()
            for m in re.findall(r'href=["\']([^"\']+/article/download/[^"\']+)["\']', html, re.I):
                u = urllib.parse.urljoin(final_url, m)
                if u not in seen_cand:
                    seen_cand.add(u)
                    candidate_urls.append(u)
            for m in re.findall(r'href=["\']([^"\']+/article/view/(\d+)/(\d+)[^"\']*)["\']', html, re.I):
                cand_dl = re.sub(r'/article/view/(\d+)/(\d+)', r'/article/download/\1/\2', urllib.parse.urljoin(final_url, m[0]))
                if cand_dl not in seen_cand:
                    seen_cand.add(cand_dl)
                    candidate_urls.append(cand_dl)
            for m in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', html, re.I):
                u = urllib.parse.urljoin(final_url, m)
                if u not in seen_cand:
                    seen_cand.add(u)
                    candidate_urls.append(u)

            for cand in candidate_urls[:2]:
                data = try_fetch_open_access_pdf(cand, timeout_sec=2.5)
                if data:
                    return data
    except Exception:
        pass
    return None

def resolve_and_fetch_authentic_pdf(
    doi: str = "",
    title: str = "",
    direct_url: str = "",
    candidate_pdf_url: str = ""
) -> Optional[bytes]:
    """
    Universal Parallel Racing Resolver for Authentic Academic Full-Text PDFs.
    Fires all discovery channels concurrently and returns the FIRST authentic binary PDF bytes immediately.
    """
    clean_doi = normalize_doi(doi).lower()
    
    # Fast path: Check candidate_pdf_url directly if provided
    if candidate_pdf_url and candidate_pdf_url.startswith("http"):
        fast_url = candidate_pdf_url
        if "/article/view/" in fast_url:
            fast_url = re.sub(
                r'/article/view/(\d+)(?:/(\d+))?',
                lambda m: f"/article/download/{m.group(1)}" + (f"/{m.group(2)}" if m.group(2) else ""),
                fast_url
            ).rstrip('/')
        pdf_bytes = try_fetch_open_access_pdf(fast_url, timeout_sec=4)
        if pdf_bytes:
            return pdf_bytes

    stop_event = threading.Event()
    winning_result: List[bytes] = []
    lock = threading.Lock()

    def set_winner(data: Optional[bytes]):
        if not data or not is_authentic_pdf_bytes(data, min_size=1000):
            return
        with lock:
            if not winning_result:
                winning_result.append(data)
                stop_event.set()

    def worker_arxiv():
        if stop_event.is_set(): return
        data = resolve_arxiv_pdf(clean_doi, title, direct_url, candidate_pdf_url)
        if data: set_winner(data)

    def worker_unpaywall():
        if stop_event.is_set() or not clean_doi: return
        data = resolve_unpaywall_pdf(clean_doi)
        if data: set_winner(data)

    def worker_openalex():
        if stop_event.is_set() or not clean_doi: return
        data = resolve_openalex_pdf(clean_doi)
        if data: set_winner(data)

    def worker_europe_pmc():
        if stop_event.is_set() or (not clean_doi and not title): return
        data = resolve_europe_pmc_pdf(clean_doi, title)
        if data: set_winner(data)

    def worker_semantic_scholar():
        if stop_event.is_set() or not clean_doi: return
        data = resolve_semantic_scholar_pdf(clean_doi)
        if data: set_winner(data)

    def worker_landing_page():
        if stop_event.is_set(): return
        data = resolve_landing_page_pdf(clean_doi, direct_url)
        if data: set_winner(data)

    workers = [
        worker_arxiv,
        worker_landing_page,
        worker_unpaywall,
        worker_openalex,
        worker_europe_pmc,
        worker_semantic_scholar
    ]

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(workers))
    try:
        futures = [executor.submit(w) for w in workers]
        stop_event.wait(timeout=10.0)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    with lock:
        if winning_result:
            return winning_result[0]

    return None
