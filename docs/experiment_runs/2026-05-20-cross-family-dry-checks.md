# 2026-05-20 Cross-Family Dry Checks

## Purpose

This note records dry checks for the planned cross-family replication. The goal
was to find a non-EventQA source that can support named-entity hub propagation
without obvious extraction artifacts.

## LongMemEval

Initial dry check exposed a chunking bug: each 1.6M-character context was treated
as one chunk because the chunker split only on line boundaries. After fixing
single-long-line chunking, LongMemEval produced roughly 97-105 chunks per sample.

However, the top hubs remained prompt/template artifacts:

- `Chat Time`
- `Here`
- `However`
- `Avoid`
- `Start`
- `Use`
- `Make`
- `Remember`
- `Can`
- `Check`
- `Tips`

Conclusion: do not use LongMemEval for headline cross-family claims until a
dataset-specific preprocessing pass removes chat-template artifacts or the graph
construction is made more semantic.

## EventQA Full

`eventqa_full` dry check produced mostly content entities after adding `Then` to
the artifact filter. Example hubs:

- Sample 0: Debbie, Edgar, Atlanta, Kali, Yankees
- Sample 1: Paris, Saint, Rue, France, God
- Sample 2: Brayan Annabel, Adan, Shayne, Nestor, Blaire
- Sample 3: Bea, Sylvia, Isaiah, Kayla, Donald
- Sample 4: Ladonna, Clarisse, Karissa, Alain, Alexey Alexandrovitch

Conclusion: `eventqa_full` is suitable as a larger-scale EventQA robustness run,
but it is not a true cross-family replication.

## Full-Run Attempt

A full `eventqa_full` run was started but stopped after sample 1 began because
sample 1 memory construction alone took about 10 minutes. Sample 0 already showed
an important edge case: BFS created very large affected counts, while ATTR-AWARE
also produced extremely high affected counts for some hubs despite lower
collateral. This suggests full-context runs should be scheduled as overnight jobs
and analyzed separately for affected-count vs. collateral divergence.

## Next Decision

For top-tier evidence, the next cross-family step should not be a naive
LongMemEval run. It should be one of:

1. Add chat-template filtering for LongMemEval and rerun dry checks.
2. Use another benchmark family with cleaner entity-bearing memory text.
3. Build a controlled synthetic graph-memory benchmark where entity/dependency
   structure is known.
