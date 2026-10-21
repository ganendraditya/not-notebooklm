import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import random
import subprocess
import sys


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from runtime_environment import load_backend_environment

from evaluation.search_context.cases import build_cases
from evaluation.search_context.proofs import write_proofs
from evaluation.search_context.report import write_report
from evaluation.search_context.runtime import (
    configured_models,
    evaluate_case,
    evaluation_source_fingerprint,
    should_trip_circuit,
    source_fingerprint,
)


RESUME_PROVENANCE_KEYS = (
    "commit",
    "planner_sha256",
    "evaluation_sha256",
    "cases_sha256",
    "models",
    "modes",
    "repeat",
    "concurrency",
    "timeout_seconds",
    "seed",
)


def resume_provenance_mismatch(current: dict[str, object], previous: dict[str, object]) -> str | None:
    for key in RESUME_PROVENANCE_KEYS:
        if current.get(key) != previous.get(key):
            return key
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the current search planner without changing runtime code.")
    parser.add_argument("--tiers", nargs="+", choices=["fast", "primary", "fallback"], default=["fast"])
    parser.add_argument("--model", help="Run-only comparison model ID; never writes application configuration.")
    parser.add_argument("--modes", nargs="+", choices=["history", "explicit", "no_history", "summary_as_user", "fallback"], default=["history", "explicit", "no_history"])
    parser.add_argument("--category", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=55)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--seed", type=int, default=48)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.concurrency < 1 or args.repeat < 1 or args.timeout <= 0 or (args.limit is not None and args.limit < 1):
        parser.error("concurrency, repeat, timeout, and limit must be positive")
    if args.model and (len(args.tiers) != 1 or args.offline):
        parser.error("--model requires exactly one live tier")
    if not args.offline:
        load_backend_environment()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cases = build_cases()
    if args.category:
        cases = [case for case in cases if case.category in args.category]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        parser.error("no matching cases")
    models = [("offline", None, {"tier": "offline", "model": "no_model", "temperature": None})] if args.offline else configured_models(args.tiers, args.model)
    if not models:
        parser.error("no configured models; configure the app or use --offline")
    modes = ["fallback"] if args.offline else args.modes
    case_payload = [case.to_dict() for case in cases]
    case_json = json.dumps(case_payload, ensure_ascii=False, indent=2)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BACKEND, text=True).strip(),
        "planner_sha256": source_fingerprint(),
        "evaluation_sha256": evaluation_source_fingerprint(),
        "cases_sha256": hashlib.sha256(case_json.encode()).hexdigest(),
        "case_count": len(cases),
        "models": [info for _tier, _llm, info in models],
        "modes": modes,
        "repeat": args.repeat,
        "concurrency": args.concurrency,
        "timeout_seconds": args.timeout,
        "seed": args.seed,
        "planned_observations": args.repeat * len(models) * sum(
            sum(mode != "summary_as_user" or case.category == "compacted_memory" for mode in modes)
            for case in cases
        ),
    }
    output = args.output.resolve()
    rows = []
    if args.resume:
        previous = json.loads((output / "manifest.json").read_text())
        mismatch = resume_provenance_mismatch(manifest, previous)
        if mismatch:
            parser.error(f"resume provenance mismatch: {mismatch}")
        rows = [json.loads(line) for line in (output / "observations.jsonl").read_text().splitlines() if line.strip()]
        manifest = previous
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (output / "cases.json").write_text(case_json, encoding="utf-8")
    completed = {(row["tier"], row["case_id"], row["mode"], row["repeat"]) for row in rows}
    await write_proofs(output)
    semaphore = asyncio.Semaphore(args.concurrency)
    blocked_tiers = set()

    with (output / "observations.jsonl").open("a", encoding="utf-8") as stream:
        async def run_one(case, mode, tier, llm, repeat):
            if (tier, case.id, mode, repeat) in completed:
                return
            async with semaphore:
                if tier in blocked_tiers:
                    return
                row = await evaluate_case(case, mode, tier, llm, args.timeout, repeat)
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(f"{len(rows)} {tier} {case.id} {mode}: {row['status']} screen={row['screen']['passed']}", flush=True)
                tier_rows = [item for item in rows if item["tier"] == tier]
                if should_trip_circuit(tier_rows):
                    blocked_tiers.add(tier)
                    print(f"Circuit breaker: {tier} has three consecutive connection/authentication/server errors; remaining calls skipped.", flush=True)
                write_report(output, manifest, rows)

        ordered_cases = list(cases)
        random.Random(args.seed).shuffle(ordered_cases)
        tasks = [
            run_one(case, mode, tier, llm, repeat)
            for repeat in range(args.repeat)
            for case in ordered_cases
            for tier, llm, _info in models
            for mode in modes
            if mode != "summary_as_user" or case.category == "compacted_memory"
        ]
        await asyncio.gather(*tasks)
    write_report(output, manifest, rows)
    print(f"Report: {output / 'REPORT.md'}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
