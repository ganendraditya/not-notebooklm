import requests
import html
import re
from typing import List, Optional
from utils.text_processing import reconstruct_inverted_index

def fetch_openalex(
    term: str, 
    target_count: int, 
    min_year: Optional[int], 
    min_citations: int,
    open_access_only: bool, 
    exclude_preprints: bool,
    lang_codes: Optional[List[str]],
    headers: dict,
    is_valid_academic_title_fn,
    is_candidate_duplicate_fn,
    is_matching_topic_fn,
    mark_candidate_seen_fn
) -> List[dict]:
    fetched = []
    if not term.strip(): return fetched
    page = 1
    max_pages = max(15, (target_count // 20) + 5)
    while len(fetched) < target_count and page <= max_pages:
        try:
            per_page = min(max(target_count - len(fetched) + 20, 50), 100)
            url = "https://api.openalex.org/works"
            params = {"search": term.strip(), "per_page": per_page, "page": page}
            filter_parts = []
            if min_year: filter_parts.append(f"publication_year:{min_year}-")
            if min_citations > 0: filter_parts.append(f"cited_by_count:>{min_citations - 1}")
            if open_access_only: filter_parts.append("is_oa:true")
            if lang_codes and len(lang_codes) > 0:
                clean_codes = [c.lower().strip() for c in lang_codes if c.lower().strip() != "all"]
                if clean_codes:
                    filter_parts.append(f"language:{'|'.join(clean_codes)}")
            if filter_parts: params["filter"] = ",".join(filter_parts)
                
            resp = requests.get(url, params=params, headers=headers, timeout=8)
            if resp.status_code == 200:
                results_list = resp.json().get("results", [])
                if not results_list: break
                for work in results_list:
                    if len(fetched) >= target_count: break
                    raw_t = work.get("title", "") or ""
                    title = html.unescape(raw_t).strip()
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    doi = work.get("doi", "")
                    if not title or not is_valid_academic_title_fn(title) or is_candidate_duplicate_fn(title, doi): continue
                        
                    year = str(work.get("publication_year", "N/A"))
                    if min_year and year.isdigit() and int(year) < min_year: continue
                            
                    citations_count = work.get("cited_by_count", 0)
                    if min_citations > 0 and citations_count < min_citations: continue
                            
                    loc = work.get("primary_location") or {}
                    is_oa_work = (work.get("open_access") or {}).get("is_oa", False) or loc.get("is_oa", False)
                    if open_access_only and not is_oa_work:
                        continue

                    work_type = (loc.get("source") or {}).get("type") or work.get("type", "")
                    is_preprint_work = work_type == "preprint" or "preprint" in ((loc.get("source") or {}).get("display_name") or "").lower()
                    if exclude_preprints and is_preprint_work:
                        continue

                    landing_url = loc.get("landing_page_url") or doi or f"https://openalex.org/{work.get('id')}"
                    oa_pdf = (work.get("best_oa_location") or {}).get("pdf_url") or loc.get("pdf_url") or ""
                    venue = (loc.get("source") or {}).get("display_name") if loc.get("source") else ""
                    
                    authors = []
                    for auth in work.get("authorships", []):
                        aname = (auth.get("author") or {}).get("display_name")
                        if aname: authors.append(aname.strip())
                            
                    ab_idx = work.get("abstract_inverted_index")
                    abstract = reconstruct_inverted_index(ab_idx)
                    
                    snippet = abstract if abstract else f"Scholarly research published in {venue} ({year})."
                    if not is_matching_topic_fn(title, snippet): continue
                    
                    mark_candidate_seen_fn(title, doi)
                    fetched.append({
                        "title": title,
                        "year": str(year),
                        "doi": doi,
                        "url": landing_url,
                        "snippet": snippet,
                        "authors": authors,
                        "venue": venue,
                        "pdf_url": oa_pdf,
                        "is_oa": is_oa_work
                    })
                page += 1
            else:
                break
        except Exception as e:
            import logging
            logger = logging.getLogger("uvicorn.error")
            logger.warning(f"OpenAlex API err: {e}")
            break
    return fetched