# 2026-05-20 ATTR-AWARE Audit Candidates

## Purpose

Prepare a manual audit set for measuring ATTR-AWARE missed-dependency risk.

## Configuration

- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 3
- Hubs per sample: 5
- Queries: 0
- Hub selection: named-entity-like + triggerable fact required
- Embedding: mock embedding
- Audit trace: enabled
- Audit trace limit: 100 affected memories per hub

## Candidate Buckets

- `bfs_reached_attr_blocked`: potential false negatives for ATTR-AWARE.
- `attr_reached`: accepted propagation controls.

## Smoke Result

The current candidate file contains 50 items, all in the
`bfs_reached_attr_blocked` bucket. This is enough to begin a missed-dependency
pilot audit, but not enough for a balanced audit because no `attr_reached`
controls were sampled under the current cap/ordering.

## Next Labeling Step

Use `docs/attr_aware_labeling_protocol.md` and label each item as
`SHOULD_PROPAGATE`, `SHOULD_NOT_PROPAGATE`, or `BORDERLINE`.

For a balanced final audit, update the sampler to stratify `attr_reached`
examples directly from ATTR-AWARE traces rather than relying only on overlap
with BFS trace samples.
