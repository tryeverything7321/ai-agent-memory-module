# Workshop Paper Tables

Generated from experiments/analyze_all.py

## Table 1: Collateral Damage Scale Trend

| Scale | Valid Mem | BFS Decay (%) | Attr Decay (%) | Reduction (%) | BFS Kill (<0.1) | Max Hub Degree |
|-------|----------|---------------|----------------|---------------|-----------------|----------------|
| 6K | 344 | 237 (68.9%) | 51 (14.8%) | 78.5% | 143 | 23 (United States) |
| 32K | 1,744 | 1,377 (79.0%) | 275 (15.8%) | 80.0% | 1,179 | 121 (United States) |
| 64K | 3,414 | 2,680 (78.5%) | 513 (15.0%) | 80.9% | 2,465 | 298 (America) |

**Key observation**: Hub entity degree grows superlinearly (23→121→298, ~13x from 6K→64K) while BFS damage ratio plateaus at ~78-79%. The absolute number of destroyed memories (weight<0.1) scales linearly: 143→1,179→2,465.

## Table 2: Adversarial Hub Exploitation

### 6K Context (344 valid memories)

| Attack Facts | BFS Damage (%) | BFS Kill (%) | Attr Damage (%) | BFS EM Drop |
|-------------|----------------|--------------|-----------------|-------------|
| 1 | 5.2% | 0.3% | 0.0% | +0.0pp |
| 3 | 26.7% | 4.4% | 0.0% | +10.0pp |
| 5 | 39.8% | 17.4% | 0.3% | +10.0pp |

### 32K Context (1,744 valid memories)

| Attack Facts | BFS Damage (%) | BFS Kill (%) | Attr Damage (%) | BFS EM Drop |
|-------------|----------------|--------------|-----------------|-------------|
| 1 | 38.1% | 1.0% | 0.0% | +0.0pp |
| 3 | 46.0% | 8.8% | 1.0% | +0.0pp |
| 5 | 57.3% | 19.3% | 1.0% | +0.0pp |

### Scale Effect (same 5-fact attack)

| Context | BFS Damage | BFS Kill | Attr Damage | Scale Amplification |
|---------|-----------|----------|-------------|---------------------|
| 6K | 39.8% | 17.4% | 0.3% | baseline |
| 32K | 57.3% | 19.3% | 1.0% | +17.5pp (1.4x) |

## Table 3: Defense Effectiveness Across All Experiments

| Experiment | BFS Damage | Attr Damage | Defense Rate |
|------------|------------|-------------|--------------|
| CD 6K | 68.9% | 14.8% | 78.5% |
| CD 32K | 79.0% | 15.8% | 80.0% |
| CD 64K | 78.5% | 15.0% | 80.9% |
| Adv 6K / 1f | 5.2% | 0.0% | 100.0% |
| Adv 6K / 3f | 26.7% | 0.0% | 100.0% |
| Adv 6K / 5f | 39.8% | 0.3% | 99.3% |
| Adv 32K / 1f | 38.1% | 0.0% | 100.0% |
| Adv 32K / 3f | 46.0% | 1.0% | 97.8% |
| Adv 32K / 5f | 57.3% | 1.0% | 98.2% |

## Table 4: Cross-task Impact (C2) — Accurate_Retrieval (eventqa_65536)

BFS propagation의 collateral damage가 conflict resolution뿐 아니라 retrieval accuracy에도 부정적 영향.

| ARM | EM | SubEM | F1 | Collateral Damage | Memories Affected |
|-----|-----|-------|-----|-------------------|-------------------|
| Baseline (no propagation) | 15.0% | 15.0% | 67.1% | 0 | 0 |
| Post-BFS | 10.0% | 10.0% | 48.9% | 32 | 3,381 |
| Post-Attribute-aware | 15.0% | 15.0% | 67.1% | 1 | 0 |

| Metric | Baseline → BFS | Baseline → Attr | BFS → Attr (recovery) |
|--------|---------------|-----------------|----------------------|
| EM | **-5.0pp** | +0.0pp | **+5.0pp** |
| F1 | **-18.2pp** | +0.0pp | **+18.2pp** |

**Key finding**: A single BFS propagation from a hub entity (degree=715) affects 3,381 memories, degrades 32 retrievable memories below threshold, and drops F1 by 18.2pp. Attribute-aware propagation preserves full retrieval accuracy.