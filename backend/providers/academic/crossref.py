import logging
import requests
import re
from typing import List, Optional

logger = logging.getLogger("uvicorn.error")

def fetch_crossref(
    term: str, 
    target_count: int, 
    min_year: Optional[int], 
    open_access_only: bool, 
    headers: dict,
    is_valid_academic_title_fn,
    is_candidate_duplicate_fn,
    is_matching_topic_fn,
    mark_candidate_seen_fn
) -> List[dict]:
    fetched = []
    if not term.strip(): return fetched
    offset = 0
    while len(fetched) < target_count and offset <= (target_count * 3):
        try:
            url = "https://api.crossref.org/works"
            rows = min(target_count - len(fetched) + 30, 100)
            params = {"query": term.strip(), "rows": rows, "offset": offset}
            if min_year: params["filter"] = f"from-pub-date:{min_year}-01-01"
            resp = requests.get(url, params=params, headers=headers, timeout=8)
            if resp.status_code == 200:
                items = resp.json().get("message", {}).get("items", [])
                if not items: break
                for item in items:
                    if len(fetched) >= target_count: break
                    title_list = item.get("title", [])
                    if not title_list: continue
                    title = title_list[0].strip()
                    doi = item.get("DOI", "")
                    if not title or not is_valid_academic_title_fn(title) or is_candidate_duplicate_fn(title, doi): continue
                        
                    year = "N/A"
                    date_info = (
                        item.get("issued")
                        or item.get("published-print")
                        or item.get("published-online")
                        or item.get("created")
                        or {}
                    )
                    date_parts = date_info.get("date-parts")
                    if date_parts and len(date_parts) > 0 and len(date_parts[0]) > 0:
                        year = str(date_parts[0][0])
                    if min_year and year.isdigit() and int(year) < min_year: continue

                    # Open access link check for Crossref
                    link_list = item.get("link") or []
                    oa_pdf_link = ""
                    for l_entry in link_list:
                        if l_entry.get("content-type") == "application/pdf":
                            oa_pdf_link = l_entry.get("URL", "")
                            break
                    is_oa_cr = bool(oa_pdf_link) or any("open-access" in str(lic.get("URL", "")).lower() for lic in (item.get("license") or []))
                    if open_access_only and not is_oa_cr:
                        continue
                        
                    authors = [
                        f"{a.get('given', '')} {a.get('family', '')}".strip() 
                        for a in (item.get("author") or [])
                        if a.get("family") or a.get("given") or a.get("name")
                    ]
                    venue = item.get("container-title", [""])[0] if item.get("container-title") else ""
                    raw_abs = item.get("abstract", "")
                    clean_abs = re.sub(r"<[^>]+>", " ", raw_abs) if raw_abs else ""
                    snippet = re.sub(r"\s+", " ", clean_abs).strip() if clean_abs else f"Scholarly contribution published in {venue} ({year}). DOI: {doi}"
                    
                    if not is_matching_topic_fn(title, snippet): continue
                        
                    mark_candidate_seen_fn(title, doi)
                    fetched.append({
                        "title": title,
                        "year": str(year),
                        "doi": f"https://doi.org/{doi}" if doi and not doi.startswith("http") else doi,
                        "url": f"https://doi.org/{doi}" if doi else item.get("URL", ""),
                        "snippet": snippet,
                        "authors": authors,
                        "venue": venue,
                        "pdf_url": oa_pdf_link,
                        "is_oa": is_oa_cr
                    })
                offset += rows
            else:
                break
        except Exception as e:
            logger.warning(f"Crossref API err: {e}")
            break
    return fetched