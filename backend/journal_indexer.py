import os
import re
import json
import sqlite3
from typing import Optional, Dict, Any, List

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "journal_index.db"))

def init_journal_db():
    """Initializes the SQLite database for Scopus, SCImago, and SINTA indexing."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journals (
            issn TEXT PRIMARY KEY,
            title TEXT,
            quartile TEXT,
            sjr_score REAL,
            h_index INTEGER,
            publisher TEXT,
            indexing_type TEXT,
            country TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_title ON journals (title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_quartile ON journals (quartile)")
    
    # Check if DB has entries
    cursor.execute("SELECT COUNT(*) FROM journals")
    count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return count

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
    2. Queries SCImago / Scopus Master database by exact ISSN / eISSN.
    3. Falls back to normalized title matching.
    4. Evaluates Indonesian SINTA accreditation.
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

    # 4. Scopus / SCImago Empirical Database Lookup by ISSN
    clean_issns = [clean_issn(x) for x in (issn_list or []) if x]
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Match by ISSN
            for issn in clean_issns:
                if not issn: continue
                cursor.execute("SELECT quartile, sjr_score, h_index, publisher, indexing_type FROM journals WHERE issn = ?", (issn,))
                row = cursor.fetchone()
                if row:
                    q, sjr, h, pub, idx_type = row
                    conn.close()
                    label = f"Scopus {q} (SJR)" if idx_type == "Scopus" else (idx_type or "Indexed Journal")
                    return {
                        "journal_metric": label,
                        "quartile": q,
                        "sjr_score": sjr,
                        "h_index": h,
                        "publisher": pub,
                        "indexing_type": idx_type or "Scopus",
                        "is_conference": False,
                        "is_preprint": False,
                        "quality_tier": 1 if q == "Q1" else (2 if q == "Q2" else (3 if q == "Q3" else 4))
                    }
                    
            # Match by Normalized Title
            if j_norm:
                cursor.execute("SELECT quartile, sjr_score, h_index, publisher, indexing_type FROM journals WHERE lower(title) = ? LIMIT 1", (j_title_clean.lower(),))
                row = cursor.fetchone()
                if row:
                    q, sjr, h, pub, idx_type = row
                    conn.close()
                    label = f"Scopus {q} (SJR)" if idx_type == "Scopus" else (idx_type or "Indexed Journal")
                    return {
                        "journal_metric": label,
                        "quartile": q,
                        "sjr_score": sjr,
                        "h_index": h,
                        "publisher": pub,
                        "indexing_type": idx_type or "Scopus",
                        "is_conference": False,
                        "is_preprint": False,
                        "quality_tier": 1 if q == "Q1" else (2 if q == "Q2" else (3 if q == "Q3" else 4))
                    }
            conn.close()
        except Exception as e:
            pass

    # 5. Default Peer-Reviewed / Open Access
    return {
        "journal_metric": "Peer-Reviewed Journal",
        "quartile": "Q4",
        "indexing_type": "Peer-Reviewed",
        "is_conference": False,
        "is_preprint": False,
        "quality_tier": 4
    }
