import os
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
import csv
import hashlib
import io
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from utils.network_utils import is_safe_external_url
from services.search.scopus_source_list import parse_scopus_source_list

logger = logging.getLogger("uvicorn.error")

OPENJOURNALS_CSV_URL = "https://raw.githubusercontent.com/LukasRoeseler/openjournals/main/scimagojr_2024.csv"
SCOPUS_CONTENT_URL = "https://www.elsevier.com/products/scopus/content"
MAX_SCOPUS_CSV_BYTES = 32 * 1024 * 1024
MAX_SOURCE_PAGE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_WORKBOOK_BYTES = 64 * 1024 * 1024


class SourceListLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._anchor_href = None
        self._anchor_text = ""
        self.href = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            values = dict(attrs)
            self._anchor_href = values.get("href")
            self._anchor_text = ""

    def handle_data(self, data):
        if self._anchor_href:
            self._anchor_text += data

    def handle_endtag(self, tag):
        if tag != "a" or not self._anchor_href:
            return
        if "download the source title list" in self._anchor_text.lower():
            self.href = self._anchor_href
        self._anchor_href = None
        self._anchor_text = ""


def _read_limited(response, limit: int) -> bytes:
    body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"Scopus source download exceeded {limit} bytes")
    return body


def _current_source_workbook(opener) -> tuple[bytes, str]:
    page_request = urllib.request.Request(SCOPUS_CONTENT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(page_request, timeout=30.0) as response:
        page = _read_limited(response, MAX_SOURCE_PAGE_BYTES).decode("utf-8", errors="replace")
    parser = SourceListLinkParser()
    parser.feed(page)
    if not parser.href:
        raise ValueError("Elsevier page did not expose its official Scopus source title list")
    source_url = urllib.parse.urljoin(SCOPUS_CONTENT_URL, parser.href)
    parsed = urllib.parse.urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname != "downloads.ctfassets.net":
        raise ValueError("Elsevier source list link did not use the official download host")
    if not is_safe_external_url(source_url):
        raise ValueError("Elsevier source list URL failed outbound URL validation")
    workbook_request = urllib.request.Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(workbook_request, timeout=60.0) as response:
        workbook = _read_limited(response, MAX_SOURCE_WORKBOOK_BYTES)
    if not workbook.startswith(b"PK\x03\x04"):
        raise ValueError("Elsevier source-list download was not an XLSX workbook")
    return workbook, source_url


def _compile_index(db_path: str, csv_bytes: bytes, workbook_bytes: bytes, source_url: str) -> bool:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    tmp_db_path = db_path + ".tmp"
    if os.path.exists(tmp_db_path):
        try:
            os.remove(tmp_db_path)
        except Exception:
            pass

    try:
        source_list = parse_scopus_source_list(workbook_bytes)
        csv_text = csv_bytes.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(csv_text), delimiter=";")
        headers = next(reader)
        metric_year = ""
        for header in headers:
            if header.startswith("Total Docs."):
                match = re.search(r"\b(20\d{2})\b", header)
                if match:
                    metric_year = match.group(1)
                    break
        header_indexes = {name: index for index, name in enumerate(headers)}
        required_indexes = ("Issn", "SJR", "SJR Best Quartile", "Title", "Coverage")
        if any(name not in header_indexes for name in required_indexes):
            raise ValueError("SCImago CSV is missing expected indexing columns")

        conn = sqlite3.connect(tmp_db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE scopus_journals (issn TEXT PRIMARY KEY, quartile TEXT, sjr REAL, title TEXT)")
        cur.execute(
            "CREATE TABLE scopus_sources (issn TEXT NOT NULL, source_id TEXT NOT NULL, title TEXT NOT NULL, normalized_title TEXT NOT NULL, source_type TEXT NOT NULL, status TEXT NOT NULL, coverage TEXT NOT NULL, discontinued_flag TEXT NOT NULL, discontinued_event TEXT NOT NULL, final_coverage_year TEXT NOT NULL, PRIMARY KEY (issn, source_id))"
        )
        cur.execute("CREATE INDEX idx_scopus_sources_normalized_title ON scopus_sources(normalized_title)")
        cur.execute("CREATE INDEX idx_scopus_sources_source_id ON scopus_sources(source_id)")
        cur.execute("CREATE TABLE scopus_manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

        rows = []
        for row in reader:
            if len(row) <= max(header_indexes[name] for name in required_indexes):
                continue
            quartile = row[header_indexes["SJR Best Quartile"]].strip()
            quartile = quartile if quartile and quartile != "-" else None
            sjr_text = row[header_indexes["SJR"]].strip().replace(",", ".")
            try:
                sjr = float(sjr_text) if sjr_text else None
            except ValueError:
                sjr = None
            if quartile is None and sjr is None:
                continue
            title = row[header_indexes["Title"]].strip()
            for raw_issn in row[header_indexes["Issn"]].split(","):
                issn = raw_issn.strip().replace("-", "").upper()
                if len(issn) == 8:
                    rows.append((issn, quartile, sjr, title))

        cur.executemany("INSERT OR REPLACE INTO scopus_journals VALUES (?, ?, ?, ?)", rows)
        source_rows = [
            (
                record.issn,
                record.source_id,
                record.title,
                " ".join(re.sub(r"[^a-zA-Z0-9\s]", "", record.title).lower().split()),
                record.source_type,
                record.status,
                record.coverage,
                record.discontinued_flag,
                record.discontinued_event,
                record.final_coverage_year,
            )
            for record in source_list.records
        ]
        cur.executemany("INSERT OR REPLACE INTO scopus_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", source_rows)
        manifest = {
            "source_list_snapshot": source_list.snapshot,
            "source_list_url": source_url,
            "source_list_sha256": hashlib.sha256(workbook_bytes).hexdigest(),
            "scimago_source_url": OPENJOURNALS_CSV_URL,
            "scimago_source_sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "scimago_metric_year": metric_year,
            "compiled_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        cur.executemany("INSERT INTO scopus_manifest VALUES (?, ?)", manifest.items())
        conn.commit()
        conn.close()

        os.replace(tmp_db_path, db_path)
        logger.info(
            "[Scopus Indexer] Compiled %s SJR records and %s official source ISSNs from snapshot %s.",
            len(rows),
            len(source_rows),
            source_list.snapshot,
        )
        return True
    except Exception as e:
        logger.warning(f"[Scopus Indexer] Failed to compile current Scopus source list: {e}")
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except Exception:
                pass
        return False

class SafeExternalRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_safe_external_url(newurl):
            logger.warning(f"[SSRF Guard] Blocked Scopus index redirect to unsafe URL: {newurl}")
            raise urllib.error.HTTPError(req.full_url, code, "Blocked unsafe redirect", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def build_scopus_index_db(db_path: str) -> bool:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    try:
        req = urllib.request.Request(OPENJOURNALS_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
        opener = urllib.request.build_opener(SafeExternalRedirectHandler())
        with opener.open(req, timeout=30.0) as resp:
            csv_bytes = _read_limited(resp, MAX_SCOPUS_CSV_BYTES)
        workbook_bytes, source_url = _current_source_workbook(opener)
        return _compile_index(db_path, csv_bytes, workbook_bytes, source_url)
    except Exception as e:
        logger.warning(f"[Scopus Indexer] Failed to download current Scopus reference data: {e}")
        return False
