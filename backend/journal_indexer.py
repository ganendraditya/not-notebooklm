import os
import re
import sqlite3
import logging
from typing import Optional, Dict, Any, List
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("uvicorn.error")

SCOPUS_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "scopus_index.db"))

def init_journal_db():
    """No-op stub for backward compatibility."""
    return 0

def clean_issn(raw_issn: str) -> str:
    """Normalizes ISSN format into 8-digit uppercase (e.g. '0162-8828' or '01628828' -> '0162-8828')."""
    if not raw_issn:
        return ""
    digits = re.sub(r'[^0-9xX]', '', str(raw_issn).strip()).upper()
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return digits

def clean_issn_digits(raw_issn: str) -> str:
    """Extracts raw 8-digit uppercase alphanumeric string without hyphens."""
    if not raw_issn:
        return ""
    digits = re.sub(r'[^0-9xX]', '', str(raw_issn).strip()).upper()
    return digits if len(digits) == 8 else ""

def normalize_title(title: str) -> str:
    """Normalizes journal title for matching."""
    if not title:
        return ""
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', title).lower()
    return " ".join(clean.split())

_SCOPUS_INIT_TRIGGERED = False

def lookup_scopus_db(clean_digits: str) -> Optional[Dict[str, Any]]:
    """Fast deterministic lookup (<0.1ms) against local SQLite Scopus Master DB."""
    global _SCOPUS_INIT_TRIGGERED
    if not clean_digits:
        return None
    if not os.path.exists(SCOPUS_DB_PATH):
        if not _SCOPUS_INIT_TRIGGERED:
            _SCOPUS_INIT_TRIGGERED = True
            try:
                from services.search.scopus_compiler import build_scopus_index_db
                build_scopus_index_db(SCOPUS_DB_PATH)
            except Exception as e:
                logger.debug(f"[Scopus Init Trigger Error]: {e}")
        if not os.path.exists(SCOPUS_DB_PATH):
            return None
    try:
        conn = sqlite3.connect(SCOPUS_DB_PATH, timeout=5.0)
        cur = conn.cursor()
        cur.execute("SELECT quartile, sjr, title FROM scopus_journals WHERE issn = ?", (clean_digits,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            q = str(row[0]).strip().upper()
            sjr = float(row[1]) if row[1] is not None else 0.0
            return {
                "quartile": q,
                "sjr": sjr,
                "title": row[2] or ""
            }
    except Exception as e:
        logger.debug(f"[Scopus Lookup Error]: {e}")
    return None

def lookup_sinta_live(clean_digits: str) -> Optional[Dict[str, Any]]:
    """
    Live official SINTA resolution from sinta.kemdiktisaintek.go.id with persistent DB caching.
    Free, keyless, and reflects official SK Akreditasi Kementerian.
    """
    if not clean_digits or len(clean_digits) != 8:
        return None

    # 1. Check local persistent database cache
    try:
        from database import SessionLocal, SintaJournalCache
        db = SessionLocal()
        cached = db.query(SintaJournalCache).filter(SintaJournalCache.issn == clean_digits).first()
        if cached:
            res = {
                "tier": cached.tier,
                "is_scopus": cached.is_scopus,
                "journal_name": cached.journal_name or ""
            }
            db.close()
            return res if cached.tier else None
        db.close()
    except Exception as e:
        logger.debug(f"[SINTA Cache Check Error]: {e}")

    # 2. Query live official ministry portal
    url = f"https://sinta.kemdiktisaintek.go.id/journals?q={clean_digits}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=3.0)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            item = soup.select_one(".list-item")
            tier_found = None
            is_scopus_indexed = False
            journal_name = ""

            if item:
                title_elem = item.select_one(".affil-name a")
                if title_elem:
                    journal_name = title_elem.get_text(strip=True)
                
                text = item.get_text(separator=" | ", strip=True)
                m = re.search(r"\b(S[1-6])\s*\|\s*Accredited", text)
                if m:
                    tier_found = f"{m.group(1)} Accredited"
                    is_scopus_indexed = "Scopus" in text and "Indexed" in text

            # Cache the result in DB
            try:
                from database import SessionLocal, SintaJournalCache, commit_with_retry
                db_write = SessionLocal()
                new_entry = SintaJournalCache(
                    issn=clean_digits,
                    journal_name=journal_name,
                    tier=tier_found,
                    is_scopus=is_scopus_indexed
                )
                db_write.merge(new_entry)
                commit_with_retry(db_write)
                db_write.close()
            except Exception as ce:
                logger.debug(f"[SINTA Cache Write Error]: {ce}")

            if tier_found:
                return {
                    "tier": tier_found,
                    "is_scopus": is_scopus_indexed,
                    "journal_name": journal_name
                }
    except Exception as e:
        logger.debug(f"[SINTA Live Fetch Error for {clean_digits}]: {e}")

    return None

def lookup_journal_index(
    issn_list: Optional[List[str]] = None,
    journal_title: str = "",
    venue_type: str = "journal",
    publisher: str = ""
) -> Dict[str, Any]:
    """
    Deterministic Scholarly Index Resolver:
    1. Distinguishes Preprints vs Conference Proceedings vs Periodical Journals.
    2. Exact Scopus Q1-Q4 & SJR resolution via local Scopus Master DB.
    3. Official Indonesian SINTA S1-S6 accreditation via live ministry portal + cache.
    4. Deterministic fallback to 'Peer-Reviewed Journal' without hallucination.
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

    # Extract all candidate 8-digit ISSNs from the list
    candidate_issns = []
    if issn_list:
        for raw in issn_list:
            digits = clean_issn_digits(raw)
            if digits and digits not in candidate_issns:
                candidate_issns.append(digits)

    # 3. Deterministic Scopus Master Database Lookup
    for digits in candidate_issns:
        scopus_match = lookup_scopus_db(digits)
        if scopus_match and scopus_match.get("quartile"):
            q = scopus_match["quartile"]
            sjr = scopus_match["sjr"]
            tier_num = 1 if q == "Q1" else (2 if q == "Q2" else (3 if q == "Q3" else 4))
            return {
                "journal_metric": f"Scopus {q} (SJR: {sjr:.2f})" if sjr > 0 else f"Scopus {q}",
                "quartile": q,
                "sjr": sjr,
                "indexing_type": "Scopus",
                "is_conference": False,
                "is_preprint": False,
                "quality_tier": tier_num
            }

    # 4. Indonesian SINTA National Accreditation Lookup (Live + Cache)
    # Check if venue name or publisher indicates an Indonesian publication or check all candidate ISSNs
    for digits in candidate_issns:
        sinta_match = lookup_sinta_live(digits)
        if sinta_match and sinta_match.get("tier"):
            tier_str = sinta_match["tier"]  # e.g. "S1 Accredited"
            raw_q = tier_str.split()[0]      # "S1"
            q_num = 1 if raw_q == "S1" else (2 if raw_q == "S2" else 3)
            return {
                "journal_metric": tier_str,
                "quartile": raw_q,
                "sinta_tier": raw_q,
                "indexing_type": "SINTA",
                "is_conference": False,
                "is_preprint": False,
                "quality_tier": q_num
            }

    # 5. Default Peer-Reviewed Journal fallback (No LLM hallucinations)
    return {
        "journal_metric": "Peer-Reviewed Journal",
        "quartile": None,
        "indexing_type": "Peer-Reviewed",
        "is_conference": False,
        "is_preprint": False,
        "quality_tier": 4
    }
