import os
import re
from typing import Optional, Dict, Any, List

def init_journal_db():
    """No-op stub for backward compatibility; journal reputation is resolved dynamically by AI auditor."""
    return 0

def clean_issn(raw_issn: str) -> str:
    """Normalizes ISSN format (e.g. 0162-8828 or 01628828 -> 0162-8828)."""
    if not raw_issn:
        return ""
    digits = re.sub(r'[^0-9xX]', '', raw_issn.strip()).upper()
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return digits

def normalize_title(title: str) -> str:
    """Normalizes journal title for fuzzy matching."""
    if not title:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', title).lower()
    return " ".join(clean.split())

def lookup_journal_index(
    issn_list: Optional[List[str]] = None,
    journal_title: str = "",
    venue_type: str = "journal",
    publisher: str = ""
) -> Dict[str, Any]:
    """
    Empirical Scholarly Index Resolver:
    1. Distinguishes Conference Proceedings vs Preprints vs Periodical Journals.
    2. Heuristically identifies Indonesian SINTA accredited venues.
    3. Delegates periodical/journal indexing classification to AI research auditor for unbiased global coverage across all disciplines.
    """
    j_title_clean = (journal_title or "").strip()
    j_norm = normalize_title(j_title_clean)
    
    # 1. Preprints (Non-Peer-Reviewed Repositories)
    if venue_type == "preprint" or any(p in j_norm for p in ["sportrxiv", "arxiv", "biorxiv", "medrxiv", "ssrn", "osf preprints", "repec", "research square"]):
        return {
            "journal_metric": "Preprint (Non-Peer-Reviewed)",
            "quartile": None,
            "indexing_type": "Preprint",
            "is_conference": False,
            "is_preprint": True,
            "quality_tier": 0
        }
        
    # 2. Conference Proceedings (Never Scopus Q1-Q4)
    if venue_type == "conference" or any(c in j_norm for c in ["conference", "proceedings", "symposium", "workshop", "congress", "ieee xplore", "icmla", "iccv", "cvpr", "icml", "neurips", "calcon", "icaart"]):
        metric_label = "Conference Proceedings (Indexed)"
        if "ieee" in j_norm:
            metric_label = "IEEE Conference Proceedings"
        elif "acm" in j_norm:
            metric_label = "ACM Conference Proceedings"
        elif "springer" in j_norm or "lncs" in j_norm:
            metric_label = "Springer Proceedings (LNCS)"
        return {
            "journal_metric": metric_label,
            "quartile": None,
            "indexing_type": "Conference Proceedings",
            "is_conference": True,
            "is_preprint": False,
            "quality_tier": 4
        }
        
    # 3. Indonesian SINTA National Journals
    if any(s in j_norm for s in ["sinta", "garuda", "jurnal indonesia", "jurnal nasional", "ilkom", "resti", "matrik", "sisfo", "teknomatika"]):
        sinta_rank = "SINTA Accredited"
        if "resti" in j_norm:
            sinta_rank = "SINTA 2 Accredited"
        elif "ilkom" in j_norm:
            sinta_rank = "SINTA 2 Accredited"
        elif "sisfo" in j_norm or "ultimatics" in j_norm:
            sinta_rank = "SINTA 3 Accredited"
        return {
            "journal_metric": sinta_rank,
            "quartile": "SINTA",
            "indexing_type": "SINTA",
            "is_conference": False,
            "is_preprint": False,
            "quality_tier": 3
        }

    # 4. Default Peer-Reviewed Journal (Detailed quartile & metrics audited by AI auditor)
    return {
        "journal_metric": "Peer-Reviewed Journal",
        "quartile": None,
        "indexing_type": "Peer-Reviewed",
        "is_conference": False,
        "is_preprint": False,
        "quality_tier": 4
    }
