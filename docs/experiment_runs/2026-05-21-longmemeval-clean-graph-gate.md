# LongMemEval Clean Graph Gate

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

After filtering known function-word and chat-template artifacts, does
LongMemEval still provide stable content-entity hubs suitable for propagation
experiments?

## Setup

- Dataset: `Accurate_Retrieval / longmemeval_s*`
- Samples: 5
- Mode: `--named_entity_hubs --list_hubs_only`
- Queries: disabled with `--max_queries 0`
- Embeddings: `--mock_embedding`; acceptable because this is hub diagnostics
  only.

Command:

```bash
.venv/bin/python experiments/benchmark_accurate_retrieval.py \
  --sub_dataset 'longmemeval_s*' \
  --max_samples 5 \
  --max_queries 0 \
  --num_hubs 5 \
  --named_entity_hubs \
  --list_hubs_only \
  --mock_embedding \
  --disable_graph_persist
```

## First Filter Pass

After filtering the initially observed artifacts (`Chat Time`, `Here`, `Use`,
`Make`, `Can`, etc.), LongMemEval still surfaced instruction/template hubs:

- Sample 0: `However`
- Sample 1: `Congratulations`, `However`, `Good`, `Your`
- Sample 2: `Choose`, `Congratulations`, `Mix`, `Focus`, `Many`
- Sample 3: `However`, `Good`, `Additional Tips`, `Some`
- Sample 4: `However`, `Create`, `Add`, `Congratulations`, `Enjoy`

Result JSON:

- `experiments/results/accurate_retrieval_longmemeval_s*_1779337798.json`

## Expanded Filter Pass

After adding the observed instruction/template terms, the filtered hubs became:

- Sample 0: no actionable hub
- Sample 1: no actionable hub
- Sample 2: `Many`, `Try` before final artifact update
- Sample 3: no actionable hub
- Sample 4: `Research`

Result JSON:

- `experiments/results/accurate_retrieval_longmemeval_s*_1779337845.json`

`Many` and `Try` were then added to the artifact list because they are generic
instruction/common terms, not content entities.

## Interpretation

LongMemEval does not pass the Clean Graph Gate under the current rule-based
entity extraction pipeline. Filtering removes the most obvious artifacts, but it
also leaves too few stable content entities for a credible propagation experiment.

This is not evidence that the paper's EventQA findings are wrong. It is evidence
that cross-family replication cannot be claimed by naively applying the same
co-occurrence graph extraction to LongMemEval. LongMemEval is better used as
evidence of graph-construction brittleness and template-hub risk, not as a
headline replication benchmark.

## Decision

Do not spend GPU or retrieval-query budget on LongMemEval propagation experiments
until graph construction is changed. The next credible path is:

1. typed/NER-normalized graph construction, or
2. a controlled synthetic benchmark with known dependency structure, or
3. another real benchmark with cleaner entity-bearing memories.
