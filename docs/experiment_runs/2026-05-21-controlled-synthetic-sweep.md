# Controlled Synthetic Memory Graph Sweep

Date: 2026-05-21

Branch: `research/20260520-preprint-followup`

## Question

Does BFS false-positive invalidation increase systematically as co-occurrence
noise and generic hub strength increase?

## Setup

- Entity counts: 30, 100, 300
- Chain length: 5
- Dependency chains: `n_entities / 3`
- Noise multipliers: 0, 1, 3 times base fact count
- Hub multipliers: 0, 0.5, 2 times number of chains
- Seeds: 20
- Total worlds: 540
- Depth: 2

Command:

```bash
.venv/bin/python experiments/synthetic_memory_graph.py \
  --sweep \
  --sizes 30 100 300 \
  --noise_multipliers 0 1 3 \
  --hub_multipliers 0 0.5 2 \
  --seeds 20 \
  --output experiments/results/synthetic_memory_graph_sweep_20260521.json
```

## Key Results

| Entities | Noise x | Hub x | BFS FP | BFS blast | ATTR FP | ATTR recall | Degree-cap FP | Weighted recall |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30 | 0 | 0 | 0.00 | 2.00 | 0.00 | 0.500 | 0.00 | 1.000 |
| 30 | 1 | 0 | 9.82 | 11.82 | 0.13 | 0.518 | 4.92 | 0.545 |
| 30 | 3 | 0 | 33.09 | 35.09 | 0.30 | 0.550 | 6.53 | 0.025 |
| 30 | 3 | 2 | 49.69 | 51.23 | 0.82 | 0.662 | 8.30 | 0.238 |
| 100 | 0 | 0 | 0.00 | 2.00 | 0.00 | 0.500 | 0.00 | 1.000 |
| 100 | 1 | 0 | 11.06 | 13.06 | 0.02 | 0.504 | 5.63 | 0.570 |
| 100 | 3 | 0 | 49.65 | 51.65 | 0.08 | 0.512 | 6.84 | 0.033 |
| 100 | 3 | 2 | 70.66 | 72.49 | 0.28 | 0.551 | 7.50 | 0.103 |
| 300 | 0 | 0 | 0.00 | 2.00 | 0.00 | 0.500 | 0.00 | 1.000 |
| 300 | 1 | 0 | 11.03 | 13.03 | 0.01 | 0.502 | 5.30 | 0.581 |
| 300 | 3 | 0 | 54.29 | 56.29 | 0.03 | 0.505 | 6.65 | 0.031 |
| 300 | 3 | 2 | 76.64 | 78.58 | 0.10 | 0.517 | 7.00 | 0.047 |

Full grid:

- `experiments/results/synthetic_memory_graph_sweep_20260521.json`

## Interpretation

The sweep supports the controlled mechanism:

1. When co-occurrence aligns with dependency (`noise=0`, `hub=0`), BFS matches
   dependency propagation: false positives are zero and blast radius is exactly
   the dependency closure size.
2. Random co-occurrence noise increases BFS false-positive invalidation across
   all graph sizes.
3. Generic hub facts further increase false-positive invalidation, especially
   under noisy co-occurrence.
4. ATTR-like filtering keeps false positives near zero, but only with recall
   around 0.5-0.66 in this controlled setup. This quantifies the
   under-propagation tradeoff.
5. Degree-capped BFS reduces false positives but still leaves several collateral
   invalidations per trigger. Weighted BFS can suppress false positives, but its
   recall collapses in high-noise settings.

## Paper Use

Use this as the main mechanism table. It gives the paper a stable backbone:

> The failure is not that BFS is inherently bad. BFS is correct when
> co-occurrence is dependency-aligned, but becomes a high-false-positive
> maintenance operation when co-occurrence topology diverges from dependency.

EventQA and structured LongMemEval should then be framed as real-data stress
tests showing that this divergence appears in benchmark-derived memory graphs.
