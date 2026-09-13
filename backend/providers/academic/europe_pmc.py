import logging
import urllib.parse
import requests
import re
import html
from typing import List, Optional

logger = logging.getLogger("uvicorn.error")

def fetch_europe_pmc(
    term: str, 
    target_count: int, 
    min_year: Optional[int], 
    open_access_only: bool, 
    exclude_preprints: bool,
    is_valid_academic_title_fn,
    is_candidate_duplicate_fn,
    is_matching_topic_fn,
    mark_candidate_seen_fn
) -> List[dict]:
    fetched = []
    if not term.strip(): return fetched
    try:
        query_term = term.strip()
        if open_access_only:
            query_term += " OPEN_ACCESS:y"
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={urllib.parse.quote(query_term)}&format=json&pageSize={min(target_count + 10, 50)}&resultType=core"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            for p in resp.json().get("resultList", {}).get("result", []):
                if len(fetched) >= target_count: break
                title = html.unescape(p.get("title") or "").strip().rstrip(".")
                doi = p.get("doi", "")
                if not title or not is_valid_academic_title_fn(title) or is_candidate_duplicate_fn(title, doi): continue
                
                year = str(p.get("pubYear", ""))
                if min_year and year.isdigit() and int(year) < min_year: continue
                
                author_str = p.get("authorString") or ""
                authors = [a.strip() for a in author_str.split(",") if a.strip()]
                venue = p.get("journalTitle") or ""
                abstract = p.get("abstractText") or ""
                ft_urls = (p.get("fullTextUrlList") or {}).get("fullTextUrl") or []
                pdf_urls = [f.get("url") for f in ft_urls if f.get("documentStyle") == "pdf" and f.get("url")]
                pdf_url = pdf_urls[0] if pdf_urls else ""
                
                # Filter OA if requested
                is_oa_pmc = p.get("isOpenAccess") == "Y" or bool(pdf_url)
                if open_access_only and not is_oa_pmc:
                    continue

                # Filter preprint
                is_preprint_pmc = p.get("pubType") == "preprint" or "preprint" in (venue or "").lower()
                if exclude_preprints and is_preprint_pmc:
                    continue
                
                snippet = abstract if abstract else f"Scholarly research publication in {venue} ({year}). DOI: {doi}"
                if not is_matching_topic_fn(title, snippet): continue
                
                mark_candidate_seen_fn(title, doi)
                src = p.get("source") or "MED"
                fetched.append({
                    "title": title,
                    "year": str(year),
                    "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                    "url": f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{src}/{p.get('id')}",
                    "snippet": snippet,
                    "authors": authors,
                    "venue": venue,
                    "pdf_url": pdf_url,
                    "is_oa": is_oa_pmc
                })
    except Exception as e:
        logger.warning(f"EuropePMC API err: {e}")
    return fetched
