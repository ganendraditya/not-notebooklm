# Deterministic search-context proofs

Reproduced fixtures: 20/20 across two code mechanisms and ten synthetic topics.
These are code-path reproductions using a fixed synthetic model answer. They do not measure any real model's intelligence.
No runtime source files were modified.

## Medium: compaction bridge is omitted from search planning

Status: Confirmed. Location: `backend/services/search/query_planner.py:132-138`.
Trigger: an earlier research topic survives only in the system-role bridge produced by `acompact_chat_history`; later user/assistant turns do not restate it.
Evidence: the actual compactor retains the topic in its system message, but the actual planner serializes only user and assistant messages. The recorded outgoing prompt lacks the topic in all ten fixtures.
Impact: follow-up searches lose their only topic reference before the model sees it. A more capable model cannot recover information absent from its input.
Recommendation: preserve trusted compaction context when constructing the search-planner input, then rerun both standalone and compacted controls.

## Medium: stale UI language overrides a correct model decision

Status: Confirmed. Location: `backend/services/search/query_planner.py:240-241`.
Trigger: the latest request says English only while the appended filter tag still says `languages: zh`.
Evidence: the fixed model answer supplies `languages: [en]`; postprocessing replaces it with `[zh]` in all ten fixtures. Raw and final plans are saved side by side.
Impact: the returned search plan requests the wrong language despite a correct model decision and explicit latest-user priority in the planner prompt.
Recommendation: resolve explicit user/filter precedence consistently in postprocessing; verify language inclusion and filter reset cases before choosing a fix.

## Counts

Critical 0; High 0; Medium 2; Low 0. Twenty reproductions establish two mechanisms, not twenty independent defects.

## Notes / limitations

The compactor uses its real orchestration with an injected correct summary and deterministic word-count tokenizer. This isolates the role-handoff contract; it does not test live summarizer fidelity or normal context-budget frequency.
The language reproduction isolates planner output. It does not claim a registry returned Chinese papers or measure downstream result quality.
The hardcoded fake response is deliberately correct and is never counted as live model evidence.
The large synthetic corpus remains a stress suite, not a population estimate.
Full inputs and outputs: `proofs.json`.
