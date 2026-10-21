"""
50-case comparison of a reconstructed V0 baseline, a naive Scopus-map V1, and the current V2 resolver.

Ground truth is derived from the bundled Scopus reference DB (`backend/data/scopus_index.db`),
not hand-typed. Cases are sampled with a fixed seed so the run is reproducible.

Run:
    PYTHONPATH=backend backend/venv/bin/python backend/evaluation/benchmark_indexing_50.py
"""
import os
import sys
import csv
import json
import random
import sqlite3
import time
import re
import urllib.request
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from journal_indexer import lookup_journal_index, lookup_sinta_live, SCOPUS_DB_PATH  # noqa: E402

SEED = 20241011
SCOPUS_SAMPLE_PER_Q = 6          # 4 quartiles x 6 = 24, plus 1 Q1 pad = 25 Scopus cases
SINTA_CASES = 15
NEGATIVE_CASES = 10
SCIMAGO_CSV_URL = "https://raw.githubusercontent.com/LukasRoeseler/openjournals/main/scimagojr_2024.csv"
V1_CSV_PATH = "/tmp/scimagojr_2024.csv"

# SINTA-accredited Indonesian journals harvested live from the SINTA portal, filtered to
# venues absent from the Scopus DB so they exercise the SINTA-only path.
SINTA_SEED = [
    {"issn": "2252-7877", "journal": "Industria: Jurnal Teknologi dan Manajemen Agroindustri", "gt": "SINTA 1"},
    {"issn": "2354-7960", "journal": "PEDAGOGIK : JURNAL PENDIDIKAN", "gt": "SINTA 1"},
    {"issn": "2088-2866", "journal": "Jurnal Pendidikan Vokasi", "gt": "SINTA 1"},
    {"issn": "2355-7699", "journal": "Jurnal Teknologi Informasi dan Ilmu Komputer", "gt": "SINTA 2"},
    {"issn": "1411-2744", "journal": "JTP - Jurnal Teknologi Pendidikan", "gt": "SINTA 2"},
    {"issn": "2338-9184", "journal": "Kwangsan: Jurnal Teknologi Pendidikan", "gt": "SINTA 2"},
    {"issn": "2406-7768", "journal": "JSiI (Jurnal Sistem Informasi)", "gt": "SINTA 3"},
    {"issn": "2622-6901", "journal": "Jurnal Sistem Informasi dan Informatika (SIMIKA)", "gt": "SINTA 3"},
    {"issn": "2302-8149", "journal": "Sistemasi: Jurnal Sistem Informasi", "gt": "SINTA 3"},
    {"issn": "3021-8462", "journal": "Jurnal Komputer dan Elektro Sains", "gt": "SINTA 4"},
    {"issn": "2722-4368", "journal": "JUKI : Jurnal Komputer dan Informatika", "gt": "SINTA 4"},
    {"issn": "2962-3022", "journal": "Jurnal Komputer Teknologi Informasi Sistem Komputer (JUKTISI)", "gt": "SINTA 4"},
    {"issn": "2580-4316", "journal": "IKRA-ITH Informatika : Jurnal Komputer dan Informatika", "gt": "SINTA 5"},
    {"issn": "2963-1289", "journal": "Jurnal Komputer dan Teknologi (JUKOMTEK)", "gt": "SINTA 5"},
    {"issn": "2988-5272", "journal": "Jurnal Komputer Antartika", "gt": "SINTA 5"},
]

NEGATIVE_SEED = [
    {"journal": "arXiv preprint cs.AI", "venue_type": "preprint", "issns": [], "gt": "NONE"},
    {"journal": "bioRxiv", "venue_type": "preprint", "issns": [], "gt": "NONE"},
    {"journal": "IEEE Conference on Computer Vision and Pattern Recognition", "venue_type": "conference", "issns": [], "gt": "NONE"},
    {"journal": "Proceedings of the ACM SIGKDD Conference", "venue_type": "conference", "issns": [], "gt": "NONE"},
    {"journal": "Lokal Regional Bulletin Unindexed", "venue_type": "journal", "issns": ["9999-0001"], "gt": "NONE"},
    {"journal": "Unknown Working Paper Series", "venue_type": "journal", "issns": ["9999-0002"], "gt": "NONE"},
    {"journal": "Journal of Nothing Indexed", "venue_type": "journal", "issns": ["9999-0003"], "gt": "NONE"},
    {"journal": "Local Community Newsletter", "venue_type": "journal", "issns": ["9999-0004"], "gt": "NONE"},
    {"journal": "Internal Technical Report Series", "venue_type": "journal", "issns": ["9999-0005"], "gt": "NONE"},
    {"journal": "Private Conference Proceedings Vol 3", "venue_type": "conference", "issns": ["9999-0006"], "gt": "NONE"},
]


def _digits(issn: str) -> str:
    return issn.replace("-", "").strip().upper()


def select_sinta_only_seeds(scopus_issns: set[str]) -> list[dict[str, str]]:
    return [seed for seed in SINTA_SEED if _digits(seed["issn"]) not in scopus_issns]


def build_cases() -> list:
    rng = random.Random(SEED)
    cases = []
    with sqlite3.connect(SCOPUS_DB_PATH) as conn:
        scopus_issns = {
            row[0]
            for row in conn.execute(
                "SELECT issn FROM scopus_journals WHERE quartile IS NOT NULL"
            ).fetchall()
        }
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            rows = conn.execute(
                "SELECT issn, title FROM scopus_journals WHERE quartile = ? AND title IS NOT NULL",
                (q,),
            ).fetchall()
            pick = rng.sample(rows, SCOPUS_SAMPLE_PER_Q if q != "Q1" else SCOPUS_SAMPLE_PER_Q + 1)
            for issn, title in pick:
                cases.append({
                    "journal": title,
                    "venue_type": "journal",
                    "issns": [issn[:4] + "-" + issn[4:]],
                    "gt": f"Scopus {q}",
                    "kind": "scopus",
                })
    sinta_only_seeds = select_sinta_only_seeds(scopus_issns)
    if len(sinta_only_seeds) < SINTA_CASES:
        raise RuntimeError(
            f"Need {SINTA_CASES} SINTA-only seed journals; found {len(sinta_only_seeds)}"
        )
    for seed in sinta_only_seeds[:SINTA_CASES]:
        cases.append({
            "journal": seed["journal"],
            "venue_type": "journal",
            "issns": [seed["issn"]],
            "gt": seed["gt"],
            "kind": "sinta",
        })
    for neg in NEGATIVE_SEED[:NEGATIVE_CASES]:
        cases.append({**neg, "kind": "negative"})
    return cases


def ensure_v1_map() -> dict:
    if not os.path.exists(V1_CSV_PATH):
        req = urllib.request.Request(SCIMAGO_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(V1_CSV_PATH, "wb") as f:
            f.write(resp.read())
    v1 = {}
    with open(V1_CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for r in reader:
            if len(r) <= 9:
                continue
            q = r[9].strip()
            if not q or q == "-":
                continue
            try:
                sjr = float(r[8].strip().replace(",", "."))
            except ValueError:
                sjr = 0.0
            for item in r[4].split(","):
                clean = _digits(item.strip())
                if len(clean) == 8:
                    v1[clean] = (q, sjr)
    return v1


def _reported_token_count(response) -> int | None:
    raw = getattr(response, "raw", None)
    additional_kwargs = getattr(response, "additional_kwargs", None)
    usage = None
    for source in (raw, additional_kwargs):
        if isinstance(source, dict):
            usage = source.get("usage") or source.get("usage_metadata")
        else:
            usage = getattr(source, "usage", None) or getattr(source, "usage_metadata", None)
        if usage is not None:
            break
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif hasattr(usage, "to_dict"):
        usage = usage.to_dict()
    if not isinstance(usage, dict):
        return None

    total = usage.get("total_tokens", usage.get("total_token_count"))
    if total is not None:
        try:
            return int(total)
        except (TypeError, ValueError):
            return None

    prompt = usage.get("prompt_tokens", usage.get("prompt_token_count", usage.get("input_tokens")))
    completion = usage.get(
        "completion_tokens",
        usage.get("candidates_token_count", usage.get("output_tokens")),
    )
    if prompt is None or completion is None:
        return None
    try:
        return int(prompt) + int(completion)
    except (TypeError, ValueError):
        return None


def run_with_isolated_sinta_cache(cases: list, runner) -> list:
    """Give each benchmark variant an independent in-memory SINTA cache."""
    cache = {}

    def read_cache(issn):
        return cache.get(issn)

    def write_cache(issn, result):
        cache[issn] = result

    with patch("journal_indexer._read_sinta_cache", side_effect=read_cache), patch(
        "journal_indexer._write_sinta_cache",
        side_effect=write_cache,
    ):
        return [runner(case) for case in cases]


def run_v0_before(case: dict, llm) -> dict:
    """Reconstruct V0's venue-name heuristics, then use the configured LLM if needed."""
    t0 = time.perf_counter()
    j = case["journal"].lower()
    out = None
    llm_called = False
    reported_tokens = None
    status = "ok"
    error = None
    if "resti" in j or "ilkom" in j or "sisfo" in j:
        out = "SINTA 2 Accredited"
    elif any(k in j for k in ["cvpr", "neurips", "icml", "acl", "sigkdd", "conference", "ieee/cvf"]):
        out = "Conference Proceedings (Indexed)"
    elif "arxiv" in j or "biorxiv" in j or case["venue_type"] == "preprint":
        out = "Preprint (Non-Peer-Reviewed)"
    if out is None:
        if llm is None:
            status = "unavailable"
        else:
            llm_called = True
            prompt = (
                "Classify the academic venue. Output JSON {\"journal_metric\": \"...\"}.\n"
                f"Journal: {case['journal']}\nISSN: {', '.join(case['issns']) or 'none'}"
            )
            try:
                response = llm.complete(prompt)
                reported_tokens = _reported_token_count(response)
                match = re.search(r"\{.*\}", response.text, re.DOTALL)
                out = json.loads(match.group(0)).get("journal_metric") if match else response.text.strip()
                if not out:
                    status = "error"
                    error = "invalid_response"
            except Exception as exc:
                status = "error"
                error = type(exc).__name__
    return {
        "output": out,
        "status": status,
        "error": error,
        "llm_called": llm_called,
        "reported_tokens": reported_tokens,
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def run_v1_after(case: dict, v1_map: dict) -> dict:
    """V1: naive Scopus map (no coverage filter) + live SINTA, preprint/conference by venue_type."""
    t0 = time.perf_counter()
    out = None
    if case["venue_type"] == "preprint":
        out = "Preprint (Non-Peer-Reviewed)"
    elif case["venue_type"] == "conference":
        out = "Conference Proceedings (Indexed)"
    else:
        for i in case["issns"]:
            hit = v1_map.get(_digits(i))
            if hit:
                out = f"Scopus {hit[0]}"
                break
        if out is None and case["issns"]:
            s = lookup_sinta_live(_digits(case["issns"][0]))
            if s and s.get("tier"):
                out = s["tier"]
    return {
        "output": out or "Peer-Reviewed Journal",
        "status": "ok",
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def run_v2_current(case: dict) -> dict:
    t0 = time.perf_counter()
    res = lookup_journal_index(issn_list=case["issns"], journal_title=case["journal"], venue_type=case["venue_type"])
    return {
        "output": res.get("journal_metric", "Peer-Reviewed Journal"),
        "status": "ok",
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def matches(gt: str, output: str) -> bool:
    """Strict match: the claimed tier/quartile must equal ground truth; negatives must not claim any index."""
    out = (output or "").upper()
    if gt == "NONE":
        # Negative: must not claim any national or Scopus index.
        return not any(tok in out for tok in ["SCOPUS Q", "SINTA", "ACCREDITED"])
    if gt.startswith("Scopus"):
        return gt.upper() in out
    if gt.startswith("SINTA"):
        want = "S" + gt.split()[1]
        return re.search(rf"\b{want}\b", out) is not None and "SCOPUS" not in out
    return False


def main():
    from runtime_environment import load_backend_environment

    load_backend_environment()
    try:
        from rag.llm_factory import get_fast_llm, get_main_llm
        llm = get_fast_llm() or get_main_llm()
    except Exception:
        llm = None

    v1_map = ensure_v1_map()
    cases = build_cases()
    v0_runs = [run_v0_before(case, llm) for case in cases]
    v1_runs = run_with_isolated_sinta_cache(cases, lambda case: run_v1_after(case, v1_map))
    v2_runs = run_with_isolated_sinta_cache(cases, run_v2_current)
    results = []
    for case, v0, v1, v2 in zip(cases, v0_runs, v1_runs, v2_runs):
        results.append({
            "case": case,
            "v0": v0,
            "acc0": matches(case["gt"], v0["output"]) if v0["status"] == "ok" else None,
            "v1": v1,
            "acc1": matches(case["gt"], v1["output"]),
            "v2": v2,
            "acc2": matches(case["gt"], v2["output"]),
        })

    n = len(results)

    def mark(run, correct):
        if run["status"] == "error":
            return "ERR"
        if run["status"] == "unavailable":
            return "SKIP"
        return "OK" if correct else "X"

    print(f"\n{'#':<3} {'kind':<9} {'journal':<38} {'gt':<12} {'V0*':<5} {'V1':<4} {'V2':<4}")
    for i, r in enumerate(results, 1):
        c = r["case"]
        print(f"{i:<3} {c['kind']:<9} {c['journal'][:38]:<38} {c['gt']:<12} "
              f"{mark(r['v0'], r['acc0']):<5} {mark(r['v1'], r['acc1']):<4} {mark(r['v2'], r['acc2']):<4}")

    def score(key):
        valid = [r[key] for r in results if r[key] is not None]
        percentage = sum(valid) / len(valid) * 100 if valid else None
        return percentage, sum(valid), len(valid)

    print(f"\nTotal cases: {n}")
    for label, accuracy_key, run_key in [
        ("reconstructed V0*", "acc0", "v0"),
        ("naive Scopus V1", "acc1", "v1"),
        ("current resolver V2", "acc2", "v2"),
    ]:
        percentage, correct, evaluated = score(accuracy_key)
        valid_runs = [r[run_key] for r in results if r[accuracy_key] is not None]
        avg_lat = sum(run["latency_ms"] for run in valid_runs) / len(valid_runs) if valid_runs else None
        accuracy_text = f"{percentage:5.1f}% ({correct}/{evaluated})" if percentage is not None else "n/a (0 cases)"
        latency_text = f"{avg_lat:8.2f} ms" if avg_lat is not None else "n/a"
        print(f"  {label:<22} accuracy {accuracy_text:<18} avg latency {latency_text}")

    llm_runs = [r["v0"] for r in results if r["v0"]["llm_called"]]
    reported_usage = [run["reported_tokens"] for run in llm_runs if run["reported_tokens"] is not None]
    if llm_runs:
        print(
            f"  V0 provider-reported tokens: {sum(reported_usage)} "
            f"(usage reported for {len(reported_usage)}/{len(llm_runs)} LLM calls)"
        )
    else:
        print("  V0 provider-reported tokens: n/a (no LLM calls)")
    print("  V0 is a reconstructed heuristic/LLM proxy, not an exact historical-code baseline.")
    print("  V1 and V2 use separate in-memory SINTA caches; persistent application cache is not read or written.")

    by_kind = {}
    for r in results:
        by_kind.setdefault(r["case"]["kind"], []).append(r)
    print("\nPer kind (V0 / V1 / V2 correct):")
    for kind, rs in by_kind.items():
        v0_correct, v0_evaluated = sum(x["acc0"] is True for x in rs), sum(x["acc0"] is not None for x in rs)
        v1_correct = sum(x["acc1"] is True for x in rs)
        v2_correct = sum(x["acc2"] is True for x in rs)
        print(f"  {kind:<9} n={len(rs):<3} "
              f"V0* {v0_correct}/{v0_evaluated} evaluated  "
              f"V1 {v1_correct}/{len(rs)}  "
              f"V2 {v2_correct}/{len(rs)}")


if __name__ == "__main__":
    main()
