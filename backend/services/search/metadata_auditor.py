import json
import logging
from typing import List
from utils.text_processing import (
    clean_academic_abstract,
    is_valid_abstract_content,
    is_ai_synthesized_overview,
    extract_json_from_llm,
)
import journal_indexer

logger = logging.getLogger("uvicorn.error")

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
    try:
        from rag.engine import get_fast_llm, get_main_llm
        active_llm = get_fast_llm() or get_main_llm()
        if active_llm:
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
            res = active_llm.complete(prompt)
            if res and res.text:
                clean_json_str = extract_json_from_llm(res.text)
                parsed = json.loads(clean_json_str)
                if parsed.get("abstract"):
                    if is_ai_synthesized_overview(parsed.get("abstract")):
                        parsed["abstract_type"] = "ai_summary"
                    elif is_valid_abstract_content(parsed.get("abstract")):
                        if not parsed.get("abstract_type"):
                            parsed["abstract_type"] = "official"
                    return parsed
    except Exception as e:
        logger.debug(f"[AI Auditor] Audit failed for '{paper_title}': {e}")

    # Fallback to empirical journal indexing resolver
    venue_type = "journal"
    j_low = (raw_journal or "").lower()
    if any(p in j_low for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf", "repec", "research square", "preprint"]):
        venue_type = "preprint"
    elif any(c in j_low for c in ["conference", "proceedings", "symposium", "workshop", "congress"]):
        venue_type = "conference"

    idx_info = journal_indexer.lookup_journal_index(journal_title=raw_journal, venue_type=venue_type)
    metric = idx_info.get("journal_metric")
    if not metric or metric == "Peer-Reviewed Journal":
        metric = "Open Access Journal" if is_oa else "Peer-Reviewed Publication"

    return {
        "title": paper_title,
        "authors": raw_authors,
        "year": raw_year,
        "journal": raw_journal or "Peer-reviewed Publication",
        "journal_metric": metric,
        "abstract": clean_academic_abstract(raw_abstract_or_html),
        "abstract_type": "official" if is_valid_abstract_content(raw_abstract_or_html) else "ai_summary"
    }
