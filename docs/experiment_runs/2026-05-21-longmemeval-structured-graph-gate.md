# LongMemEval Structured Graph Gate

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

Can LongMemEval become usable if graph construction uses structured benchmark
metadata instead of raw serialized conversation text?

## Motivation

The previous LongMemEval clean graph gate failed on raw context. Top hubs were
chat-template and instruction artifacts (`Chat Time`, `Here`, `Use`, `Make`,
`Can`, `However`, `Congratulations`, etc.). This did not prove that LongMemEval
is unusable; it proved that raw serialized context is the wrong graph input.

MemoryAgentBench exposes LongMemEval metadata with structured
`haystack_sessions` containing `role`, `content`, and `has_answer`. This run
tests graph gates over structured variants.

## Modes

- `raw_context`: original serialized context string.
- `content_turns`: all structured message contents, no roles or chat-time
  wrappers.
- `user_turns`: only user message contents.
- `answer_turns`: only messages marked `has_answer`.
- `answer_session_user_turns`: user turns from sessions that contain at least
  one answer-bearing message.

The analyzer uses the same proper-noun-shaped entity extraction as the benchmark
adapter, but runs in memory for fast hub diagnostics.

## Results

Command:

```bash
.venv/bin/python experiments/structured_graph_gate.py \
  --sub_dataset 'longmemeval_s*' \
  --max_samples 5 \
  --top_k 5 \
  --output experiments/results/structured_graph_gate_longmemeval_final_20260521.json
```

Summary:

| Mode | Samples | Samples with filtered hubs | Avg filtered hubs |
| --- | ---: | ---: | ---: |
| raw_context | 5 | 0 | 0.0 |
| content_turns | 5 | 5 | 5.0 |
| user_turns | 5 | 5 | 5.0 |
| answer_turns | 5 | 5 | 5.0 |
| answer_session_user_turns | 5 | 5 | 5.0 |

Representative `user_turns` / `answer_session_user_turns` hubs:

- Sample 0: Europe, Paris, Delta, Miami, Boston
- Sample 1: Rachel, Sweet Support, The Nightingale, Alex, Emma
- Sample 2: Delta, Miami, Boston, The Nightingale
- Sample 3: Instagram, Museum, Computer Science, Facebook, Data Science
- Sample 4: Disneyland, Facebook, Merrell Moab, Keen Targhee

`answer_turns` also recovers content hubs, but it remains more contaminated by
assistant discourse markers and should be treated as secondary.

## Interpretation

This changes the LongMemEval conclusion:

- Raw LongMemEval still fails the graph gate.
- Structured user-turn and answer-session-user graph construction passes a
  first clean hub gate on 5/5 samples.
- Therefore, the failure was not simply "LongMemEval is unusable." The failure
  was raw graph construction over serialized dialogue/template text.

This supports a stronger paper claim:

> Graph construction is a safety-critical part of memory maintenance. Raw
> dialogue serialization can create template hubs, while structured turn-level
> graph construction can recover content-bearing hubs.

## Next Step

Run propagation diagnostics on `answer_session_user_turns`, not raw context:

1. top-5 content hubs per sample;
2. BFS vs ATTR structural blast radius;
3. retrieval only after the structural result is stable.

Do not headline `content_turns` or `answer_turns` until residual discourse hubs
are audited.
