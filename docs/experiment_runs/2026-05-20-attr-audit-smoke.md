# 2026-05-20 ATTR-AWARE Audit Trace Smoke

## Purpose

This smoke run verifies that the benchmark runner can now emit compact audit
traces for manual dependency labeling. The goal is to support the next paper
claim that ATTR-AWARE reduces over-propagation while still requiring an explicit
under-propagation audit.

## Configuration

- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 1
- Hubs: 2 named/actionable hubs
- Queries: 0
- Embedding: mock embedding
- Audit trace: enabled
- Audit trace limit: 20 affected memories per hub
- Raw local result: `experiments/results/accurate_retrieval_eventqa_65536_1779265866.json`
- Candidate file: `experiments/results/attr_audit_candidates_smoke_20260520.json`

## Result

The sampler produced 20 audit candidates, all in the
`bfs_reached_attr_blocked` bucket. This is expected for the first smoke because
the sampled BFS affected set contains many memories that ATTR-AWARE did not
reach.

## Interpretation

The pipeline is now ready to create manual labeling sets from future trace-enabled
runs:

- `bfs_reached_attr_blocked`: possible ATTR-AWARE false negatives if the target
  memory truly depends on the invalidated source memory.
- `attr_reached`: propagation accepted by both BFS and ATTR-AWARE, useful as a
  sanity/control bucket.

The next audit run should use a larger trace limit and more hubs so both buckets
are populated, then label a balanced set by the protocol in
`docs/attr_aware_labeling_protocol.md`.
