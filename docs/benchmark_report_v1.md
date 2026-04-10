# MemoryAgentBench Benchmark Report v1

**날짜:** 2026-04-09
**데이터셋:** FactConsolidation (ai-hyz/MemoryAgentBench, Conflict_Resolution split)
**인프라:** DooGPU Gemma-4-31B-it (LLM) + BAAI/bge-m3 (Embedding)

## 실험 목적

Graph-aware Selective Forgetting이 MemoryAgentBench FactConsolidation 태스크에서
Baseline(단순 메모리 저장/검색) 대비 성능 개선을 보이는지 검증.

## 실험 설계

| 구성 | Baseline | Experiment |
|------|----------|------------|
| 메모리 저장 | 개별 fact → SQLite + Vector | 동일 |
| 충돌 감지 | Subject key 기반 | 동일 |
| 이전 fact 무효화 | is_valid=False | 동일 |
| **Graph Propagation** | **OFF** | **ON** |
| Semantic Filter | N/A | ON |
| 검색 | RRF (vector + graph) | RRF * decay_weight |

## 결과 요약

### Full Benchmark (100 queries each)

| Dataset | Depth | decay_per_hop | B_EM | E_EM | Delta_EM | B_F1 | E_F1 | Delta_F1 |
|---------|-------|---------------|------|------|----------|------|------|----------|
| SH 6K | 0 | 0.5 | 78.0% | 78.0% | **+0.0%** | 78.4% | 78.4% | +0.0% |
| SH 6K | 2 | 0.9 | 78.0% | 74.0% | **-4.0%** | 78.4% | 74.0% | -4.4% |
| SH 6K | 2 | 0.5 | 78.0% | 70.0% | **-8.0%** | 78.4% | 70.0% | -8.4% |
| MH 6K | 2 | 0.5 | 19.0% | 19.0% | **+0.0%** | 19.3% | 19.0% | -0.3% |

### Key Metrics

- **Baseline SH**: EM=78%, F1=78.4% (strong baseline)
- **Baseline MH**: EM=19%, F1=19.3% (multi-hop RAG의 근본적 한계)
- **Memorize time**: ~25-35초 per context (2 chunks, ~400 facts)
- **Query time**: ~0.16초 per query

## 분석

### 1. Propagation depth=0 (충돌 감지만)

충돌 감지 + 무효화만 작동시키면 Baseline과 동일한 성능.
이는 subject-key 기반 충돌 감지가 정확하게 동작하고 있으며,
무효화된 fact의 is_valid=False 필터링이 검색에서 올바르게 적용됨을 증명.

### 2. Propagation의 Collateral Damage

Graph propagation을 켜면 **이웃 메모리까지 decay**되면서 valid fact의 검색 순위가 하락.

- SH에서 악화된 12개 쿼리 중 10개가 `→ "Unknown"` 패턴
- Entity co-occurrence graph가 **너무 dense** — 무관한 fact들이 graph 상에서 연결됨
- 예: "France" 관련 fact가 "Russia" 관련 fact와 co-occurrence edge로 연결되어 collateral decay 발생

### 3. Multi-hop에서 중립적 결과

MH에서 EM=19% (Baseline) = 19% (Experiment) — 이건 다른 이유:
- Multi-hop 정답률 자체가 너무 낮음 (80% 쿼리에서 F1=0)
- 검색이 2-3hop chain의 모든 중간 fact를 가져오지 못함
- Propagation이 영향을 줄 수 있는 쿼리가 극소수

### 4. 교통공학 관점의 해석

교통 네트워크에서 link failure propagation은 **대체 경로 밀도**에 의존.
현재 entity graph는 co-occurrence 기반이라 edge density가 높아서,
하나의 invalidation이 너무 넓은 범위로 전파됨.

해결 방향:
- **Edge 가중치 도입**: co-occurrence 빈도 기반 edge weight
- **Semantic similarity threshold**: entity 간 실제 관련성이 높은 경우만 edge 생성
- **Direction-aware propagation**: 인과 방향성을 고려한 단방향 전파

## 개선 방향

1. **Graph sparsification**: co-occurrence edge에 threshold 적용 (현재 모든 co-occurrence가 edge)
2. **Relation-type aware propagation**: "is" 관계만 전파, "co_occurs"는 전파 제외
3. **Adaptive decay_per_hop**: entity 유형별 다른 감쇄율 적용
4. **Multi-hop retrieval 개선**: 단순 top-k 대신 chain reasoning aware retrieval

## 실험 환경

- Python 3.12, SQLite (in-memory)
- LLM: google/gemma-4-31B-it (max_tokens=10, temp=0.0)
- Embedding: BAAI/bge-m3 (dim=1024)
- Vector search: FAISS (in-memory), RRF fusion (k=60)
- Graph: NetworkX (entity co-occurrence graph)

## 결과 파일

- `experiments/results/benchmark_factconsolidation_sh_6k_*.json`
- `experiments/results/benchmark_factconsolidation_mh_6k_*.json`
