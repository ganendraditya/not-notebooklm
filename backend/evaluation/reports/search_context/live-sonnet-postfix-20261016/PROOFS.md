# Post-fix search-context checks

Resolved deterministic checks: 20/20 across two code paths and ten synthetic topics.
These checks use the real planner and compactor with fixed synthetic model output. They verify data flow and normalization, not model quality or registry results.

## Compaction bridge

The real compactor creates a system-role bridge containing a history summary. The planner recognizes the server-generated bridge marker and includes the bridge as historical context, before the current request.
Topic retained from summary through planner prompt: 10/10.
The bridge remains contextual data. Other unrecognized system-role messages are omitted.

## Language-filter precedence

When the model explicitly reports a conflict and returns English, postprocessing preserves English rather than restoring the stale Mandarin filter.
Correct model language preserved: 10/10.
Separate tests verify that a non-conflicting UI filter remains active and malformed model language fields fall back to that filter.

## Limits

The fixed responses are deliberate test inputs, not live model observations.
The compactor test supplies a fixed summary. It does not measure summarizer accuracy or how often production chats trigger compaction.
The full stress corpus remains a synthetic test set, not an estimate of production success rate.
Full inputs, prompts, and outputs: `proofs.json`.
