# Artificial Hub Injection: Project Note

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

Can a repeated generic phrase fabricate a triggerable graph entity and amplify
invalidation propagation, even when the phrase is not a natural content entity?

## Setup

- Dataset: `Accurate_Retrieval / eventqa_65536`
- Samples: 5
- Injection phrase: `Project Note`
- Repetitions: 0, 5, 20, 50, 200
- Trigger: forced `--hub_entity "Project Note"`
- Queries: disabled with `--max_queries 0`; this run measures graph topology,
  propagation, and retrievability threshold effects only.
- Embeddings: `--mock_embedding`; acceptable for this structural run because no
  retrieval queries are evaluated, but not valid for retrieval-quality claims.

Command template:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset eventqa_65536 \
  --max_samples 5 \
  --max_queries 0 \
  --num_hubs 1 \
  --hub_entity "Project Note" \
  --inject_phrase "Project Note" \
  --inject_repetitions <N> \
  --mock_embedding \
  --disable_graph_persist
```

## Forced-Trigger Results

| Repetitions | Avg Project Note degree | BFS affected | BFS collateral | ATTR affected | ATTR collateral |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 5 | 20.0 | 3185.8 | 38.4 | 423.6 | 1.0 |
| 20 | 61.0 | 3384.2 | 43.0 | 418.6 | 1.0 |
| 50 | 108.6 | 3425.4 | 47.0 | 406.6 | 1.0 |
| 200 | 276.0 | 3461.0 | 38.4 | 320.2 | 0.8 |

Per-sample forced-trigger rows are stored in:

- `experiments/results/accurate_retrieval_eventqa_65536_1779337006.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337015.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337023.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337031.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337111.json`

## Hub-Ranking Check

With `--list_hubs_only --num_hubs 10`, `Project Note` does not enter the raw
top-10 at 5, 20, or 50 repetitions. At 200 repetitions it enters the raw top-10
in 4 of 5 samples:

| Sample | Rank at 200 reps | Degree | Top competing hubs |
| ---: | ---: | ---: | --- |
| 0 | 4 | 593 | Debbie, And, She |
| 1 | outside top-10 | n/a | He, In, This |
| 2 | 5 | 141 | Pascal, Shayne, He, Marseilles |
| 3 | 4 | 155 | Mr, Bea, It |
| 4 | 10 | 168 | He, And, But, She, Ladonna |

Hub-ranking JSON:

- `experiments/results/accurate_retrieval_eventqa_65536_1779337065.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337071.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337076.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337082.json`
- `experiments/results/accurate_retrieval_eventqa_65536_1779337102.json`

## Interpretation

This supports a narrower claim than "any small injection takes over the graph."
The correct claim is:

1. A repeated generic phrase can create a triggerable artificial entity.
2. Once triggerable, even low repetition counts can produce large BFS blast
   radius and retrievability loss from that artificial entity.
3. Larger repetition counts can push the artificial phrase into raw top-hub
   diagnostics, but natural content hubs and extraction artifacts remain strong
   competitors.
4. ATTR-AWARE sharply limits collateral retrievability loss even when its raw
   affected count is nonzero.

This strengthens the paper's revised thesis: graph-memory risk is not only a
property of natural named-entity hubs; it is also affected by graph-construction
choices and repeated template/generic language. The paper should present this
as a topology-construction vulnerability or stress test, not as a completed
retrieval attack.

## Caveats

- Query evaluation was intentionally disabled; these numbers do not support
  retrieval F1 claims.
- Mock embeddings were used; graph extraction and propagation are the relevant
  surfaces here, but retrieval experiments need the real embedding endpoint.
- `Project Note` does not enter top-10 at 5/20/50 repetitions; those conditions
  demonstrate targeted triggerability, not top-hub takeover.
- Raw top hubs still include function-word or title artifacts, reinforcing the
  need for clean graph gates before headline claims.
