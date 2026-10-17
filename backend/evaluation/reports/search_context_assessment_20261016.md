# Issue #48: search-context implementation and validation

## Conclusion

The pre-patch baseline confirmed two bounded planner defects: compacted system-role context was omitted from the planner prompt, and stale language filters overrode a correct model decision. The patch now preserves recognized compaction bridges as historical context and normalizes language filters according to an explicit model conflict flag. Ordinary user/assistant history already reached the planner before this change, so the issue's premise that planning always uses an isolated prompt was outdated.

The pre-patch `ag/claude-sonnet-4-6` comparison completed all 430 calls without API errors. All 100 ordinary history cases passed the annotated checks; the only primary failures were ten compacted-summary cases and ten language-filter conflicts. The post-patch comparison also completed all 430 calls without transport errors. All 120 primary history cases and all 120 explicit-query controls passed, including 10/10 compacted-memory cases and 10/10 language-filter conflicts. This supports targeted fixes, not a claim that ordinary follow-up search is generally broken or that session-title injection is necessary.

The configured Fast model's broad run has insufficient successful API coverage for a model-quality conclusion. No matched smaller/edge-model comparison was completed. Its raw run artifacts are excluded from the PR evidence bundle; the matched Sonnet runs and deterministic proofs are included.

The implementation is on branch `fix/search-context-48` at version `1.18.2`. The run manifests record baseline commit `e2fbfc1745c63de7b00f320c4785244a57c93a8a` because the evaluations predate the implementation commit. The model configuration and pre-patch evaluation artifacts remain unchanged.

## Scope and method

- Baseline: `e2fbfc1745c63de7b00f320c4785244a57c93a8a`.
- Planner SHA-256: `beee4236928ac8178046114a6922fd24c41194c27ec76ac7bed1100bdfea74b4`.
- 140 synthetic cases: ten research domains crossed with fourteen scenario families.
- Families: ellipsis, slang/typos, multilingual requests, reference selection, topic switches, corrections, distractors, quoted instructions, conflicting filters, inherited constraints, compacted memory, structured source references, long history, and ambiguity.
- 120 primary cases; 20 diagnostic-only cases with ambiguous references or source-card-only topic metadata.
- Conditions: follow-up with history, equivalent standalone query, follow-up without history, and ten compacted-summary counterfactuals with the summary role changed to user.
- 430 planned calls per full model run. SDK retries are disabled. The SDK timeout is 45 seconds, with a 55-second outer bound in the recorded runs.
- The exact production planner is loaded without package-root database/vector-store initialization. Registry results, routing, final synthesis, and end-to-end retrieval quality are outside this experiment.
- Topic matching is a lexical screen with annotated alternatives, not a semantic judge. Raw model decisions and postprocessed plans are stored separately.

## Confirmed bugs

### Medium: compacted context disappears at the planner boundary

**Status:** Confirmed. **Location:** `backend/services/search/query_planner.py:132-138`.

**Failure scenario:** the old research topic survives only in the system-role compaction bridge; retained user/assistant turns contain formatting discussion rather than that topic. A follow-up asks for more papers on the earlier topic.

**Evidence:** the real `acompact_chat_history` retains the supplied correct summary, but the real planner serializes only user/assistant messages. The outgoing prompt lacks the retained topic in all ten deterministic fixtures. A second ten-topic test uses the production token counter: 978-986 input tokens become 240-248 tokens under a deliberately small 250-token budget; the topic remains in the summary and is absent from the planner prompt. The summary text is injected to isolate the handoff, not scored as a live summarizer result.

**Impact:** topic information is lost before inference. Model strength cannot recover information that is absent from its input. This demonstrates a conditional handoff defect, not how often normal sessions reach compaction.

**Live cross-check:** all ten Sonnet compacted-history fixtures failed to resolve the topic. Their recorded prompts lack it, and their responses explicitly identify insufficient topic context. The same ten topics all pass when the synthetic summary's role alone is changed from system to user. This counterfactual tests information delivery, not a production fix.

**Recommended action:** preserve trusted compaction context at the planner boundary and test it alongside ordinary history, topic switches, and explicit controls. Adding session titles is not required to explain this failure.

**Patch status:** implemented in `backend/services/search/query_planner.py`. The planner recognizes the compactor's exact bridge markers, includes them in a historical-context section, and keeps the current request later in the prompt. Unrecognized system-role messages remain excluded.

**Evidence files:** `search_context/offline-postfix-20261016/PROOFS.md`, `search_context/offline-postfix-20261016/proofs.json`, `search_context/live-sonnet-postfix-20261016/REPORT.md`, and `backend/tests/test_search_context_evaluation.py` (`test_real_compactor_summary_reaches_search_prompt`, `test_summary_handoff_with_production_token_counter`).

### Medium: stale UI language replaces a correct model answer

**Status:** Confirmed. **Location:** `backend/services/search/query_planner.py:240-241`.

**Failure scenario:** the latest request explicitly says English only; its appended UI tag still says `[Filter Preferences: languages: zh, year: 2020]`.

**Evidence:** a correct synthetic answer returns `languages: [en]`, then production postprocessing returns `[zh]` in all ten fixtures. The configured Fast model independently reproduced this in `filter_override-05`: its raw JSON chooses English and explicitly reports prioritizing the latest prompt, while the final plan uses Chinese. This contradicts the planner's documented conflict priority at lines 156-158.

**Live cross-check:** Sonnet returned the correct English language and all other annotated fields in all ten history fixtures; all ten final plans instead use Chinese. The topic itself was preserved. This distinguishes code-level normalization from contextual reasoning.

**Impact:** the returned plan requests the wrong language even when model reasoning is correct. This proof does not claim particular papers were returned by a registry.

**Recommended action:** make postprocessing respect the intended explicit-user/filter precedence, including filter-reset cases, rather than adding more context to the prompt.

**Patch status:** implemented in `backend/services/search/query_planner.py`. The planner asks for a boolean `language_filter_conflict`, validates ISO-style two-letter language codes, keeps the selected UI language when there is no conflict or the model response is invalid, and preserves an explicit empty language list only when the model reports a conflict. A sole English selection also sets the search routing preference to English.

**Evidence files:** `search_context/offline-postfix-20261016/proofs.json`, `search_context/live-sonnet-postfix-20261016/REPORT.md`, and `backend/tests/test_search_query_planner_context.py`.

### Severity totals

Critical: 0. High: 0. Medium: 2. Low: 0. Twenty deterministic fixtures reproduce two mechanisms, not twenty independent bugs. Neither finding establishes a widespread fatal search failure.

## Completed independent-model experiment

Run-only override: `ag/claude-sonnet-4-6`, provider-reported model `claude-sonnet-4-6` on all 430 responses, temperature 0.1. The application remained configured for its original Fast model. Conditions use the same frozen 140-case corpus as the configured-model run.

| Condition / subset | Passed / primary cases | Interpretation |
| --- | --- | --- |
| Standalone explicit query | 120/120 | Control: topic and constraints are stated directly. |
| Ordinary history families | 100/100 | Ellipsis, slang, multilingual requests, corrections, topic switches, distractors, reference selection, inherited constraints, quoted text, and long un-compacted history. |
| Compacted system-role summary | 0/10 | Planner prompt loses the topic; not a failure to reason over a supplied topic. |
| Conflicting language filter | 0/10 | Model chooses English correctly; postprocessing changes it to Chinese. |
| All primary history cases | 100/120 | Structured stress-suite result, not an estimated production success rate. |
| Follow-up without history | 10/120 | Only explicit topic switches pass, since those queries name their own topic. Other missing-topic failures are expected negative-control behavior. |
| Summary changed to user role | 10/10 | Diagnostic counterfactual for the compacted-summary subset only. |

All 120 primary history/explicit pairs completed. One hundred passed both conditions; twenty failed only in the history condition, entirely accounted for by the two mechanisms above. No other primary failure required a semantic rejection of the lexical screen. Inspection of all 100 ordinary history queries found the expected topics or corrections, and all annotated field checks passed.

There were 291 parseable model-response records and 139 `invalid_model_output` records, with zero API errors. The latter means the production JSON extractor could not consume the complete response, not that the model failed to notice missing context. All ten primary compacted-history failures are among these records; the other 129 are no-history or ambiguous-reference observations. Missing-context responses commonly contain clarification text or JSON accompanied by explanatory prose. They are not counted as evidence of an intelligence deficit.

The 20 ambiguous/source-card diagnostic cases are excluded from the primary results above. Their explicit controls select or name a topic; this does not supply a gold answer for an ambiguous request.

Evidence: `search_context/live-sonnet-20261016/REPORT.md`, `manifest.json`, `summary.json`, and `observations.jsonl`. Integrity checks verified 430 unique observation identities, all ten raw-correct language overwrites, and all ten omitted-topic/counterfactual pairs. These checks did not modify or resample responses.

## Post-patch live comparison

The same frozen corpus, seed, run-only Sonnet override, temperature, and four evaluation modes completed 430/430 calls. There were 346 parseable model responses and 84 invalid model outputs, with no transport errors. The 84 invalid outputs were confined to the no-history negative control and one diagnostic history observation; none affected the 120 primary history cases.

| Condition / subset | Passed / primary cases | Interpretation |
| --- | --- | --- |
| Standalone explicit query | 120/120 | Same control as the baseline. |
| Primary history cases | 120/120 | All annotated topics and fields passed, including compaction and filter conflicts. |
| Ordinary history families | 100/100 | No regression in the cases that already passed before the patch. |
| Compacted system-role summary | 10/10 | Up from 0/10; the bridge topic reaches the planner and the model resolves it. |
| Conflicting language filter | 10/10 | Up from 0/10; the final plan keeps the requested language. |
| Follow-up without history | 10/120 | Expected negative-control behavior; only standalone explicit topic switches pass. |
| Summary changed to user role | 10/10 | Diagnostic control, unchanged from baseline. |

The 120 primary history/explicit pairs all passed both conditions. The production planner file's evaluated SHA-256 is recorded in the run manifest. The manifest's HEAD is the pre-patch base commit because the run predates the implementation commit. This experiment does not query registries or measure search-result relevance.

Evidence: `search_context/live-sonnet-postfix-20261016/REPORT.md`, `manifest.json`, `summary.json`, and `observations.jsonl`.

## Configured-model coverage

Model: `ag/gemini-3.8-flash-high`, temperature 0.1, existing Fast profile.

The full run attempted 430/430 observations: 31 model responses and 399 API failures (384 `BadRequestError`, 15 `APITimeoutError`). A separate minimal request reproduced HTTP 400 with `User location is not supported for the API use.` That probe explains an observed provider restriction; individual historical HTTP 400 bodies were not captured, so not every failed row is assigned that exact cause.

Only 8/120 primary history cases received a response; 7 passed the automatic screen and the remaining case was the confirmed language-postprocessing defect. Only five primary history/standalone pairs completed without an API failure; all five passed both conditions. These are coverage observations, not representative model pass rates.

The initial pilot, an aborted pre-shuffle run, and other exploratory runs are not part of the committed evidence set. Their results must not be pooled as independent cases. Provider/account failures also prevented useful runs on the configured Fallback and the initial GPT comparison candidates. A model's presence in the gateway catalog did not guarantee account access.

The configured-model run and its provider failure details remain in local evaluation artifacts and are not part of the committed evidence bundle.

## Rejected claim

**Claim:** the current planner never receives conversation history and always reformulates an isolated user prompt.

**Status:** Rejected. Ordinary history is passed by `backend/rag/pipelines/search_pipeline.py:28-29` and serialized at `backend/services/search/query_planner.py:129-140`. The ordinary-user-history control in the new tests verifies the actual outgoing prompt includes the topic. Successful live history/standalone pairs also contradict the universal claim. This does not reject the narrower confirmed system-summary omission.

Rejected claims are excluded from severity totals.

## Notes / limitations

- The corpus is structured synthetic stress testing, not 140 independent handwritten scenarios or a population sample. Most families reuse ten topic templates; multilingual variants are not fully crossed with every topic.
- Ambiguous requests have no unique topic answer and are excluded from primary scores. Structured-source references explore a separate metadata boundary and are also excluded.
- Failures of the no-history negative control are expected when the requested topic was deliberately withheld. They are not additional defects.
- Compaction uses a deliberately small budget and supplied correct summaries. The live loop accepts prepared history and does not measure production compaction frequency or summarizer fidelity.
- No smaller/edge model completed a matched comparison. The experiment cannot attribute any issue specifically to model size or edge deployment.
- No session-title mechanism or migration was added. The implementation stays within the planner boundary and the two demonstrated defects. Keep Issue #48 scoped to those behaviors rather than assuming its original architecture is necessary.

## Local verification

- Initial full backend suite: **441 passed, 7 live tests deselected**; nine dependency/runtime warnings.
- Post-review focused suites: **187 passed** across the search-context evaluation and query-planner tests; eight dependency deprecation warnings.
- Resume smoke checks rejected changed concurrency and timeout settings. The offline runner completed and wrote its report using deterministic fallback.
- Regression checks cover the production compactor-to-planner handoff, language precedence, invalid language values, and adapter-bound search plans.
- Deterministic post-patch proofs: **20/20** across ten synthetic topics.
- Ruff: **passed** across `backend`; `git diff --check`: **passed**.
- Frontend: **125 tests passed**, lint and type-check passed, and the production build passed. The version footer test now expects `v1.18.2`.
- Targeted `compileall` passed for changed Python files. Recursive `compileall backend` reached an incompatible Python 3.12 syntax file inside the Python 3.11 virtualenv's installed PyTorch package; it did not indicate an application-source syntax error.
- The general RAG answer-quality benchmark was not run because this patch does not change `backend/rag/` retrieval or synthesis behavior.
- Copy filter: PASS for evidence-backed statements and no fabricated claims. No UI layout or styling changed.
