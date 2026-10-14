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
INDEX_METADATA_FIELDS = (
    "indexing_type",
    "scopus_status",
    "scopus_source_snapshot",
    "scopus_last_coverage_year",
    "historical_sjr_quartile",
    "historical_sjr",
    "historical_sjr_year",
    "sinta_status",
)
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
            manifest_table = cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'scopus_manifest'"
            ).fetchone()
            metric_year_row = None
            if manifest_table:
                metric_year_row = cur.execute(
                    "SELECT value FROM scopus_manifest WHERE key = 'scimago_metric_year'"
                ).fetchone()
        if row:
            q = str(row[0]).strip().upper() if row[0] and str(row[0]).strip() else None
            sjr = float(row[1]) if row[1] is not None else None
            if q is None and sjr is None:
                return None
            return {
                "quartile": q,
                "sjr": sjr,
                "title": row[2] or "",
                "metric_year": metric_year_row[0] if metric_year_row else None,
            }
    except Exception as e:
        logger.debug(f"[Scopus Lookup Error]: {e}")
    return None

def lookup_scopus_source(issn_list: Optional[List[str]] = None, journal_title: str = "") -> Dict[str, Any]:
    if not os.path.exists(SCOPUS_DB_PATH):
        return {"status": "unknown", "source_snapshot": None}
    try:
        with sqlite3.connect(SCOPUS_DB_PATH, timeout=5.0) as conn:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'scopus_sources'"
            ).fetchone()
            if not table:
                return {"status": "unknown", "source_snapshot": None}
            snapshot_row = conn.execute(
                "SELECT value FROM scopus_manifest WHERE key = 'source_list_snapshot'"
            ).fetchone()
            snapshot = snapshot_row[0] if snapshot_row else None
            if not snapshot:
                return {"status": "unknown", "source_snapshot": None}
            rows = []
            seen = set()
            for raw_issn in issn_list or []:
                digits = clean_issn_digits(raw_issn)
                if not digits:
                    continue
                for row in conn.execute(
                    "SELECT issn, source_id, title, source_type, status, coverage, discontinued_flag, discontinued_event, final_coverage_year "
                    "FROM scopus_sources WHERE issn = ?",
                    (digits,),
                ):
                    key = (row[0], row[1])
                    if key not in seen:
                        seen.add(key)
                        rows.append(row)
            normalized_title = normalize_title(journal_title)
            if not rows and normalized_title:
                rows = conn.execute(
                    "SELECT issn, source_id, title, source_type, status, coverage, discontinued_flag, discontinued_event, final_coverage_year "
                    "FROM scopus_sources WHERE normalized_title = ?",
                    (normalized_title,),
                ).fetchall()
            if not rows:
                return {"status": "unlisted", "source_snapshot": snapshot}

            exact_title = [row for row in rows if normalize_title(row[2]) == normalized_title] if normalized_title else []
            candidates = exact_title or rows
            source_ids = {row[1] for row in candidates}
            statuses = {row[4] for row in candidates}
            if len(source_ids) > 1 or len(statuses) > 1:
                return {"status": "ambiguous", "source_snapshot": snapshot}
            row = candidates[0]
            return {
                "status": row[4],
                "issn": row[0],
                "source_id": row[1],
                "title": row[2],
                "source_type": row[3],
                "coverage": row[5],
                "discontinued_flag": row[6],
                "discontinued_event": row[7],
                "last_coverage_year": row[8],
                "source_snapshot": snapshot,
            }
    except sqlite3.OperationalError as e:
        logger.debug(f"[Scopus Source Lookup Error]: {e}")
        return {"status": "unknown", "source_snapshot": None}
    except Exception as e:
        logger.debug(f"[Scopus Source Lookup Error]: {e}")
        return {"status": "unknown", "source_snapshot": None}

def lookup_sinta_live(clean_digits: str) -> Optional[Dict[str, Any]]:
    """
    Live official SINTA resolution from sinta.kemdiktisaintek.go.id with persistent DB caching.
    Free, keyless, and reflects official SK Akreditasi Kementerian.
    """
    result = lookup_sinta_status(clean_digits)
    return result.get("record") if result.get("status") == "accredited" else None

def lookup_sinta_status(clean_digits: str) -> Dict[str, Any]:
    if not clean_digits or len(clean_digits) != 8:
        return {"status": "unknown", "record": None}

    cached = _read_sinta_cache(clean_digits)
    if cached is not None:
        if cached.get("tier"):
            return {"status": "accredited", "record": cached}
        if cached.get("row_found"):
            return {"status": "listed_without_tier", "record": cached}
        return {"status": "unlisted", "record": None}

    url = f"https://sinta.kemdiktisaintek.go.id/journals?q={clean_digits}"
    try:
        resp = _get_sinta_response(url)
        if resp is None:
            return {"status": "unknown", "record": None}
        if resp.status_code != 200:
            logger.debug(f"[SINTA] HTTP {resp.status_code} for {clean_digits}; not caching")
            return {"status": "unknown", "record": None}
        parsed = _parse_sinta_result(resp.text, clean_digits)
    except Exception as e:
        logger.debug(f"[SINTA Live Fetch Error for {clean_digits}]: {e}")
        return {"status": "unknown", "record": None}

    _write_sinta_cache(clean_digits, parsed)
    if not parsed.get("row_found"):
        logger.debug(f"[SINTA] no result row for {clean_digits}; cached as a short-lived miss")
        return {"status": "unlisted", "record": None}
    if not parsed.get("tier"):
        return {"status": "listed_without_tier", "record": parsed}
    return {"status": "accredited", "record": parsed}

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
            return {
                "tier": row.tier,
                "row_found": row.row_found,
                "is_scopus": row.is_scopus,
                "journal_name": row.journal_name or "",
            }
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
                row_found=bool(parsed.get("row_found")),
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

    # The current Elsevier list decides current Scopus status; SJR metrics remain historical metadata.
    source_match = lookup_scopus_source(candidate_issns, journal_title)
    scopus_status = source_match.get("status", "unknown")
    metric_issns = list(candidate_issns)
    if source_match.get("issn") and source_match["issn"] not in metric_issns:
        metric_issns.insert(0, source_match["issn"])
    historical_match = next(
        (match for digits in metric_issns if (match := lookup_scopus_db(digits))),
        None,
    )
    scopus_active = scopus_status == "active"

    sinta_tier = None
    sinta_status = "unknown"
    if scopus_active:
        for digits in candidate_issns:
            cached_sinta = _read_sinta_cache(digits)
            if cached_sinta and cached_sinta.get("tier"):
                sinta_tier = cached_sinta["tier"].split()[0]
                sinta_status = "accredited"
                break
    else:
        sinta_results = []
        for digits in candidate_issns:
            result = lookup_sinta_status(digits)
            sinta_results.append(result)
            if result.get("status") == "accredited":
                sinta_tier = result["record"]["tier"].split()[0]
                sinta_status = "accredited"
                break
        if not sinta_tier:
            if sinta_results and all(result.get("status") == "unlisted" for result in sinta_results):
                sinta_status = "unlisted"
            elif any(result.get("status") == "listed_without_tier" for result in sinta_results):
                sinta_status = "listed_without_tier"

    historical_quartile = historical_match.get("quartile") if historical_match else None
    historical_sjr = historical_match.get("sjr") if historical_match else None
    historical_sjr_year = historical_match.get("metric_year") if historical_match else None
    last_coverage_year = source_match.get("last_coverage_year") or None
    common = {
        "scopus_status": scopus_status,
        "scopus_source_snapshot": source_match.get("source_snapshot"),
        "scopus_last_coverage_year": last_coverage_year,
        "historical_sjr_quartile": historical_quartile,
        "historical_sjr": historical_sjr,
        "historical_sjr_year": historical_sjr_year,
        "sinta_status": sinta_status,
    }

    metric_parts = []
    if scopus_active:
        metric_parts.append("Scopus Indexed")
        if historical_match and historical_quartile:
            year = f" ({historical_sjr_year})" if historical_sjr_year else ""
            metric_parts.append(f"SJR {historical_quartile}{year}")
    elif scopus_status in {"discontinued", "inactive", "unlisted"}:
        label = "Not indexed in Scopus"
        if scopus_status == "discontinued":
            label = "Not currently indexed in Scopus (discontinued)"
        elif scopus_status == "inactive":
            label = "Not currently indexed in Scopus (inactive)"
        metric_parts.append(label)

    if sinta_tier:
        metric_parts.append(f"SINTA {sinta_tier}")
    if not metric_parts:
        metric_parts.append("Peer-Reviewed Journal")

    if scopus_active:
        quartile = historical_quartile
        indexing_type = "Scopus"
        quality_tier = {"Q1": 1, "Q2": 2, "Q3": 3}.get(quartile, 4)
    elif sinta_tier:
        quartile = sinta_tier
        indexing_type = "SINTA"
        quality_tier = _SINTA_TIER_RANK.get(sinta_tier, 4)
    else:
        quartile = None
        indexing_type = "Peer-Reviewed"
        quality_tier = 4

    return {
        **common,
        "journal_metric": " | ".join(metric_parts),
        "quartile": quartile,
        "sjr": historical_sjr if scopus_active else None,
        "sinta_tier": sinta_tier,
        "indexing_type": indexing_type,
        "is_conference": False,
        "is_preprint": False,
        "quality_tier": quality_tier,
    }
