# ATTR-AWARE Balanced Audit Set

Date: 2026-05-22

Branch: `research/20260520-preprint-followup`

## Question

Reviewers objected that ATTR-AWARE reduces collateral propagation but leaves the
cost of under-propagation unmeasured.  Before manual labeling, we need a
balanced audit set containing both:

- `bfs_reached_attr_blocked`: possible ATTR-AWARE false negatives;
- `attr_reached`: accepted propagation controls.

## Input Run

- Source result: `experiments/results/accurate_retrieval_eventqa_65536_1779268987.json`
- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 3
- Hubs per sample: 5
- Queries: disabled
- Embedding: mock embedding
- Audit trace limit: 100 affected memories per hub

## Sampler Fix

The previous sampler populated `attr_reached` only when an ATTR-AWARE affected
memory also appeared in the capped BFS trace sample.  That made the candidate
set look one-sided even when ATTR-AWARE had accepted propagation examples.

The updated sampler now:

1. samples `bfs_reached_attr_blocked` from BFS trace minus ATTR trace;
2. samples `attr_reached` directly from ATTR-AWARE traces;
3. round-robins across `(sample_idx, hub)` groups before filling the bucket cap.

This prevents the audit set from being dominated by a single hub.

## Output

Raw candidate file, kept out of git because it contains long benchmark memory
text:

- `experiments/results/attr_audit_balanced_candidates_20260522.json`

Summary:

| Bucket | Count |
| --- | ---: |
| `bfs_reached_attr_blocked` | 50 |
| `attr_reached` | 50 |

Bucket coverage:

| Bucket | Sample / hub groups |
| --- | ---: |
| `bfs_reached_attr_blocked` | 15 |
| `attr_reached` | 9 |

## Next Manual Labeling Step

Use `docs/attr_aware_labeling_protocol.md`.

Each row should be labeled as:

- `SHOULD_PROPAGATE`
- `SHOULD_NOT_PROPAGATE`
- `BORDERLINE`

The key paper metric is:

```text
ATTR-AWARE false negative rate =
  SHOULD_PROPAGATE among bfs_reached_attr_blocked / labeled bfs_reached_attr_blocked
```

The matching control metric is:

```text
ATTR-AWARE accepted-propagation precision =
  SHOULD_PROPAGATE among attr_reached / labeled attr_reached
```

## Paper Use

This is not yet a result table because labels are still blank.  It is now a
proper manual-audit input set.  The paper should not claim an ATTR-AWARE false
negative rate until this file is labeled.
