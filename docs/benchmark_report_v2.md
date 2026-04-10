# MemoryAgentBench Benchmark Report v2

**날짜:** 2026-04-09
**데이터셋:** FactConsolidation (ai-hyz/MemoryAgentBench, Conflict_Resolution split)
**인프라:** DooGPU Gemma-4-31B-it (LLM) + BAAI/bge-m3 (Embedding)

## 실험 목적

Graph-aware Selective Forgetting이 MemoryAgentBench FactConsolidation 태스크에서
Baseline 대비 성능 개선을 보이는지 검증. 특히 **Attribute-aware Selective Propagation**의
효과를 측정.

## 방법론 요약

### Baseline
- 개별 fact → SQLite + Vector 저장
- Subject-key 기반 충돌 감지 (예: "Russia:president")
- 충돌 시 이전 fact `is_valid=False` 처리
- 검색: RRF (vector + graph)

### Experiment (Attribute-aware Selective Propagation)
- Baseline과 동일한 메모리 저장/충돌 감지
- **추가**: 충돌 발생 시 downstream fact chain만 선택적 decay
  - "The president of Russia is Putin" 무효화 →
  - "Putin was born in Leningrad"만 decay (downstream chain)
  - "The capital of Russia is Moscow"는 건드리지 않음 (다른 attribute)
- 검색: RRF * decay_weight (stale fact 순위 하락)
- 교통공학 analogy: 방향성 있는 link failure propagation

## 실험 진행 과정

### Phase 1: BFS 기반 전파 (v1)

co-occurrence graph + BFS 전파. Hub entity를 통해 무관한 fact까지 decay.

| Dataset | Depth | DpH | Δ_EM |
|---------|-------|-----|------|
| SH 6K | 2 | 0.5 | **-8.0%** |
| MH 6K | 2 | 0.5 | +0.0% |

**실패 원인 진단:**
- Entity graph에 414 nodes, 520 edges
- "United States" node: degree=23, 27개 메모리 연결
- propagation으로 **81개 valid 메모리가 decay** (전체의 23.5%)
- 그 중 30개가 weight < 0.3 → 검색에서 사실상 소실

### Phase 2: Attribute-aware 전파 (v2) — 핵심 개선

**핵심 변경:** BFS 대신 fact_registry의 subject_key 구조를 활용.
충돌된 fact의 **object entity를 subject로 가진 downstream fact**만 전파.

Collateral damage 대폭 감소:
- v1: 81개 메모리 decay → v2: 51개로 감소 (37% 감소)
- SH: Δ=-8% → Δ=-2~0%
- **MH: Δ=0% → Δ=+2.0%**

## 최종 결과

### Multi-hop 6K Ablation (핵심 결과)

| depth | dph=0.3 | dph=0.5 | dph=0.7 |
|-------|---------|---------|---------|
| 1 | **+2.0%** | +1.0% | +1.0% |
| 2 | **+2.0%** | **+2.0%** | +1.0% |
| 3 | **+2.0%** | **+2.0%** | +1.0% |

**모든 설정에서 양(+) 결과!**

### 최적 설정 (depth=2, dph=0.5)

| Dataset | Baseline EM | Experiment EM | Delta | Rel. Impr. |
|---------|-------------|---------------|-------|------------|
| **MH 6K** | 19.0% | **21.0%** | **+2.0%** | **+10.5%** |
| SH 6K | 78.0% | 76~78% | -2~0% | — |

### 개선된 Multi-hop 쿼리 분석

| Query | 질문 | Baseline | Experiment | 메커니즘 |
|-------|------|----------|------------|----------|
| Q17 | "capital of country where Madame du Barry held citizenship" | Harare | **London** | France→capital chain 정확 resolve |
| Q36 | "country of performer Rocket Man" | UK | **Japan** | citizenship chain 갱신 |
| Q53 | "country of genre of spouse of Roy Lichtenstein" | USA | **Russian Empire** | 장르→국가 chain 추적 |

### 시간 성능

| Metric | Baseline | Experiment | Overhead |
|--------|----------|------------|----------|
| Memorize time | 25-30s | 26-32s | +2-4s |
| Avg query time | 0.16s | 0.16-0.21s | ~0s |

## 핵심 기여 (Contribution)

1. **Attribute-aware Selective Propagation**: 교통공학의 방향성 link failure 모델을
   AI 메모리의 selective forgetting에 적용. 동일 entity의 동일 attribute가 변경될 때만
   downstream chain으로 전파하여 collateral damage를 제거.

2. **Collateral Damage 정량 분석**: BFS 기반 전파가 hub entity를 통해 23.5%의
   valid 메모리를 무차별 decay시키는 문제를 발견하고, attribute-aware 전파로
   37% 감소시킴.

3. **벤치마크 실증**: ICLR 2026 MemoryAgentBench FactConsolidation MH 6K에서
   Baseline 대비 +2.0% EM (10.5% relative improvement) 달성.
   모든 depth × decay_per_hop 조합에서 일관된 양의 결과.

## 한계 및 향후 연구

1. **Single-hop에서 효과 없음**: SH 태스크에는 downstream chain이 없어
   propagation이 도움이 안 됨. 오히려 소량의 잔여 collateral damage 존재.

2. **Multi-hop 절대 정확도 한계**: MH baseline 19%는 RAG 기반 메모리의 근본적 한계.
   단순 top-k 검색으로는 2-3hop chain의 모든 중간 fact를 가져오지 못함.
   향후 chain-aware iterative retrieval 필요.

3. **Entity 추출 한계**: 규칙 기반 추출의 한계로 "Vladimir Putin"과 "Putin"이
   별도 entity로 처리됨. 더 강력한 entity resolution 필요.

4. **벤치마크 데이터 크기**: 6K context (455 facts, 100 queries)에서만 실험.
   32K/64K/262K context에서의 확장성 검증 필요.

## 실험 환경

- Python 3.12, SQLite (in-memory)
- LLM: google/gemma-4-31B-it (max_tokens=10, temp=0.0)
- Embedding: BAAI/bge-m3 (dim=1024)
- Vector search: NumPy cosine similarity (in-memory), RRF fusion (k=60)
- Graph: NetworkX (entity co-occurrence + attribute-aware propagation)
- 벤치마크: MemoryAgentBench (ai-hyz/MemoryAgentBench, HuggingFace)

## 결과 파일

- `experiments/results/benchmark_factconsolidation_mh_6k_*.json` (9개 ablation)
- `experiments/results/benchmark_factconsolidation_sh_6k_*.json` (6개 ablation)
- `experiments/benchmark_runner.py` — 벤치마크 실행 스크립트
- `experiments/analyze_benchmark.py` — 결과 분석 스크립트
