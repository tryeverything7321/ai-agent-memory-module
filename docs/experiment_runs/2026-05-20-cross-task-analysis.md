# 2026-05-20 Cross-Task Analysis

## Claim Update

The artifact-aware named-hub experiment strengthens the structural collateral
damage claim but narrows the retrieval degradation claim.

## Main Numbers

| Arm | F1 | Avg collateral |
|---|---:|---:|
| Baseline | 54.4 | 0.0 |
| BFS | 51.6 | 41.5 |
| ATTR-AWARE | 53.6 | 1.2 |

## Interpretation

BFS produces large collateral structural changes across all five samples.
Retrieval F1 drops in four samples and improves in one sample. The paper should
therefore present retrieval degradation as a practical risk observed in most
sampled settings, not as a deterministic consequence of BFS propagation.

## Revised Paper Claim

> Unfiltered propagation over named-entity hubs consistently expands the
> structural blast radius. Downstream retrieval degradation appears in most
> sampled settings, while ATTR-AWARE sharply reduces collateral damage and keeps
> aggregate retrieval close to baseline.
