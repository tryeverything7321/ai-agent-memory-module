# LongMemEval Support-Retrieval Diagnostics

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

The raw LLM F1 signal on LongMemEval is weak because the baseline retriever and
prompt often fail before propagation is applied.  Does propagation still create
a retrieval-side harm signal if we remove LLM generation from the measurement?

## Setup

- Dataset: `Accurate_Retrieval / longmemeval_s*`
- Structured context mode: `answer_session_user_turns`
- Samples: 5
- Successful hub samples: 4/5; sample 1 has no actionable named trigger hub
- Hubs per successful sample: top-2 named/actionable hubs
- Queries per sample: first 20
- Embedding: `BAAI/bge-m3` on the current DooGPU `reserved9` endpoint
- LLM generation: not used for the metric
- Metric: `decay-weighted vector support hit@K`

The metric first retrieves a vector candidate pool, then ranks each candidate by
`vector_score * decay_weight`.  A query is a hit if any top-K memory contains one
of the benchmark answer strings.  This is a support-retrieval proxy, not an
answer-generation score.

Command:

```bash
.venv/bin/python experiments/support_retrieval_diagnostics.py \
  --max_samples 5 \
  --max_queries 20 \
  --num_hubs 2 \
  --top_k 5,20
```

Result JSON:

- `experiments/results/support_retrieval_1779352977.json`

## Aggregate Results

| Metric | Baseline | BFS | BFS delta | ATTR-AWARE | ATTR delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| support hit@5 | 26.25 | 16.25 | -10.00 | 26.25 | +0.00 |
| support hit@20 | 32.50 | 20.00 | -12.50 | 31.88 | -0.62 |

The deltas are averaged over 8 hub runs from 4 successful samples.

## Per-Sample Notes

| Sample | Hubs | Baseline hit@20 | BFS hit@20 | ATTR hit@20 |
| ---: | --- | ---: | ---: | ---: |
| 0 | Europe, Miami | 45 | 25, 25 | 40, 45 |
| 1 | no actionable hub | 40 | n/a | n/a |
| 2 | Miami, Delta | 20 | 20, 20 | 20, 20 |
| 3 | Instagram, Computer Science | 35 | 25, 25 | 35, 35 |
| 4 | Disneyland, Keen Targhee | 30 | 10, 10 | 30, 30 |

## Interpretation

This gives the revised paper a cleaner practical-harm story than raw LLM F1:

1. The baseline LongMemEval answer-generation score is too weak to serve as the
   main downstream metric.
2. However, answer-support memories are often present in the vector candidate
   pool.
3. Unfiltered BFS propagation downweights enough memories to push answer-support
   evidence out of decay-weighted retrieval top-k.
4. ATTR-AWARE largely preserves support retrieval in this small structured run.

This should be framed as retrieval-side evidence, not as a full end-to-end QA
claim.

## Caveats

- Exact answer-string containment undercounts paraphrased support and long
  preference-style answers.
- Baseline support hit is modest, so this remains a diagnostic rather than a
  full LongMemEval QA replication.
- Only the first 20 queries per sample were evaluated.
- This metric isolates retrieval/ranking harm; it does not measure LLM answer
  generation quality.
