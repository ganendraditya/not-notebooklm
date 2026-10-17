from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any


def write_report(output: Path, manifest: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    categories: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["tier"], row["mode"])].append(row)
        if row["mode"] == "history":
            categories[(row["tier"], row["category"])].append(row)

    lines = [
        "# Search-context evaluation", "",
        f"HEAD commit: `{manifest['commit']}`. Evaluated planner SHA-256: `{manifest['planner_sha256']}`. Evaluation code SHA-256: `{manifest.get('evaluation_sha256', 'not recorded')}`.",
        f"Synthetic cases: {manifest['case_count']}. Completed observations: {len(rows)}/{manifest.get('planned_observations', 'not recorded')} planned.",
        "",
        "## Method", "",
        "This run calls the production query planner from the current checkout with synthetic conversations. The SHA-256 identifies the exact planner contents evaluated, including uncommitted edits.",
        "It does not call scholarly registries, test search-result relevance, or benchmark final answer quality.",
        "The corpus crosses ten research domains with fourteen scenario families. These are structured stress tests, not an independent random sample of users.",
        "Topic checks use documented regular-expression alternatives on en_query; lexical failures need semantic inspection before being called defects.",
        "Field checks compare only explicitly annotated requirements. No LLM judge is used.",
        "Transport errors are excluded from ability scores. Invalid model responses remain failures of the model-call path.",
        "Ambiguous references and structured source-card references are diagnostic-only and excluded from primary rates.",
        "Compacted-memory cases use synthetic system-role summaries; separate tests check the real compactor's output convention.",
        "No-history is a negative control, not an alternative implementation. Explicit is a standalone-query control.",
        "Summary-as-user is a diagnostic counterfactual, not current application behavior.",
        "The harness disables SDK retries to bound run duration and does not change the active model configuration or make runtime edits.",
        "", "## Models", "",
    ]
    for model in manifest["models"]:
        lines.append(f"- {model['tier']}: `{model['model']}`; temperature {model['temperature']}.")
    lines += [
        "", "## Automated screen", "",
        "Pass rates below are conditional on a completed non-transport observation. Coverage must be read alongside them.",
        "", "| Tier | Condition | Passed / scorable | Transport errors | Diagnostic-only |",
        "| --- | --- | --- | --- | --- |",
    ]
    for (tier, mode), items in sorted(groups.items()):
        valid = [row for row in items if row["status"] != "transport_error" and not row["screen"]["diagnostic_only"]]
        passed = sum(row["screen"]["passed"] and row["status"] != "invalid_model_output" for row in valid)
        transport = sum(row["status"] == "transport_error" for row in items)
        diagnostic = sum(row["screen"]["diagnostic_only"] for row in items)
        lines.append(f"| {tier} | {mode} | {passed}/{len(valid)} | {transport} | {diagnostic} |")
    lines += ["", "## History condition by category", "", "| Tier | Category | Pass / scorable |", "| --- | --- | --- |"]
    for (tier, category), items in sorted(categories.items()):
        valid = [row for row in items if row["status"] != "transport_error" and not row["screen"]["diagnostic_only"]]
        passed = sum(row["screen"]["passed"] and row["status"] != "invalid_model_output" for row in valid)
        lines.append(f"| {tier} | {category} | {passed}/{len(valid)} |")

    lines += ["", "## Paired controls", ""]
    paired: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        paired[(row["tier"], row["case_id"], row["repeat"])][row["mode"]] = row
    paired_counts: Counter = Counter()
    for (tier, _case_id, _repeat), conditions in paired.items():
        if not {"history", "explicit"}.issubset(conditions):
            continue
        history, explicit = conditions["history"], conditions["explicit"]
        if history["screen"]["diagnostic_only"] or any(row["status"] == "transport_error" for row in (history, explicit)):
            continue
        history_pass = history["status"] == "model_response" and history["screen"]["passed"]
        explicit_pass = explicit["status"] == "model_response" and explicit["screen"]["passed"]
        paired_counts[(tier, history_pass, explicit_pass)] += 1
    for (tier, history_pass, explicit_pass), count in sorted(paired_counts.items()):
        lines.append(f"- {tier}: history {'pass' if history_pass else 'fail'}, explicit {'pass' if explicit_pass else 'fail'}: {count} paired cases.")
    if not paired_counts:
        lines.append("No scorable history/explicit pairs completed.")
    lines += ["", "## Observations requiring inspection", ""]
    for row in rows:
        if row["status"] == "transport_error" or row["screen"]["passed"]:
            continue
        failures = ", ".join(row["screen"]["failed_checks"])
        lines.append(f"- `{row['case_id']}` / {row['tier']} / {row['mode']}: {failures}. Status: `{row['status']}`.")
    lines += [
        "", "## Limitations", "",
        "A failed screen does not establish a general intelligence deficit or model-size effect.",
        "Tier names do not establish model size, hardware, or an edge deployment. Compare identical case IDs when comparing models.",
        "The planner consumes already-prepared history; routing and real long-history compaction are not end-to-end tested by the live loop.",
        "The harness does not make runtime edits, perform prompt tuning, introduce a topic-state mechanism, or replace prior baselines.",
        "", "Raw prompts, responses, plans, timing, and provider-reported usage are in `observations.jsonl`.",
        "The full synthetic dataset and provenance are in `cases.json` and `manifest.json`.", "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "completed": len(rows),
        "planned": manifest.get("planned_observations"),
        "statuses": dict(Counter(row["status"] for row in rows)),
        "error_types": dict(Counter(row["error_type"] for row in rows if row.get("error_type"))),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
