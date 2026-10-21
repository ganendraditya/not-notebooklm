"""Compare legacy-style, SJR-map, and current-list indexing on status-aware cases."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_environment import load_backend_environment

load_backend_environment()

from benchmark_indexing_50 import SINTA_SEED, matches as legacy_match  # noqa: E402
import journal_indexer  # noqa: E402
from database import SintaJournalCache, SessionLocal  # noqa: E402


SEED = 20261013
SINTA_CASE_COUNT = 10
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 45
MINIMUM_REQUEST_INTERVAL_SECONDS = 3.2


def _years(coverage: str) -> list[int]:
    return [int(value) for value in re.findall(r"\b20\d{2}\b", coverage or "")]


def _display_issn(digits: str) -> str:
    return f"{digits[:4]}-{digits[4:]}"


def _sample(rows: list[dict], count: int, offset: int) -> list[dict]:
    if len(rows) < count:
        raise RuntimeError(f"Need {count} benchmark cases, found {len(rows)}")
    return random.Random(SEED + offset).sample(
        sorted(rows, key=lambda row: (row.get("source_id") or "", row.get("issn") or row.get("issns", [""])[0])),
        count,
    )


def _source_records() -> list[dict]:
    with journal_indexer.sqlite3.connect(journal_indexer.SCOPUS_DB_PATH) as connection:
        rows = connection.execute(
            "SELECT source_id, title, issn, source_type, status, coverage, final_coverage_year "
            "FROM scopus_sources ORDER BY source_id, issn"
        ).fetchall()
        metrics = {
            row[0]: {"quartile": row[1], "sjr": row[2]}
            for row in connection.execute("SELECT issn, quartile, sjr FROM scopus_journals")
        }

    grouped: dict[str, dict] = {}
    for source_id, title, issn, source_type, status, coverage, final_year in rows:
        if (source_type or "").strip().lower() != "journal":
            continue
        source = grouped.setdefault(source_id, {
            "source_id": source_id,
            "title": title,
            "status": status,
            "source_type": source_type,
            "coverage": coverage,
            "final_coverage_year": final_year,
            "issns": [],
        })
        if issn and issn not in source["issns"]:
            source["issns"].append(issn)

    records = []
    for source in grouped.values():
        source["issns"].sort(key=lambda issn: (issn not in metrics, issn))
        source["issn"] = source["issns"][0]
        source["metric"] = metrics.get(source["issn"])
        years = _years(source["coverage"])
        source["max_coverage_year"] = max(years) if years else None
        match = journal_indexer.lookup_scopus_source([source["issn"]], source["title"])
        if match.get("status") != source["status"]:
            continue
        records.append(source)
    return records


def _fresh_sinta_cache() -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    seed_issns = {seed["issn"].replace("-", "") for seed in SINTA_SEED}
    records = {}
    with SessionLocal() as session:
        rows = (
            session.query(
                SintaJournalCache.issn,
                SintaJournalCache.journal_name,
                SintaJournalCache.tier,
                SintaJournalCache.updated_at,
            )
            .filter(SintaJournalCache.issn.in_(seed_issns), SintaJournalCache.tier.isnot(None))
            .all()
        )
    for issn, name, tier, updated in rows:
        if updated is None:
            continue
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if now - updated > journal_indexer.SINTA_CACHE_TTL:
            continue
        records[issn] = {
            "tier": tier,
            "is_scopus": False,
            "journal_name": name or "",
            "updated_at": updated.isoformat(),
        }
    return records


def build_cases() -> tuple[list[dict], dict[str, dict]]:
    records = _source_records()
    discontinued = [row for row in records if row["status"] == "discontinued" and row["metric"]]
    inactive = [row for row in records if row["status"] == "inactive" and row["metric"]]
    active_old = [
        row for row in records
        if row["status"] == "active" and row["metric"] and row["max_coverage_year"] is not None
        and row["max_coverage_year"] <= 2024
    ]
    active_recent = [
        row for row in records
        if row["status"] == "active" and row["metric"] and row["max_coverage_year"] is not None
        and row["max_coverage_year"] >= 2025
    ]
    active_without_sjr = [
        row for row in records
        if row["status"] == "active" and row["metric"] is None and row["max_coverage_year"] is not None
        and row["max_coverage_year"] >= 2025
    ]

    selected = []
    for kind, rows, count, offset in (
        ("discontinued", discontinued, 10, 1),
        ("inactive", inactive, 5, 2),
        ("active_old_coverage", active_old, 10, 3),
        ("active_recent_coverage", active_recent, 8, 4),
        ("active_without_sjr", active_without_sjr, 2, 5),
    ):
        for row in _sample(rows, count, offset):
            selected.append({
                "kind": kind,
                "journal": row["title"],
                "issns": [_display_issn(row["issn"])],
                "venue_type": "journal",
                "expected_scopus_status": row["status"],
                "expected_scopus_active": row["status"] == "active",
                "expected_sinta_tier": None,
                "source_id": row["source_id"],
                "coverage": row["coverage"],
                "final_coverage_year": row["final_coverage_year"],
                "historical_sjr_quartile": row["metric"]["quartile"] if row["metric"] else None,
            })

    metrics_without_current_source = []
    with journal_indexer.sqlite3.connect(journal_indexer.SCOPUS_DB_PATH) as connection:
        metric_rows = connection.execute(
            "SELECT issn, title, quartile FROM scopus_journals ORDER BY issn"
        ).fetchall()
    for issn, title, quartile in metric_rows:
        normalized_title = (title or "").lower()
        if any(word in normalized_title for word in ("conference", "proceedings", "symposium", "workshop", "lecture notes")):
            continue
        if journal_indexer.lookup_scopus_source([issn], title).get("status") == "unlisted":
            metrics_without_current_source.append({
                "source_id": f"unlisted-{issn}",
                "issn": issn,
                "journal": title,
                "quartile": quartile,
            })
    for row in _sample(metrics_without_current_source, 5, 6):
        selected.append({
            "kind": "historical_sjr_unlisted_in_current_list",
            "journal": row["journal"],
            "issns": [_display_issn(row["issn"])],
            "venue_type": "journal",
            "expected_scopus_status": "unlisted",
            "expected_scopus_active": False,
            "expected_sinta_tier": None,
            "source_id": row["source_id"],
            "coverage": "",
            "final_coverage_year": None,
            "historical_sjr_quartile": row["quartile"],
        })

    sinta_cache = _fresh_sinta_cache()
    sinta_cases = []
    for seed in SINTA_SEED:
        digits = seed["issn"].replace("-", "")
        cached = sinta_cache.get(digits)
        if not cached:
            continue
        source = journal_indexer.lookup_scopus_source([digits], seed["journal"])
        if source.get("status") in {"unknown", "ambiguous"}:
            continue
        tier_match = re.search(r"\bS[1-6]\b", cached["tier"].upper())
        if not tier_match:
            continue
        sinta_cases.append({
            "kind": "sinta_accredited",
            "journal": cached["journal_name"] or seed["journal"],
            "issns": [_display_issn(digits)],
            "venue_type": "journal",
            "expected_scopus_status": source["status"],
            "expected_scopus_active": source["status"] == "active",
            "expected_sinta_tier": tier_match.group(0),
            "source_id": source.get("source_id"),
            "coverage": source.get("coverage", ""),
            "final_coverage_year": source.get("last_coverage_year"),
            "sinta_cache_updated_at": cached["updated_at"],
            "historical_sjr_quartile": None,
        })
    selected.extend(_sample(sinta_cases, SINTA_CASE_COUNT, 7))

    for index, case in enumerate(selected, start=1):
        case["id"] = index
    if len(selected) != 50:
        raise RuntimeError(f"Status benchmark expected 50 cases, generated {len(selected)}")
    return selected, sinta_cache


def _v1_map() -> dict[str, dict]:
    with journal_indexer.sqlite3.connect(journal_indexer.SCOPUS_DB_PATH) as connection:
        return {
            issn: {"quartile": quartile, "sjr": sjr}
            for issn, quartile, sjr in connection.execute(
                "SELECT issn, quartile, sjr FROM scopus_journals WHERE quartile IS NOT NULL"
            )
        }


def _run_v1(case: dict, metrics: dict[str, dict], sinta_cache: dict[str, dict]) -> dict:
    for raw_issn in case["issns"]:
        digits = journal_indexer.clean_issn_digits(raw_issn)
        hit = metrics.get(digits)
        if hit:
            return {"output": f"Scopus {hit['quartile']}", "status": "ok"}
    for raw_issn in case["issns"]:
        digits = journal_indexer.clean_issn_digits(raw_issn)
        record = sinta_cache.get(digits)
        if record and record.get("tier"):
            return {"output": record["tier"], "status": "ok"}
    return {"output": "Peer-Reviewed Journal", "status": "ok"}


def _run_v2(case: dict, sinta_cache: dict[str, dict]) -> dict:
    started = time.perf_counter()
    original_read = journal_indexer._read_sinta_cache
    original_status = journal_indexer.lookup_sinta_status

    def read_cache(issn):
        return sinta_cache.get(issn)

    def lookup_status(issn):
        record = sinta_cache.get(issn)
        if record and record.get("tier"):
            return {"status": "accredited", "record": record}
        return {"status": "unknown", "record": None}

    journal_indexer._read_sinta_cache = read_cache
    journal_indexer.lookup_sinta_status = lookup_status
    try:
        result = journal_indexer.lookup_journal_index(
            issn_list=case["issns"],
            journal_title=case["journal"],
            venue_type=case["venue_type"],
        )
    finally:
        journal_indexer._read_sinta_cache = original_read
        journal_indexer.lookup_sinta_status = original_status
    return {
        "output": result["journal_metric"],
        "status": "ok",
        "latency_ms": (time.perf_counter() - started) * 1000,
        "scopus_status": result.get("scopus_status"),
        "sinta_status": result.get("sinta_status"),
        "historical_sjr_quartile": result.get("historical_sjr_quartile"),
        "historical_sjr_year": result.get("historical_sjr_year"),
    }


def _has_active_scopus_claim(output: str) -> bool:
    return bool(re.search(r"\bSCOPUS\s+(?:Q[1-4]\b|INDEXED\b)", (output or "").upper()))


def _sinta_tier_claim(output: str) -> str | None:
    text = (output or "").upper()
    match = re.search(r"\bSINTA\s+S?([1-6])\b", text)
    if match:
        return f"S{match.group(1)}"
    match = re.search(r"\b(S[1-6])\s+ACCREDITED\b", text)
    return match.group(1) if match else None


def _status_correct(case: dict, run: dict) -> bool | None:
    if run.get("status") != "ok":
        return None
    output = run.get("output") or ""
    if _has_active_scopus_claim(output) != case["expected_scopus_active"]:
        return False
    expected_sinta = case.get("expected_sinta_tier")
    return expected_sinta is None or _sinta_tier_claim(output) == expected_sinta


def _legacy_sinta_scores(case: dict, output: str) -> dict:
    tier = case.get("expected_sinta_tier")
    if not tier:
        return {}
    original = legacy_match(f"SINTA {tier[1:]}", output)
    normalized = re.sub(r"\bSINTA\s+([1-6])\b", r"S\1", output, flags=re.IGNORECASE)
    return {
        "original_sinta_match": original,
        "sinta_alias_normalized_match": legacy_match(f"SINTA {tier[1:]}", normalized),
    }


def _legacy_prompt(case: dict) -> str:
    return f"""You are an expert Senior Academic Research Indexer and Metadata Auditor.

Candidate Journal: {case['journal']}
Publication Year: 2026

Indexing & reputation rules:
- Indonesian national journals: identify current SINTA accreditation and tier.
- International peer-reviewed journals: use your scholarly knowledge. Top-tier is Scopus Q1 (SJR), high-tier Q2, mid-tier Q3, and regular indexed Q4 / Indexed.
- Do not infer a conference or preprint classification; all candidates here are journals.

Return only JSON with this shape: {{"journal_metric": "..."}}"""


def _run_groq(case: dict, api_key: str) -> dict:
    started = time.perf_counter()
    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": _legacy_prompt(case)}],
            "temperature": 0.1,
            "max_tokens": 4096,
            "reasoning_effort": "low",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    latency = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        return {"output": "", "status": "error", "error": f"http_{response.status_code}", "latency_ms": latency}
    payload = response.json()
    text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", text or "", re.DOTALL)
        try:
            parsed = json.loads(match.group(0)) if match else {}
        except json.JSONDecodeError:
            parsed = {}
    output = parsed.get("journal_metric") if isinstance(parsed, dict) else None
    usage = payload.get("usage") or {}
    if not isinstance(output, str) or not output.strip():
        return {
            "output": text[:500] if isinstance(text, str) else "",
            "status": "error",
            "error": "invalid_metric_response",
            "latency_ms": latency,
            "usage": usage,
        }
    return {
        "output": output.strip(),
        "status": "ok",
        "latency_ms": latency,
        "usage": usage,
    }


def _score_report(cases: list[dict], runs: dict[str, list[dict]]) -> dict:
    scorecard = {}
    for version, outputs in runs.items():
        scored = [
            _status_correct(case, run)
            for case, run in zip(cases, outputs)
        ]
        valid = [value for value in scored if value is not None]
        scorecard[version] = {
            "correct": sum(value is True for value in valid),
            "evaluated": len(valid),
            "accuracy": sum(value is True for value in valid) / len(valid) if valid else None,
            "errors": sum(run.get("status") != "ok" for run in outputs),
        }
        by_kind = {}
        for case, run, result in zip(cases, outputs, scored):
            item = by_kind.setdefault(case["kind"], {"correct": 0, "evaluated": 0})
            if result is not None:
                item["evaluated"] += 1
                item["correct"] += result is True
        scorecard[version]["by_kind"] = by_kind

    legacy_sinta = {}
    for version, outputs in runs.items():
        sinta_cases = [
            _legacy_sinta_scores(case, run.get("output", ""))
            for case, run in zip(cases, outputs)
            if case.get("expected_sinta_tier")
        ]
        legacy_sinta[version] = {
            "cases": len(sinta_cases),
            "original_match_count": sum(item.get("original_sinta_match", False) for item in sinta_cases),
            "alias_normalized_match_count": sum(item.get("sinta_alias_normalized_match", False) for item in sinta_cases),
        }
    return {"scorecard": scorecard, "legacy_sinta_matchers": legacy_sinta}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true", help="Run deterministic V1/V2 comparisons without Groq")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases, sinta_cache = build_cases()
    v1_metrics = _v1_map()
    runs = {
        "v1_sjr_map": [_run_v1(case, v1_metrics, sinta_cache) for case in cases],
        "v2_current_source_list": [_run_v2(case, sinta_cache) for case in cases],
    }

    groq_meta = None
    if not args.skip_llm:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise SystemExit("Groq run blocked: configure GROQ_API_KEY in the local environment; no other provider will be used.")
        host = urlparse(GROQ_URL).hostname
        groq_runs = []
        for index, case in enumerate(cases):
            groq_runs.append(_run_groq(case, api_key))
            print(f"Groq {index + 1}/{len(cases)}", flush=True)
            if index + 1 < len(cases):
                time.sleep(MINIMUM_REQUEST_INTERVAL_SECONDS)
        runs = {"v0_legacy_prompt_proxy": groq_runs, **runs}
        groq_meta = {
            "provider": "Groq",
            "model": GROQ_MODEL,
            "host": host,
            "temperature": 0.1,
            "reasoning_effort": "low",
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "minimum_request_interval_seconds": MINIMUM_REQUEST_INTERVAL_SECONDS,
            "calls": len(groq_runs),
            "credential_written": False,
        }

    with journal_indexer.sqlite3.connect(journal_indexer.SCOPUS_DB_PATH) as connection:
        manifest = dict(connection.execute("SELECT key, value FROM scopus_manifest"))
    encoded_cases = json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_mode": "deterministic_only" if args.skip_llm else "groq_and_deterministic",
        "source_snapshot": manifest.get("source_list_snapshot"),
        "source_list_sha256": manifest.get("source_list_sha256"),
        "scimago_metric_year": manifest.get("scimago_metric_year"),
        "scopus_db_sha256": hashlib.sha256(Path(journal_indexer.SCOPUS_DB_PATH).read_bytes()).hexdigest(),
        "cases_sha256": hashlib.sha256(encoded_cases).hexdigest(),
        "groq": groq_meta,
        "cases": cases,
        "runs": runs,
        **_score_report(cases, runs),
        "notes": [
            "V0 is a legacy-prompt proxy, not a byte-for-byte replay of the historical application pipeline.",
            "Scopus ground truth is the official Elsevier source-list snapshot used by V2; the score measures consistency with that data, not independent accuracy.",
            "SJR quartiles are stored as dated historical metrics.",
            "Fresh positive SINTA labels come from official-portal cache rows inside the configured seven-day TTL.",
            "No live SINTA negative queries are included; uncached portal requests may be unavailable.",
            "The original SINTA matcher and alias-normalized score are reported separately from the status-aware score.",
        ],
    }
    if args.skip_llm:
        report["notes"].append("Groq was not run in deterministic-only mode; configure GROQ_API_KEY locally to run the V0 proxy.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report["scorecard"], indent=2))
    print(json.dumps(report["legacy_sinta_matchers"], indent=2))
    print({"cases": len(cases), "snapshot": report["source_snapshot"], "cases_sha256": report["cases_sha256"]})
    if args.output:
        print(f"report: {args.output}")


if __name__ == "__main__":
    main()
