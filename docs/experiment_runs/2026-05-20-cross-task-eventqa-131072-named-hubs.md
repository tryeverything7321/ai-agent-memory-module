# 2026-05-20 Cross-Task Named-Hub Run: EventQA 131K

## Why This Run Replaced the Planned 10-Sample Run

The planned `eventqa_65536` 10-sample replication is not available in the current
MemoryAgentBench `Accurate_Retrieval` split: `eventqa_65536`, `eventqa_131072`,
`eventqa_full`, and `longmemeval_s*` each expose 5 samples, while the two RULER
QA sources expose 1 sample each. Therefore, the next useful replication is a
larger-context source rather than more samples within the same source.

## Configuration

- Dataset: `Accurate_Retrieval / eventqa_131072`
- Samples: 5
- Queries per sample: 100
- Hubs per sample: 5
- Hub selection: named-entity-like + triggerable fact required
- LLM: `google/gemma-4-26B-A4B-it`
- Embedding model: `BAAI/bge-m3`
- Raw local result: `experiments/results/accurate_retrieval_eventqa_131072_1779265059.json`

## Aggregate Result

| Arm | EM | F1 | Avg collateral |
|---|---:|---:|---:|
| Baseline | 9.2 | 45.0 | 0.0 |
| BFS | 9.9 | 52.2 | 33.4 |
| ATTR-AWARE | 8.6 | 45.8 | 1.8 |

## Per-Sample Result

| Sample | Named hubs | Baseline F1 | BFS F1 | ATTR F1 | BFS collateral | ATTR collateral |
|---:|---|---:|---:|---:|---:|---:|
| 0 | Debbie, Marianne, Kali, Edgar, Atlanta | 45.6 | 45.5 | 47.3 | 35.2 | 1.2 |
| 1 | Paris, Bishop, Saint, God, Louis | 51.2 | 52.6 | 54.8 | 11.0 | 1.8 |
| 2 | Pascal, Armando, Shayne, Marseilles, Corbin | 42.2 | 52.1 | 40.3 | 27.2 | 1.2 |
| 3 | Bea, Brevin, Sylvia, Miss Brevin, Kyra | 44.3 | 46.8 | 38.7 | 30.4 | 3.4 |
| 4 | Clarisse, Alain, Ladonna, Karissa, Edie Arkadyevitch | 42.0 | 64.0 | 47.7 | 63.4 | 1.4 |

## Interpretation

This larger-context run reinforces the structural collateral-damage claim but
does not support a simple retrieval-degradation headline. BFS increases aggregate
F1 by 7.2pp on EventQA 131K, while still causing high collateral structural
damage. ATTR-AWARE keeps collateral much lower, but it is not completely
cost-free: sample 3 shows ATTR-AWARE collateral rising to 3.4 on average, and
some hubs produce large affected-memory counts despite low collateral.

The revised paper should therefore frame downstream retrieval as instability
under broad structural intervention, not as guaranteed degradation:

> Unfiltered BFS propagation reliably creates a much larger structural blast
> radius than ATTR-AWARE. Its downstream retrieval effect is unstable: it can
> degrade retrieval, improve retrieval by suppressing distractors, or leave
> aggregate F1 roughly unchanged depending on graph/query conditions.

## Follow-Up

- Analyze retrieval gains in EventQA 131K to determine whether BFS suppresses
  distractors or changes refusal behavior.
- Add a practical-harm table that separates blast radius, collateral count, and
  retrieval F1.
- Prioritize the ATTR-AWARE audit: larger contexts show that ATTR-AWARE can still
  traverse many memories for specific hubs even when collateral remains low.
