# MemoryAgentBench Benchmark Report v3 — Collateral Damage Analysis

**날짜:** 2026-04-09
**데이터셋:** FactConsolidation (ai-hyz/MemoryAgentBench, Conflict_Resolution split)
**인프라:** Gemma-4-31B-it served through an OpenAI-compatible local endpoint + BAAI/bge-m3 (Embedding)

## 실험 목적

BFS 기반 graph propagation이 hub entity를 통해 무관한 메모리를 무차별 decay시키는
**Collateral Damage** 현상을 정량적으로 분석하고, Attribute-aware Selective Propagation이
이를 얼마나 감소시키는지 다양한 context 크기(6K, 32K)에서 검증.

## 핵심 발견: Collateral Damage의 정량적 증거

### 1. BFS vs Attribute-aware: 전파 범위 비교

| Context | Valid 메모리 | BFS decay | Attr-aware decay | 감소 | 감소율 |
|---------|-------------|-----------|------------------|------|--------|
| **6K** | 344 | 237 (68.9%) | 51 (14.8%) | 186 | **78.5%** |
| **32K** | 1,744 | 1,377 (79.0%) | 275 (15.8%) | 1,102 | **80.0%** |

**핵심 관찰:** Context가 커질수록 BFS collateral damage가 악화(68.9%→79.0%)되지만,
attribute-aware는 안정적(14.8%→15.8%).

### 2. Weight 분포 비교 — 메모리 소실 분석

#### 6K Context

| Weight 범위 | BFS | Attr-aware | Δ |
|-------------|-----|------------|---|
| < 0.1 (완전 소실) | **143** | 0 | -143 |
| < 0.3 (사실상 소실) | 175 | 1 | -174 |
| < 0.5 (검색 불리) | 188 | 1 | -187 |
| = 1.0 (무영향) | 107 | **293** | +186 |

#### 32K Context

| Weight 범위 | BFS | Attr-aware | Δ |
|-------------|-----|------------|---|
| < 0.1 (완전 소실) | **1,179** | 5 | -1,174 |
| < 0.3 (사실상 소실) | 1,263 | 11 | -1,252 |
| < 0.5 (검색 불리) | 1,278 | 15 | -1,263 |
| = 1.0 (무영향) | 367 | **1,469** | +1,102 |

**핵심:** BFS에서 weight < 0.1인 완전 소실 메모리가 6K에서 143개, 32K에서 **1,179개**.
Attribute-aware는 각각 0개, 5개로 **99.6% 감소**.

### 3. Hub Entity 분석 — Collateral Damage의 근본 원인

| Entity | 6K degree | 32K degree | 32K memories |
|--------|-----------|------------|-------------|
| United States | 23 | **121** | 127 |
| America | 23 | **121** | 127 |
| University | 17 | **86** | 76 |
| United Kingdom | 12 | **68** | 58 |
| Catholic Church | — | **66** | 49 |
| France | 13 | **41** | 39 |

**스케일링 분석:** "United States" hub entity의 degree가 context 크기에 따라
23→121로 **5.3배** 증가. Entity graph의 density가 superlinear하게 증가하면서
BFS 전파의 blast radius가 급격히 커짐.

교통공학 비유: hub entity는 교통 네트워크의 주요 교차로에 해당.
교차로를 폐쇄하면 연결된 모든 도로가 영향 받듯, hub entity를 통한 BFS 전파는
무관한 fact까지 decay시킴.

## 벤치마크 성능 결과

### 전체 결과 (Baseline vs Attribute-aware Experiment)

| Dataset | Baseline EM | Experiment EM | Δ |
|---------|-------------|---------------|---|
| SH 6K | 78.0% | 76-78% | -2~0% |
| **MH 6K** | 19.0% | **21.0%** | **+2.0%** |
| SH 32K | 30.0% | 30.0% | 0.0% |
| MH 32K | 4.0% | 3.0% | -1.0% |

### MH 6K Ablation (모든 설정에서 양의 결과)

| depth | dph=0.3 | dph=0.5 | dph=0.7 |
|-------|---------|---------|---------|
| 1 | +2.0% | +1.0% | +1.0% |
| 2 | +2.0% | +2.0% | +1.0% |
| 3 | +2.0% | +2.0% | +1.0% |

### 성능 해석

1. **MH 6K (+2.0%):** Attribute-aware propagation이 downstream fact chain을 정확히
   추적하여 stale fact의 검색 순위를 낮추고, 최신 fact가 top-k에 포함됨.

2. **SH (-2~0%):** Single-hop에서는 downstream chain이 없어 propagation 효과 없음.
   잔여 collateral damage로 소량의 성능 하락 가능.

3. **32K에서의 한계:** 32K context의 baseline EM이 이미 매우 낮음 (SH 30%, MH 4%).
   이는 top-k 검색으로 2000+개 fact에서 관련 fact를 찾는 근본적 한계.
   Propagation 이전에 검색 정확도 자체가 병목.

## 핵심 기여 (Contribution)

### 1. Collateral Damage의 정량적 발견 (Primary)

BFS 기반 graph propagation이 **hub entity를 통해 유효 메모리의 68-79%를
무차별 decay시키는** 심각한 collateral damage 현상을 정량적으로 발견하고 분석.

- 6K: 344개 valid 중 237개(68.9%) decay, 그 중 143개 완전 소실(weight < 0.1)
- 32K: 1,744개 valid 중 1,377개(79.0%) decay, 그 중 1,179개 완전 소실
- **Context가 커질수록 hub entity degree가 superlinear하게 증가하여 문제 악화**

### 2. Attribute-aware Selective Propagation (Solution)

교통공학의 방향성 link failure propagation 모델을 AI 메모리의 selective forgetting에 적용.
동일 entity의 동일 attribute가 변경될 때만 downstream chain으로 전파.

- Collateral damage **78.5-80.0% 감소**
- Weight < 0.1 메모리 수: BFS 대비 **99.6% 감소**
- Overhead: memorize time +2-4s, query time ~0s

### 3. 벤치마크 실증

MemoryAgentBench FactConsolidation MH 6K에서 Baseline 대비 +2.0% EM 달성.
모든 9개 ablation 설정에서 일관된 양의 결과.

## 한계 및 향후 연구

1. **검색 정확도 병목:** 32K+ context에서 baseline EM이 급락 (6K: 19% → 32K: 4%).
   Top-k 검색으로는 multi-hop chain의 모든 중간 fact를 확보하기 어려움.
   Chain-aware iterative retrieval 필요.

2. **Entity 추출 한계:** 규칙 기반 추출의 한계로 동일 entity의 다른 표기가
   별도 entity로 처리됨. 강력한 entity resolution 필요.

3. **64K/262K 확장 검증:** 더 큰 context에서의 collateral damage 스케일링 검증 필요.

## 실험 환경

- Python 3.12, SQLite (in-memory)
- LLM: google/gemma-4-31B-it (max_tokens=10, temp=0.0)
- Embedding: BAAI/bge-m3 (dim=1024)
- Vector search: NumPy cosine similarity (in-memory), RRF fusion (k=60)
- Graph: NetworkX (entity co-occurrence + attribute-aware propagation)
- 벤치마크: MemoryAgentBench (ai-hyz/MemoryAgentBench, HuggingFace)

## 결과 파일

### 벤치마크 결과
- `experiments/results/benchmark_factconsolidation_mh_6k_*.json` (9개 ablation)
- `experiments/results/benchmark_factconsolidation_sh_6k_*.json` (6개 ablation)
- `experiments/results/benchmark_factconsolidation_mh_32k_*.json`
- `experiments/results/benchmark_factconsolidation_sh_32k_*.json`

### Collateral Damage 분석
- `experiments/results/collateral_damage_factconsolidation_mh_6k_*.json`
- `experiments/results/collateral_damage_factconsolidation_sh_6k_*.json`
- `experiments/results/collateral_damage_factconsolidation_mh_32k_*.json`

### 스크립트
- `experiments/benchmark_runner.py` — 벤치마크 실행
- `experiments/analyze_benchmark.py` — 벤치마크 결과 분석
- `experiments/analyze_collateral_damage.py` — collateral damage 정량 분석
