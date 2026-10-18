# Search-context stress suite (Issue #48)

This suite tests the current query planner without modifying the search pipeline or calling scholarly registries. All dialogue and source-card examples are synthetic fixtures, not actual papers or user records.

Recorded results and verified findings: [Issue #48 assessment, 2026-10-16](../reports/search_context_assessment_20261016.md).

The corpus has 140 cases: ten research domains crossed with fourteen scenario families. It covers ellipsis, slang, ten language/register variants, reference selection, explicit topic switches, corrections, distractors, quoted instructions, filter conflicts, inherited constraints, compacted history, structured source cards, long history, and ambiguous references. The structured-card and ambiguous-reference families are diagnostic-only.

## Run

From the repository root:

```bash
PYTHONPATH=backend backend/venv/bin/python backend/evaluation/eval_search_context.py \
  --offline --output backend/evaluation/reports/search_context/offline-YYYYMMDD

PYTHONPATH=backend backend/venv/bin/python backend/evaluation/eval_search_context.py \
  --tiers fast fallback --modes history explicit no_history summary_as_user \
  --concurrency 3 --output backend/evaluation/reports/search_context/live-YYYYMMDD
```

The live runner uses existing application profiles and credentials. It never changes the active configuration. Identical model/endpoint combinations are deduplicated. A tier is not evidence of model size or edge hardware. SDK retries are disabled to bound duration; three consecutive connection, authentication, bad-request, or server failures stop further requests for that tier. A per-case timeout does not trip that breaker. Cases are shuffled with a recorded seed (default 48) rather than attempting all ambiguous cases first.

Use `--tiers fast --model <gateway-model-id>` for a run-only comparison model. Its override flag and the application's configured model ID are both recorded in the manifest. This never writes `.env` or changes the active application model. Provider error messages are retained with the API key and email addresses redacted.

Use `--category ellipsis --limit 2` for a pilot, `--repeat 3` for repeated sampling, and `--resume` with the same output path and arguments after interruption. Resume validates the commit, planner and evaluation-code hashes, dataset hash, model configuration, conditions, concurrency, timeout, repeat count, and seed. Failed transport observations are retained as unavailable coverage, not silently replaced.

## Conditions

- `history`: the original follow-up and supplied history, using the current planner and its recognized server-generated compaction bridge.
- `explicit`: a standalone query naming the topic and annotated constraints.
- `no_history`: the follow-up without history, a negative control.
- `summary_as_user`: only compacted-memory fixtures, with their summary role changed to user. This is a diagnostic counterfactual used to isolate role handling, not current application behavior.
- `fallback`: no model, even if a live model is configured for other modes. It demonstrates deterministic fallback behavior and is not a model-quality score.

The runner imports the exact planner and factory source files directly, avoiding package-root initialization of databases, vector stores, and embedding models. It still executes the original functions and prompt construction. This is planner-level isolation, not an end-to-end application benchmark.

## Evidence and grading

Each run writes:

- `cases.json`, the frozen synthetic inputs and annotated expectations.
- `manifest.json`, source commit, planner, directly executed evaluation-source, and corpus hashes, plus model IDs, protocol, settings, and a credential-free endpoint fingerprint. Resume rejects changes to these values.
- `observations.jsonl`, incremental raw prompts, responses, raw and normalized plans, provider-reported usage, timing, and individual checks.
- `REPORT.md`, paired controls, category breakdowns, coverage, and limitations.
- `proofs.json` and `PROOFS.md`, deterministic fixed-response regression checks for compaction-bridge delivery and language-filter precedence.

Topic checks are synonym-aware regular-expression screens on `en_query`, not semantic ground truth. A screen failure requires manual inspection before it becomes a confirmed finding. Field checks apply only to the annotated requirements. A transport failure never becomes a zero intelligence score. Raw model answers and application-normalized plans are retained separately to distinguish generation from postprocessing.

The suite does not evaluate registry recall, candidate reranking, citation quality, final answers, live compaction fidelity, or user population failure rates. Do not tune the planner on this suite and then present its score as held-out performance.
