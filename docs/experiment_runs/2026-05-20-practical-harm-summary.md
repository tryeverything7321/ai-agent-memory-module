# 2026-05-20 Practical-Harm Summary

## Purpose

This summary separates structural intervention from downstream retrieval effect.
The SCALE submission over-relied on broad `damage` language; the preprint should
report blast radius, collateral, retrievable loss, below-threshold memories, and
F1 delta as distinct quantities.

## Summary Table

| Dataset | Policy | Blast radius | Collateral | Retrievable loss | Below threshold | F1 delta |
|---|---|---:|---:|---:|---:|---:|
| eventqa_65536 | BFS | 3245.2 | 41.5 | 46.6 | 327.6 | -2.8 |
| eventqa_65536 | ATTR-AWARE | 791.2 | 1.2 | 1.0 | 2.0 | -0.7 |
| eventqa_131072 | BFS | 6327.3 | 33.4 | 33.6 | 708.0 | +7.2 |
| eventqa_131072 | ATTR-AWARE | 3221.6 | 1.8 | 1.8 | 7.8 | +0.7 |

## Interpretation

The most stable result is structural. BFS has a much larger blast radius and
creates far more below-threshold memories than ATTR-AWARE in both context sizes.
Retrieval F1 is not monotonic with structural damage: BFS decreases F1 on
EventQA 64K but increases F1 on EventQA 131K. This makes F1 unsuitable as the
only safety metric for memory maintenance.

The preprint should use the following framing:

> Unfiltered propagation creates large, repeatable structural interventions in
> graph memory state. These interventions can degrade or improve observed
> retrieval depending on query conditions, so accuracy alone can miss unsafe
> memory maintenance behavior.

## Caveat

The `blast radius` column is the mean number of affected memories over selected
named hubs. `Below threshold` and `retrievable loss` are sample-level post-run
state summaries available from the current benchmark runner, not independently
manual-labeled corruption counts.
