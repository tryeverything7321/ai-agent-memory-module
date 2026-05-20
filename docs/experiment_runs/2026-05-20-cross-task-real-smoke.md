# 2026-05-20 Cross-task Real Smoke

Branch: `research/20260520-preprint-followup`

Purpose: verify that the post-SCALE cross-task experiment runs with real embedding and LLM endpoints after switching to named-entity, triggerable hubs.

This is an early smoke result, not yet the final paper table. It uses one `eventqa_65536` sample and five named-entity hubs.

## Configuration

- Dataset: `MemoryAgentBench / Accurate_Retrieval / eventqa_65536`
- Samples: 1
- Queries: 100
- Hub selection: named-entity-like and triggerable fact required
- Hubs: `Debbie`, `Marianne`, `Kali`, `Lucian`, `Sue`
- LLM: `google/gemma-4-26B-A4B-it`
- Embedding: `BAAI/bge-m3`
- Policies: baseline/no propagation, BFS, ATTR-AWARE

## Aggregate Result

| Policy | EM | F1 | Avg collateral |
| --- | ---: | ---: | ---: |
| Baseline | 23.0 | 67.6 | 0.0 |
| BFS | 20.4 | 58.0 | 29.4 |
| ATTR-AWARE | 23.0 | 67.1 | 1.0 |

Interpretation:

- BFS causes a `-9.6pp` F1 drop relative to baseline on 100 unrelated retrieval queries.
- ATTR-AWARE stays within `-0.5pp` F1 of baseline.
- BFS creates much larger collateral damage than ATTR-AWARE: `29.4` vs `1.0` average collateral memories.

## Per-hub Result

| Hub | Degree | BFS F1 | BFS affected | BFS collateral | ATTR F1 | ATTR affected | ATTR collateral |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Debbie | 715 | 57.3 | 3381 | 32 | 67.6 | 0 | 1 |
| Marianne | 589 | 58.0 | 3064 | 15 | 66.1 | 1298 | 1 |
| Kali | 473 | 57.3 | 2578 | 10 | 64.6 | 2600 | 1 |
| Lucian | 407 | 60.6 | 3321 | 39 | 69.5 | 470 | 1 |
| Sue | 351 | 56.6 | 3484 | 51 | 67.6 | 0 | 1 |

## Notes

- A previous 5-hub smoke selected `Kerry`, which was named-entity-like but had no triggerable fact. The hub selector now requires a triggerable fact.
- `There` was also added to the function-word/pronoun filter after it surfaced as an artifact hub.
- The next scale-up should run the same setup over more samples or more hubs after deciding the LLM-call budget.

