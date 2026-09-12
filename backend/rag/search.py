import os
import re
import logging
from typing import List, Optional, Dict, Any

from llama_index.core.llms import LLM
from utils.text_processing import (
    normalize_title_str,
    is_valid_academic_title,
    clean_doi,
)
from providers.academic import fetch_europe_pmc, fetch_openalex, fetch_crossref
from services.search import (
    plan_academic_search,
    judge_and_filter_papers_with_llm,
    audit_paper_metadata_with_ai
)

logger = logging.getLogger("uvicorn.error")

def get_existing_notebook_sources_signatures(chat_id: str) -> dict:
    """
    Scans existing documents in this chat directly from DB and returns
    comprehensive signatures (DOIs, full titles, filenames, token sets)
    to prevent recommending or importing duplicate papers without disk I/O.
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
            if doc.filename:
                filenames.add(doc.filename)
                clean_fn = doc.filename.replace(".pdf", "").replace(".txt", "").strip()
                if clean_fn:
                    titles.add(clean_fn)
            if doc.title:
                titles.add(doc.title.strip())
            if doc.doi:
                c_d = clean_doi(doc.doi).lower()
                if c_d:
                    dois.add(c_d)
    finally:
        db.close()

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
        c_doi = clean_doi(candidate_doi).lower()
        for ex_doi in existing_signatures.get("dois", set()):
            e_doi = clean_doi(ex_doi).lower()
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
            c_doi = clean_doi(doi).lower()
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
            c_doi = clean_doi(doi).lower()
            if c_doi:
                seen_dois.add(c_doi)

    # Build domain-agnostic search keywords from queries and plan
    raw_query_texts = [en_query, id_query, plan.get("native_query", "")]
    core_search_tokens = set()
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "study", "analysis",
        "paper", "journal", "research", "using", "based", "effect", "effects",
        "dan", "dari", "yang", "untuk", "pada", "dalam", "dengan", "studi", "analisis"
    }
    for q_txt in raw_query_texts:
        if q_txt:
            for word in re.findall(r'[a-zA-Z0-9_\-\u00C0-\u024F]+', q_txt.lower()):
                if len(word) >= 3 and word not in stop_words:
                    core_search_tokens.add(word)

    def is_matching_topic_local(title: str, snippet: str) -> bool:
        """
        Domain-agnostic candidate relevance filter.
        Ensures the candidate shares meaningful semantic overlap with the search query.
        Fine-grained ranking and deep relevance is handled by the LLM Judge.
        """
        if not core_search_tokens:
            return True

        cand_text = f"{title} {snippet}".lower()
        cand_words = set(re.findall(r'[a-zA-Z0-9_\-\u00C0-\u024F]+', cand_text))
        
        # Check if candidate shares at least one core search token
        return bool(core_search_tokens.intersection(cand_words))

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
            from flashrank import RerankRequest
            from rag.vector_store import get_flashrank_ranker
            ranker = get_flashrank_ranker()
            if not ranker:
                raise RuntimeError("FlashRank Ranker unavailable")
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
