# 2026-05-20 Cross-Task Named-Hub Run: 5 Samples

## Purpose

This run expands the artifact-aware cross-task contamination smoke test from one
EventQA 64K sample to five samples. The goal is to check whether the named-entity
hub result survives after filtering sentence-initial function words and pronouns
such as `And`, `She`, `But`, `What`, `All`, and `These`.

## Configuration

- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 5
- Queries per sample: 100
- Hubs per sample: 5
- Hub selection: named-entity-like + triggerable fact required
- LLM: `google/gemma-4-26B-A4B-it`
- Embedding model: `BAAI/bge-m3`
- Raw local result: `experiments/results/accurate_retrieval_eventqa_65536_1779261391.json`

## Aggregate Result

| Arm | EM | F1 | Avg collateral |
|---|---:|---:|---:|
| Baseline | 11.8 | 54.4 | 0.0 |
| BFS | 10.8 | 51.6 | 41.5 |
| ATTR-AWARE | 11.8 | 53.6 | 1.2 |

Overall, BFS causes a modest aggregate F1 drop of 2.8pp while increasing
collateral damage to 41.5 memories on average. ATTR-AWARE keeps aggregate F1
within 0.7pp of baseline and reduces collateral damage to 1.2 memories on
average.

## Per-Sample Result

| Sample | Named hubs | Baseline F1 | BFS F1 | ATTR F1 | BFS collateral | ATTR collateral |
|---:|---|---:|---:|---:|---:|---:|
| 0 | Debbie, Marianne, Kali, Lucian, Sue | 67.6 | 58.3 | 67.1 | 29.4 | 1.0 |
| 1 | Bishop, Paris, Louis, God, Madame | 62.1 | 58.6 | 59.0 | 20.4 | 1.0 |
| 2 | Pascal, Shayne, Marseilles, Blaire, Abrielle | 42.5 | 34.6 | 42.6 | 32.0 | 1.2 |
| 3 | Bea, Miss Brevin, Brevin, Kyra, Miss Rosie | 56.1 | 51.1 | 55.2 | 70.8 | 1.2 |
| 4 | Ladonna, Clarisse, Alain, Edie Arkadyevitch, Karissa | 43.7 | 55.2 | 44.3 | 55.0 | 1.6 |

## Interpretation

The result supports the structural collateral-damage claim after artifact-aware
hub filtering: across all five samples, BFS creates far more collateral damage
than ATTR-AWARE. The retrieval-degradation claim is weaker and more nuanced:
four of five samples show BFS F1 drops, but sample 4 shows a large F1 increase.
This suggests that retrieval impact is query- and sample-dependent, possibly
because broad downweighting can suppress distractors in some cases.

For the next version of the paper, the strongest defensible claim is therefore:

> Named-entity hub propagation consistently creates large collateral structural
> changes, while downstream retrieval harm appears in most but not all sampled
> settings.

The preprint should not claim that every BFS propagation run degrades retrieval.
It should separate structural collateral damage from downstream task impact, and
use cross-task retrieval as evidence of practical risk rather than as the sole
definition of harm.

## Follow-Up

- Add confidence intervals over more samples before using aggregate retrieval
  degradation as a headline number.
- Investigate sample 4 to determine whether BFS improved F1 by downweighting
  retrieval distractors.
- Add a false-negative audit for ATTR-AWARE to measure missed true dependencies.
- Replicate on a second benchmark family or memory construction pipeline.
