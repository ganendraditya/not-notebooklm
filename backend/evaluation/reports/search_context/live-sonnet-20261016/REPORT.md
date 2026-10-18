# Search-context evaluation

Source commit: `e2fbfc1745c63de7b00f320c4785244a57c93a8a`. Planner SHA-256: `beee4236928ac8178046114a6922fd24c41194c27ec76ac7bed1100bdfea74b4`.
Synthetic cases: 140. Completed observations: 430/430 planned.

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

- fast: `ag/claude-sonnet-4-6`; temperature 0.1.

## Automated screen

Pass rates below are conditional on a completed non-transport observation. Coverage must be read alongside them.

| Tier | Condition | Passed / scorable | Transport errors | Diagnostic-only |
| --- | --- | --- | --- | --- |
| fast | explicit | 120/120 | 0 | 20 |
| fast | history | 100/120 | 0 | 20 |
| fast | no_history | 10/120 | 0 | 20 |
| fast | summary_as_user | 10/10 | 0 | 0 |

## History condition by category

| Tier | Category | Pass / scorable |
| --- | --- | --- |
| fast | ambiguous_reference | 0/0 |
| fast | compacted_memory | 0/10 |
| fast | constraint_inheritance | 10/10 |
| fast | correction | 10/10 |
| fast | distractors | 10/10 |
| fast | ellipsis | 10/10 |
| fast | explicit_topic_switch | 10/10 |
| fast | filter_override | 0/10 |
| fast | long_history | 10/10 |
| fast | multilingual | 10/10 |
| fast | quoted_instructions | 10/10 |
| fast | reference_selection | 10/10 |
| fast | slang_and_typos | 10/10 |
| fast | structured_source_reference | 0/0 |

## Paired controls

- fast: history fail, explicit pass: 20 paired cases.
- fast: history pass, explicit pass: 100 paired cases.

## Observations requiring inspection

- `slang_and_typos-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `reference_selection-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `slang_and_typos-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-05` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-05` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-06` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-06` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-07` / fast / history: field:target_count. Status: `invalid_model_output`.
- `multilingual-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending. Status: `model_response`.
- `ambiguous_reference-07` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `constraint_inheritance-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `ellipsis-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol. Status: `invalid_model_output`.
- `compacted_memory-04` / fast / history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-06` / fast / history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `correction-02` / fast / no_history: topic:base.edit, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `filter_override-05` / fast / history: field:languages. Status: `model_response`.
- `filter_override-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:languages. Status: `model_response`.
- `ellipsis-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water. Status: `invalid_model_output`.
- `compacted_memory-02` / fast / history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-03` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-03` / fast / history: field:target_count. Status: `invalid_model_output`.
- `compacted_memory-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `ellipsis-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil. Status: `invalid_model_output`.
- `long_history-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `constraint_inheritance-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `constraint_inheritance-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `distractors-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol. Status: `invalid_model_output`.
- `quoted_instructions-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.
- `correction-03` / fast / no_history: topic:phyto|plant.based, topic:cadmium|\bcd\b, field:target_count. Status: `invalid_model_output`.
- `long_history-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-02` / fast / history: topic:base.edit, topic:hematopo|haematopo|stem.cell. Status: `model_response`.
- `structured_source_reference-02` / fast / no_history: topic:base.edit, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `ellipsis-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial. Status: `invalid_model_output`.
- `multilingual-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count, field:languages. Status: `invalid_model_output`.
- `filter_override-03` / fast / history: field:languages. Status: `model_response`.
- `filter_override-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:languages. Status: `model_response`.
- `slang_and_typos-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `multilingual-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count, field:languages. Status: `invalid_model_output`.
- `reference_selection-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `distractors-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell. Status: `invalid_model_output`.
- `multilingual-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count, field:languages. Status: `invalid_model_output`.
- `ellipsis-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b. Status: `invalid_model_output`.
- `distractors-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending. Status: `invalid_model_output`.
- `compacted_memory-01` / fast / history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.
- `multilingual-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count, field:languages. Status: `invalid_model_output`.
- `long_history-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `constraint_inheritance-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `multilingual-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:languages. Status: `invalid_model_output`.
- `structured_source_reference-05` / fast / history: topic:secure.aggreg|cryptograph, topic:federat, topic:credit|loan|lending. Status: `model_response`.
- `constraint_inheritance-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `structured_source_reference-05` / fast / no_history: topic:secure.aggreg|cryptograph, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `reference_selection-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `reference_selection-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.
- `correction-09` / fast / no_history: topic:school.meal|school.feed|meal.program, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `reference_selection-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `long_history-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `filter_override-10` / fast / history: field:languages. Status: `model_response`.
- `quoted_instructions-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `filter_override-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:languages. Status: `model_response`.
- `ambiguous_reference-01` / fast / history: field:target_count. Status: `invalid_model_output`.
- `long_history-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-04` / fast / history: topic:sleep, topic:exten|increas|longer, topic:working.memory. Status: `model_response`.
- `ambiguous_reference-01` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-04` / fast / no_history: topic:sleep, topic:exten|increas|longer, topic:working.memory, field:target_count. Status: `invalid_model_output`.
- `slang_and_typos-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `ellipsis-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth. Status: `invalid_model_output`.
- `structured_source_reference-06` / fast / history: topic:seagrass, topic:flood|surge|wave. Status: `model_response`.
- `reference_selection-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `distractors-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water. Status: `invalid_model_output`.
- `filter_override-09` / fast / history: field:languages. Status: `model_response`.
- `structured_source_reference-06` / fast / no_history: topic:seagrass, topic:flood|surge|wave, field:target_count. Status: `invalid_model_output`.
- `filter_override-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:languages. Status: `model_response`.
- `multilingual-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count, field:languages. Status: `invalid_model_output`.
- `distractors-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b. Status: `invalid_model_output`.
- `structured_source_reference-03` / fast / history: topic:phyto|plant.based, topic:cadmium|\bcd\b. Status: `model_response`.
- `slang_and_typos-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-09` / fast / history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-03` / fast / no_history: topic:phyto|plant.based, topic:cadmium|\bcd\b, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `filter_override-07` / fast / history: field:languages. Status: `model_response`.
- `constraint_inheritance-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `filter_override-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:languages. Status: `model_response`.
- `compacted_memory-05` / fast / history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `filter_override-06` / fast / history: field:languages. Status: `model_response`.
- `filter_override-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:languages. Status: `model_response`.
- `reference_selection-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `multilingual-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count, field:min_year, field:languages. Status: `invalid_model_output`.
- `multilingual-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count, field:min_year, field:languages. Status: `invalid_model_output`.
- `quoted_instructions-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `distractors-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic. Status: `invalid_model_output`.
- `structured_source_reference-08` / fast / history: topic:perovskite, topic:encapsulat|barrier|seal. Status: `model_response`.
- `reference_selection-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `correction-06` / fast / no_history: topic:seagrass, topic:flood|surge|wave, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-08` / fast / no_history: topic:perovskite, topic:encapsulat|barrier|seal, field:target_count. Status: `invalid_model_output`.
- `ellipsis-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell. Status: `invalid_model_output`.
- `constraint_inheritance-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `constraint_inheritance-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `slang_and_typos-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `long_history-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `distractors-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit. Status: `invalid_model_output`.
- `compacted_memory-08` / fast / history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-10` / fast / history: topic:judicial|judge|human.review, topic:bail|pretrial|pre.trial. Status: `model_response`.
- `compacted_memory-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-10` / fast / no_history: topic:judicial|judge|human.review, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `filter_override-04` / fast / history: field:languages. Status: `model_response`.
- `correction-07` / fast / no_history: topic:subword|byte.pair|bpe|token, topic:turkish, topic:speech|asr, field:target_count. Status: `invalid_model_output`.
- `filter_override-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:languages. Status: `model_response`.
- `ambiguous_reference-02` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-02` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-09` / fast / history: topic:school.meal|school.feed|meal.program, topic:attendan|enrol. Status: `model_response`.
- `long_history-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-09` / fast / no_history: topic:school.meal|school.feed|meal.program, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `correction-05` / fast / no_history: topic:secure.aggreg|cryptograph, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `correction-01` / fast / no_history: topic:pneumonia|chest|lung, topic:convolution|\bcnn\b, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-03` / fast / history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil, field:target_count. Status: `invalid_model_output`.
- `quoted_instructions-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `distractors-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth. Status: `invalid_model_output`.
- `slang_and_typos-04` / fast / no_history: topic:sleep, topic:working.memory, topic:adolescen|teen|youth, field:target_count. Status: `invalid_model_output`.
- `filter_override-01` / fast / history: field:languages. Status: `model_response`.
- `filter_override-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:languages. Status: `model_response`.
- `correction-08` / fast / no_history: topic:perovskite, topic:encapsulat|barrier|seal, field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-08` / fast / history: field:target_count. Status: `invalid_model_output`.
- `long_history-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-08` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `reference_selection-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending, field:target_count. Status: `invalid_model_output`.
- `constraint_inheritance-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `long_history-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-07` / fast / history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-09` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-09` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ellipsis-05` / fast / no_history: topic:differential.priv, topic:federat, topic:credit|loan|lending. Status: `invalid_model_output`.
- `ambiguous_reference-10` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-10` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-01` / fast / history: topic:pneumonia|chest|lung, topic:convolution|\bcnn\b. Status: `model_response`.
- `ambiguous_reference-04` / fast / history: field:target_count. Status: `invalid_model_output`.
- `ambiguous_reference-04` / fast / no_history: field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-01` / fast / no_history: topic:pneumonia|chest|lung, topic:convolution|\bcnn\b, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `compacted_memory-10` / fast / history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `filter_override-02` / fast / history: field:languages. Status: `model_response`.
- `quoted_instructions-09` / fast / no_history: topic:cash.transfer|conditional.transfer|monetary.transfer, topic:school|educat, topic:attendan|enrol, field:target_count. Status: `invalid_model_output`.
- `slang_and_typos-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit, field:target_count. Status: `invalid_model_output`.
- `filter_override-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:languages. Status: `model_response`.
- `multilingual-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:target_count, field:languages. Status: `invalid_model_output`.
- `ellipsis-06` / fast / no_history: topic:mangrove, topic:flood|surge|wave, topic:restor|rehabilit. Status: `invalid_model_output`.
- `ellipsis-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic. Status: `invalid_model_output`.
- `slang_and_typos-07` / fast / no_history: topic:morpholog|segment, topic:turkish, topic:speech|asr|acoustic, field:target_count. Status: `invalid_model_output`.
- `constraint_inheritance-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:min_year, field:open_access_only, field:scopus_quartiles, field:exclude_preprints. Status: `invalid_model_output`.
- `distractors-03` / fast / no_history: topic:biochar, topic:cadmium|\bcd\b, topic:rice|paddy|soil. Status: `invalid_model_output`.
- `correction-10` / fast / no_history: topic:judicial|judge|human.review, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `reference_selection-02` / fast / no_history: topic:crispr|gene.edit|genome.edit, topic:off.target, topic:hematopo|haematopo|stem.cell, field:target_count. Status: `invalid_model_output`.
- `distractors-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial. Status: `invalid_model_output`.
- `filter_override-08` / fast / history: field:languages. Status: `model_response`.
- `filter_override-08` / fast / no_history: topic:perovskite, topic:solar|photovoltaic, topic:humid|moisture|water, field:languages. Status: `model_response`.
- `structured_source_reference-07` / fast / history: topic:subword|byte.pair|bpe|token, topic:turkish, topic:speech|asr. Status: `model_response`.
- `slang_and_typos-10` / fast / no_history: topic:procedural|process|due.process, topic:fair|justice, topic:bail|pretrial|pre.trial, field:target_count. Status: `invalid_model_output`.
- `structured_source_reference-07` / fast / no_history: topic:subword|byte.pair|bpe|token, topic:turkish, topic:speech|asr, field:target_count. Status: `invalid_model_output`.
- `correction-04` / fast / no_history: topic:sleep, topic:exten|increas|longer, topic:working.memory, field:target_count. Status: `invalid_model_output`.
- `long_history-01` / fast / no_history: topic:pneumonia|chest|lung, topic:vision.transform|transformer|\bvit\b, field:target_count. Status: `invalid_model_output`.

## Limitations

A failed screen does not establish a general intelligence deficit or model-size effect.
Tier names do not establish model size, hardware, or an edge deployment. Compare identical case IDs when comparing models.
The planner consumes already-prepared history; routing and real long-history compaction are not end-to-end tested by the live loop.
No runtime fixes, prompt tuning, new topic-state mechanism, or baseline replacement is performed by this harness.

Raw prompts, responses, plans, timing, and provider-reported usage are in `observations.jsonl`.
The full synthetic dataset and provenance are in `cases.json` and `manifest.json`.
