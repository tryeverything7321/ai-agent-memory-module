# LongMemEval Structured Propagation Diagnostics

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

After LongMemEval passes a structured clean hub gate, does unfiltered
co-occurrence propagation still create structural collateral damage?

## Setup

- Dataset: `Accurate_Retrieval / longmemeval_s*`
- Samples: 5
- Structured context mode: `answer_session_user_turns`
- Hub selection: top-5 named/actionable hubs
- Queries: disabled with `--max_queries 0`
- Embeddings: `--mock_embedding`; this run is structural only and should not be
  used for retrieval-quality claims.

Command:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset 'longmemeval_s*' \
  --max_samples 5 \
  --max_queries 0 \
  --structured_context_mode answer_session_user_turns \
  --named_entity_hubs \
  --num_hubs 5 \
  --mock_embedding \
  --disable_graph_persist
```

Result JSON:

- `experiments/results/accurate_retrieval_longmemeval_s*_1779349227.json`

## Results

| Sample | Status | Hubs | BFS collateral | ATTR collateral |
| ---: | --- | --- | ---: | ---: |
| 0 | ok | Europe, Miami, Paris, Rome, Delta | 63.0 | 1.0 |
| 1 | skipped | no actionable trigger hub | n/a | n/a |
| 2 | ok | Miami, Delta, Boston, American Airlines, The Nightingale | 56.8 | 1.4 |
| 3 | ok | Instagram, Computer Science, Museum, Facebook, Data Science | 48.8 | 1.0 |
| 4 | ok | Disneyland, Keen Targhee, Facebook, Merrell Moab, Digital Marketing Institute | 68.6 | 1.6 |

Successful samples only:

- Mean BFS collateral: 59.3 memories
- Mean ATTR collateral: 1.25 memories
- Mean BFS affected count: 1287.2
- Mean ATTR affected count: 645.15

## Interpretation

This substantially improves the external-validity story:

1. Raw LongMemEval graph construction fails because serialized conversation text
   creates template/instruction hubs.
2. Structured metadata construction recovers content-bearing hubs.
3. Under those structured hubs, unfiltered BFS still creates large structural
   collateral damage.
4. ATTR-AWARE sharply reduces below-threshold collateral, although its raw
   affected counts can remain high.

This should be framed as a structural diagnostic, not a retrieval result. The
run used mock embeddings and disabled queries.

## Caveats

- Sample 1 had no actionable trigger hub after filtering and was excluded from
  propagation averages.
- The benchmark adapter's subject-key construction is still rule-based, so a
  typed NER or event/entity parser would be a stronger graph construction
  pipeline.
- Retrieval impact remains unmeasured in this run.

## Paper Use

This can now serve as a non-EventQA real benchmark stress test, but only under
the structured graph construction condition. The correct claim is:

> LongMemEval fails under raw serialized graph construction, but structured
> turn-level graph construction recovers content hubs and reproduces the
> structural collateral pattern.
