# Controlled Synthetic Memory Graph Smoke

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

When true memory dependency and co-occurrence topology are separated by
construction, does unfiltered BFS over co-occurrence create false-positive
invalidation?

## Setup

- Entities: 30
- Dependency chains: 10
- Chain length: 5
- Trigger depth: 2
- Variants:
  - `clean`: no extra noise, no artificial hub
  - `noisy`: 120 random co-occurrence edges
  - `hub_heavy`: 120 random co-occurrence edges plus 20 generic hub facts
- Algorithms:
  - `oracle_dependency`
  - `bfs_cooccurrence`
  - `degree_capped_bfs`
  - `weighted_bfs`
  - `attr_like`

Commands:

```bash
.venv/bin/python experiments/synthetic_memory_graph.py \
  --seed 0 \
  --output experiments/results/synthetic_memory_graph_smoke_20260521.json
```

Ten-seed robustness summary:

```bash
.venv/bin/python - <<'PY'
from experiments.synthetic_memory_graph import run_smoke
for seed in range(10):
    run_smoke(seed=seed)
PY
```

Full JSON:

- `experiments/results/synthetic_memory_graph_smoke_20260521.json`
- `experiments/results/synthetic_memory_graph_10seed_20260521.json`

## Single-Seed Result

| Variant | Algorithm | Precision | Recall | FP | FN | Blast radius |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| clean | oracle | 1.000 | 1.000 | 0.00 | 0.00 | 2.00 |
| clean | BFS | 1.000 | 1.000 | 0.00 | 0.00 | 2.00 |
| clean | ATTR-like | 1.000 | 0.500 | 0.00 | 1.00 | 1.00 |
| noisy | oracle | 1.000 | 1.000 | 0.00 | 0.00 | 2.00 |
| noisy | BFS | 0.075 | 1.000 | 25.30 | 0.00 | 27.30 |
| noisy | degree-capped | 0.198 | 0.600 | 5.70 | 0.80 | 6.90 |
| noisy | weighted | 0.100 | 0.050 | 0.60 | 1.90 | 0.70 |
| noisy | ATTR-like | 0.900 | 0.550 | 0.20 | 0.90 | 1.30 |
| hub-heavy | oracle | 1.000 | 1.000 | 0.00 | 0.00 | 1.54 |
| hub-heavy | BFS | 0.033 | 1.000 | 48.77 | 0.00 | 50.31 |
| hub-heavy | degree-capped | 0.108 | 0.654 | 8.00 | 0.69 | 8.85 |
| hub-heavy | weighted | 0.308 | 0.269 | 0.00 | 1.46 | 0.08 |
| hub-heavy | ATTR-like | 0.769 | 0.654 | 0.62 | 0.69 | 1.46 |

## Ten-Seed Averages

| Variant | Algorithm | FP | Blast radius | Precision | Recall |
| --- | --- | ---: | ---: | ---: | ---: |
| clean | BFS | 0.00 | 2.00 | 1.000 | 1.000 |
| clean | degree-capped | 0.00 | 2.00 | 1.000 | 1.000 |
| clean | weighted | 0.00 | 2.00 | 1.000 | 1.000 |
| clean | ATTR-like | 0.00 | 1.00 | 1.000 | 0.500 |
| noisy | BFS | 27.06 | 29.06 | 0.073 | 1.000 |
| noisy | degree-capped | 6.02 | 7.22 | 0.192 | 0.600 |
| noisy | weighted | 0.56 | 0.68 | 0.086 | 0.060 |
| noisy | ATTR-like | 0.21 | 1.32 | 0.910 | 0.555 |
| hub-heavy | BFS | 45.01 | 46.55 | 0.037 | 1.000 |
| hub-heavy | degree-capped | 7.40 | 8.30 | 0.136 | 0.681 |
| hub-heavy | weighted | 0.16 | 0.20 | 0.210 | 0.250 |
| hub-heavy | ATTR-like | 0.68 | 1.56 | 0.721 | 0.669 |

## Interpretation

The mechanism gate passes at smoke scale:

1. In the clean graph, BFS over co-occurrence matches the oracle because
   co-occurrence is aligned with dependency.
2. In noisy and hub-heavy graphs, BFS keeps full recall but produces large
   false-positive propagation and blast radius.
3. Guardrails reduce false positives but expose recall costs. This directly
   quantifies the reviewer concern that dependency-aware propagation may miss
   real dependencies.

This supports the revised thesis: the problem is not that BFS is universally bad;
the problem is using co-occurrence topology as a proxy for dependency when those
relations diverge.

## Paper Use

Use this as the mechanism proof. Do not present it as deployment evidence.

- Synthetic: controlled mechanism and precision/recall tradeoff.
- EventQA: real-data stress test for structural blast radius.
- Artificial hub injection: topology construction stress test.
- LongMemEval: negative transfer diagnostic showing graph-construction
  brittleness.
