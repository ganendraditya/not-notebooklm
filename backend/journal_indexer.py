import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from utils.network_utils import is_safe_external_url

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

_SINTA_TIER_RANK = {"S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5, "S6": 6}
SINTA_CACHE_TTL = timedelta(days=7)
SINTA_NEGATIVE_CACHE_TTL = timedelta(minutes=5)
SINTA_MAX_REDIRECTS = 5
HTTP_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
CONFERENCE_VENUE_TYPES = {
    "conference",
    "conference-abstract",
    "conference-article",
    "conference-paper",
    "conference-proceedings",
    "conference-series",
    "proceedings",
    "proceedings-article",
    "proceedings-paper",
    "proceedings-series",
}
PREPRINT_VENUE_TYPES = {"preprint", "preprint-article", "posted-content"}
JOURNAL_VENUE_TYPES = {"journal", "journal-article", "journal-issue", "journal-volume"}
SINTA_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def lookup_scopus_db(clean_digits: str) -> Optional[Dict[str, Any]]:
    """Fast deterministic lookup (<0.1ms) against local SQLite Scopus Master DB."""
    if not clean_digits:
        return None
    if not os.path.exists(SCOPUS_DB_PATH):
        return None
    try:
        with sqlite3.connect(SCOPUS_DB_PATH, timeout=5.0) as conn:
            cur = conn.cursor()
            cur.execute("SELECT quartile, sjr, title FROM scopus_journals WHERE issn = ?", (clean_digits,))
            row = cur.fetchone()
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

    # 1. Fresh cache hit (positive entries live 7 days, misses live 5 minutes)
    cached = _read_sinta_cache(clean_digits)
    if cached is not None:
        return cached if cached.get("tier") else None

    # 2. Live official ministry portal. Only the result row whose ISSN matches the request counts.
    url = f"https://sinta.kemdiktisaintek.go.id/journals?q={clean_digits}"
    try:
        resp = _get_sinta_response(url)
        if resp is None:
            return None
        if resp.status_code != 200:
            logger.debug(f"[SINTA] HTTP {resp.status_code} for {clean_digits}; not caching")
            return None
        parsed = _parse_sinta_result(resp.text, clean_digits)
    except Exception as e:
        logger.debug(f"[SINTA Live Fetch Error for {clean_digits}]: {e}")
        return None

    # A no-result response is cached briefly to avoid repeating the same portal lookup.
    _write_sinta_cache(clean_digits, parsed)
    if not parsed.get("row_found"):
        logger.debug(f"[SINTA] no result row for {clean_digits}; cached as a short-lived miss")
        return None
    return parsed if parsed.get("tier") else None

def _get_sinta_response(url: str) -> Optional[requests.Response]:
    """Follow only redirects whose destinations pass the outbound SSRF guard."""
    for redirect_count in range(SINTA_MAX_REDIRECTS + 1):
        resp = requests.get(
            url,
            headers=SINTA_REQUEST_HEADERS,
            timeout=3.0,
            allow_redirects=False,
        )
        if resp.status_code not in HTTP_REDIRECT_STATUSES:
            return resp

        location = resp.headers.get("Location")
        if not location or redirect_count == SINTA_MAX_REDIRECTS:
            resp.close()
            logger.debug(f"[SINTA] Missing or excessive redirect for {url}")
            return None

        next_url = urljoin(url, location)
        resp.close()
        if not is_safe_external_url(next_url):
            logger.warning(f"[SSRF Guard] Blocked SINTA redirect to unsafe URL: {next_url}")
            return None
        url = next_url

    return None

def _parse_sinta_result(html: str, clean_digits: str) -> Dict[str, Any]:
    """Extracts tier from the SINTA result row that carries the requested ISSN."""
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select(".list-item"):
        text = item.get_text(separator=" | ", strip=True)
        issn_digits = {clean_issn_digits(v) for v in re.findall(r"[0-9]{4}-?[0-9Xx]{4}", text)}
        if clean_digits not in issn_digits:
            continue
        m = re.search(r"\b(S[1-6])\s*\|\s*Accredited", text)
        title_elem = item.select_one(".affil-name a")
        return {
            "row_found": True,
            "tier": f"{m.group(1)} Accredited" if m else None,
            "is_scopus": "Scopus" in text and "Indexed" in text,
            "journal_name": title_elem.get_text(strip=True) if title_elem else "",
        }
    return {"row_found": False, "tier": None, "is_scopus": False, "journal_name": ""}

def _read_sinta_cache(clean_digits: str) -> Optional[Dict[str, Any]]:
    from database import SessionLocal, SintaJournalCache
    try:
        with SessionLocal() as db:
            row = db.query(SintaJournalCache).filter(SintaJournalCache.issn == clean_digits).first()
            if row is None:
                return None
            ttl = SINTA_CACHE_TTL if row.tier else SINTA_NEGATIVE_CACHE_TTL
            updated = row.updated_at
            if updated is not None and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if updated is None or datetime.now(timezone.utc) - updated > ttl:
                return None
            return {"tier": row.tier, "is_scopus": row.is_scopus, "journal_name": row.journal_name or ""}
    except Exception as e:
        logger.debug(f"[SINTA Cache Check Error]: {e}")
        return None

def _write_sinta_cache(clean_digits: str, parsed: Dict[str, Any]) -> None:
    from database import SessionLocal, SintaJournalCache, commit_with_retry, get_utc_now
    try:
        with SessionLocal() as db:
            db.merge(SintaJournalCache(
                issn=clean_digits,
                journal_name=parsed.get("journal_name", ""),
                tier=parsed.get("tier"),
                is_scopus=bool(parsed.get("is_scopus")),
                updated_at=get_utc_now(),
            ))
            commit_with_retry(db)
    except Exception as e:
        logger.debug(f"[SINTA Cache Write Error]: {e}")

def normalize_venue_type(venue_type: str) -> str:
    normalized = re.sub(r"[\s_]+", "-", str(venue_type or "").strip().lower())
    if normalized in PREPRINT_VENUE_TYPES:
        return "preprint"
    if normalized in CONFERENCE_VENUE_TYPES:
        return "conference"
    if normalized in JOURNAL_VENUE_TYPES:
        return "journal"
    return normalized or "journal"

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
    normalized_venue_type = normalize_venue_type(venue_type)

    if normalized_venue_type == "preprint":
        return {
            "journal_metric": "Preprint (Non-Peer-Reviewed)",
            "quartile": None,
            "indexing_type": "Preprint",
            "is_conference": False,
            "is_preprint": True,
            "quality_tier": 0
        }
        
    if normalized_venue_type == "conference":
        return {
            "journal_metric": "Conference Proceedings (Indexed)",
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
    scopus_hit = None
    scopus_digits = ""
    for digits in candidate_issns:
        scopus_match = lookup_scopus_db(digits)
        if scopus_match and scopus_match.get("quartile"):
            scopus_hit = scopus_match
            scopus_digits = digits
            break

    # 4. SINTA national accreditation (live + cache).
    # For Scopus-indexed venues we only read the SINTA cache (no network on the hot path);
    # for unindexed venues we allow the live ministry lookup.
    sinta_tier = None
    if scopus_hit:
        cached_sinta = _read_sinta_cache(scopus_digits)
        if cached_sinta and cached_sinta.get("tier"):
            sinta_tier = cached_sinta["tier"].split()[0]
    else:
        for digits in candidate_issns:
            sinta_match = lookup_sinta_live(digits)
            if sinta_match and sinta_match.get("tier"):
                sinta_tier = sinta_match["tier"].split()[0]  # "S1".."S6"
                break

    if scopus_hit:
        q = scopus_hit["quartile"]
        sjr = scopus_hit["sjr"]
        tier_num = {"Q1": 1, "Q2": 2, "Q3": 3}.get(q, 4)
        metric = f"Scopus {q} (SJR: {sjr:.2f})" if sjr > 0 else f"Scopus {q}"
        if sinta_tier:
            metric = f"{metric} | SINTA {sinta_tier}"
        return {
            "journal_metric": metric,
            "quartile": q,
            "sjr": sjr,
            "sinta_tier": sinta_tier,
            "indexing_type": "Scopus",
            "is_conference": False,
            "is_preprint": False,
            "quality_tier": tier_num
        }

    if sinta_tier:
        return {
            "journal_metric": f"{sinta_tier} Accredited",
            "quartile": sinta_tier,
            "sinta_tier": sinta_tier,
            "indexing_type": "SINTA",
            "is_conference": False,
            "is_preprint": False,
            "quality_tier": _SINTA_TIER_RANK.get(sinta_tier, 4)
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
