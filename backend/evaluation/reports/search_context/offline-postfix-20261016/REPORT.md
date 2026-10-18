# Search-context evaluation

Source commit: `e2fbfc1745c63de7b00f320c4785244a57c93a8a`. Planner SHA-256: `b020b447633a1b02a2c23fe390bfe71ee416e734cc53dcf94c2efab0c5ed527f`.
Synthetic cases: 140. Completed observations: 140/140 planned.

## Method

This run calls the unchanged production query planner with synthetic conversations.
It does not call scholarly registries, test search-result relevance, or benchmark final answer quality.
The corpus crosses ten research domains with fourteen scenario families. These are structured stress tests, not an independent random sample of users.
Topic checks use documented regular-expression alternatives on en_query; lexical failures need semantic inspection before being called defects.
Field checks compare only explicitly annotated requirements. No LLM judge is used.
Transport errors are excluded from ability scores. Invalid model responses remain failures of the model-call path.
Ambiguous references and structured source-card references are diagnostic-only and excluded from primary rates.
Compacted-memory cases use synthetic system-role summaries; separate tests check the real compactor's output convention.
No-history is a negative control, not an alternative implementation. Explicit is a standalone-query control.
Summary-as-user is a diagnostic counterfactual, not current application behavior.
The harness disables SDK retries to bound run duration; no production model settings or prompt are changed.

## Models

- offline: `no_model`; temperature None.

## Automated screen

Pass rates below are conditional on a completed non-transport observation. Coverage must be read alongside them.

| Tier | Condition | Passed / scorable | Transport errors | Diagnostic-only |
| --- | --- | --- | --- | --- |
| offline | fallback | 0/120 | 0 | 20 |

## History condition by category

| Tier | Category | Pass / scorable |
| --- | --- | --- |

## Paired controls

No scorable history/explicit pairs completed.

## Observations requiring inspection

- `slang_and_typos-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `deterministic_fallback`.
- `reference_selection-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `slang_and_typos-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-05` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-06` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-07` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `multilingual-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count, field:languages. Status: `deterministic_fallback`.
- `constraint_inheritance-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `ellipsis-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol. Status: `deterministic_fallback`.
- `compacted_memory-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `deterministic_fallback`.
- `correction-02` / offline / fallback: topic:base.edit, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `filter_override-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:languages. Status: `deterministic_fallback`.
- `explicit_topic_switch-05` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `ellipsis-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water. Status: `deterministic_fallback`.
- `ambiguous_reference-03` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `ellipsis-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil. Status: `deterministic_fallback`.
- `long_history-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `deterministic_fallback`.
- `constraint_inheritance-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `constraint_inheritance-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `distractors-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol. Status: `deterministic_fallback`.
- `quoted_instructions-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `deterministic_fallback`.
- `correction-03` / offline / fallback: topic:phyto|plant.based, topic:cadmium|\bcd\b, field:target_count. Status: `deterministic_fallback`.
- `long_history-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-02` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-07` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-02` / offline / fallback: topic:base.edit, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `ellipsis-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial. Status: `deterministic_fallback`.
- `multilingual-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count, field:languages. Status: `deterministic_fallback`.
- `slang_and_typos-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `filter_override-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:languages. Status: `deterministic_fallback`.
- `quoted_instructions-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `deterministic_fallback`.
- `multilingual-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count, field:languages. Status: `deterministic_fallback`.
- `reference_selection-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `deterministic_fallback`.
- `multilingual-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count, field:languages. Status: `deterministic_fallback`.
- `distractors-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell. Status: `deterministic_fallback`.
- `ellipsis-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b. Status: `deterministic_fallback`.
- `distractors-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending. Status: `deterministic_fallback`.
- `compacted_memory-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `deterministic_fallback`.
- `multilingual-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count, field:languages. Status: `deterministic_fallback`.
- `explicit_topic_switch-03` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-08` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `long_history-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `constraint_inheritance-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `multilingual-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:languages. Status: `deterministic_fallback`.
- `constraint_inheritance-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `structured_source_reference-05` / offline / fallback: topic:secure.aggreg|cryptograph, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `reference_selection-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `deterministic_fallback`.
- `reference_selection-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `deterministic_fallback`.
- `correction-09` / offline / fallback: topic:school.meal|school.feed|meal.program, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `reference_selection-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `long_history-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-10` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `deterministic_fallback`.
- `filter_override-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:languages. Status: `deterministic_fallback`.
- `long_history-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-01` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-04` / offline / fallback: topic:sleep, topic:exten|increas|longer, topic:working.memory, field:target_count. Status: `deterministic_fallback`.
- `slang_and_typos-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `ellipsis-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth. Status: `deterministic_fallback`.
- `reference_selection-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `deterministic_fallback`.
- `distractors-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water. Status: `deterministic_fallback`.
- `structured_source_reference-06` / offline / fallback: topic:seagrass, topic:flood|surge|wave, field:target_count. Status: `deterministic_fallback`.
- `filter_override-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:languages. Status: `deterministic_fallback`.
- `multilingual-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count, field:languages. Status: `deterministic_fallback`.
- `distractors-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b. Status: `deterministic_fallback`.
- `explicit_topic_switch-09` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `slang_and_typos-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-03` / offline / fallback: topic:phyto|plant.based, topic:cadmium|\bcd\b, field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `constraint_inheritance-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `filter_override-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:languages. Status: `deterministic_fallback`.
- `compacted_memory-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `reference_selection-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `deterministic_fallback`.
- `filter_override-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:languages. Status: `deterministic_fallback`.
- `quoted_instructions-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `deterministic_fallback`.
- `multilingual-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count, field:min_year, field:languages. Status: `deterministic_fallback`.
- `multilingual-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count, field:min_year, field:languages. Status: `deterministic_fallback`.
- `quoted_instructions-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `deterministic_fallback`.
- `distractors-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic. Status: `deterministic_fallback`.
- `reference_selection-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `correction-06` / offline / fallback: topic:seagrass, topic:flood|surge|wave, field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-08` / offline / fallback: topic:perovskite, topic:encapsulat|barrier|seal, field:target_count. Status: `deterministic_fallback`.
- `ellipsis-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell. Status: `deterministic_fallback`.
- `constraint_inheritance-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `constraint_inheritance-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `slang_and_typos-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `deterministic_fallback`.
- `long_history-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `deterministic_fallback`.
- `distractors-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit. Status: `deterministic_fallback`.
- `compacted_memory-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-10` / offline / fallback: topic:judicial|judge|human.review, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `correction-07` / offline / fallback: topic:subword|byte.pair|bpe|token, topic:turkish, topic:speech|asr, field:target_count. Status: `deterministic_fallback`.
- `filter_override-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:languages. Status: `deterministic_fallback`.
- `ambiguous_reference-02` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `long_history-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-09` / offline / fallback: topic:school.meal|school.feed|meal.program, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `correction-05` / offline / fallback: topic:secure.aggreg|cryptograph, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `correction-01` / offline / fallback: topic:pneumonia|chest|lung, topic:convolution|\bcnn\b, field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `deterministic_fallback`.
- `slang_and_typos-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `deterministic_fallback`.
- `distractors-04` / offline / fallback: topic:sleep, topic:working.memory, topic:adolescen|teen|youth. Status: `deterministic_fallback`.
- `correction-08` / offline / fallback: topic:perovskite, topic:encapsulat|barrier|seal, field:target_count. Status: `deterministic_fallback`.
- `filter_override-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:languages. Status: `deterministic_fallback`.
- `long_history-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-08` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `reference_selection-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `deterministic_fallback`.
- `constraint_inheritance-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `long_history-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-04` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-09` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `ellipsis-05` / offline / fallback: topic:differential.priv, topic:federat, topic:credit|loan|lending. Status: `deterministic_fallback`.
- `ambiguous_reference-10` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `ambiguous_reference-04` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `structured_source_reference-01` / offline / fallback: topic:pneumonia|chest|lung, topic:convolution|\bcnn\b, field:target_count. Status: `deterministic_fallback`.
- `explicit_topic_switch-01` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `compacted_memory-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `slang_and_typos-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `deterministic_fallback`.
- `quoted_instructions-09` / offline / fallback: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `deterministic_fallback`.
- `filter_override-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:languages. Status: `deterministic_fallback`.
- `explicit_topic_switch-06` / offline / fallback: field:target_count. Status: `deterministic_fallback`.
- `multilingual-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count, field:languages. Status: `deterministic_fallback`.
- `ellipsis-06` / offline / fallback: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit. Status: `deterministic_fallback`.
- `ellipsis-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic. Status: `deterministic_fallback`.
- `slang_and_typos-07` / offline / fallback: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `deterministic_fallback`.
- `constraint_inheritance-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `deterministic_fallback`.
- `correction-10` / offline / fallback: topic:judicial|judge|human.review, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `distractors-03` / offline / fallback: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil. Status: `deterministic_fallback`.
- `reference_selection-02` / offline / fallback: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `deterministic_fallback`.
- `distractors-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial. Status: `deterministic_fallback`.
- `slang_and_typos-10` / offline / fallback: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `deterministic_fallback`.
- `filter_override-08` / offline / fallback: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:languages. Status: `deterministic_fallback`.
- `structured_source_reference-07` / offline / fallback: topic:subword|byte.pair|bpe|token, topic:turkish, topic:speech|asr, field:target_count. Status: `deterministic_fallback`.
- `correction-04` / offline / fallback: topic:sleep, topic:exten|increas|longer, topic:working.memory, field:target_count. Status: `deterministic_fallback`.
- `long_history-01` / offline / fallback: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `deterministic_fallback`.

## Limitations

A failed screen does not establish a general intelligence deficit or model-size effect.
Tier names do not establish model size, hardware, or an edge deployment. Compare identical case IDs when comparing models.
The planner consumes already-prepared history; routing and real long-history compaction are not end-to-end tested by the live loop.
No runtime fixes, prompt tuning, new topic-state mechanism, or baseline replacement is performed by this harness.

Raw prompts, responses, plans, timing, and provider-reported usage are in `observations.jsonl`.
The full synthetic dataset and provenance are in `cases.json` and `manifest.json`.
