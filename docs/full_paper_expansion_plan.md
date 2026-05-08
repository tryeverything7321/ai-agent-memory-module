# Full Paper 확장 계획

**작성일**: 2026-04-23
**기반**: ICML SCALE Workshop 제출본 (workshop_rev.tex) + 외부 리뷰 분석
**타겟 venue**: EMNLP 2025 / NeurIPS 2026 / AAAI 2027 (agent systems / safety track)
**현재 상태**: 워크샵 7페이지 → 목표 9-10페이지 (본문)

---

## 현재 워크샵 논문의 약점 (리뷰어 저항 예상)

| 약점 | 심각도 | 워크샵 방어 | Full paper에서 필요한 것 |
|------|--------|-----------|----------------------|
| BFS 단일 baseline (straw man 비판) | **높음** | stress-test 프레이밍 3곳 | 6+ propagation baseline 비교 |
| Single benchmark (MemoryAgentBench) | **높음** | Zipf 논증 + Limitation (1) | 2nd benchmark 실험 |
| Gold dependency label 없음 | **중간** | heuristic proxy 인정 | human-annotated subset |
| Scale-free → damage 인과관계 미증명 | **중간** | 상관관계만 제시 | synthetic graph control 실험 |
| Defense ablation 없음 | **중간** | scope 밖 처리 | subject/attribute/direction 각각 ablation |
| Single LLM (Gemma-4-31B-it) | **낮음** | rule-based extraction 강조 | 2nd LLM (GPT-4o 등) |

---

## Phase 1: Baseline 확대 (최우선)

### 목표
BFS vs Attr-Aware 이분법 → **6-8개 propagation strategy 비교**

### 추가할 baseline

| Baseline | 설명 | 구현 난이도 |
|----------|------|-----------|
| No-Propagation | 이미 있음 (Table 2) | ✅ 완료 |
| BFS (depth=2) | 이미 있음 | ✅ 완료 |
| Degree-capped BFS (cap=5) | 이미 있음 (Table 6) | ✅ 완료 |
| **Weighted BFS** | edge weight = co-occurrence count, threshold로 전파 제한 | 낮음 |
| **k-hop with decay threshold** | decay 후 weight < θ면 전파 중단 | 낮음 |
| **PPR (Personalized PageRank)** | invalidated fact에서 PPR score 기반 전파 | 중간 |
| **Relation-type constrained** | edge type (if available) 기반 필터링 | 중간 |
| Attr-Aware | 이미 있음 | ✅ 완료 |

### 예상 결과 테이블 구조

```
| Strategy              | Dam.  | Kill  | Stale | F1 (cross) | Latency |
|-----------------------|-------|-------|-------|------------|---------|
| No-Propagation        | 0%    | 0%    | 16%   | baseline   | 0ms     |
| BFS                   | 69-79%| ...   | 0%    | -10.1pp    | <10ms   |
| Weighted BFS (θ=0.3)  | ?     | ?     | ?     | ?          | <10ms   |
| k-hop threshold (θ=0.5)| ?   | ?     | ?     | ?          | <10ms   |
| Degree-capped (cap=5) | 24.1% | 8.1% | ?     | ?          | <10ms   |
| PPR (α=0.15)          | ?     | ?     | ?     | ?          | ~50ms   |
| Attr-Aware            | 0.3%  | 0%    | 8%    | +0.0pp     | <10ms   |
```

### 기대 효과
- "BFS만 때렸다" 비판 완전 해소
- Attr-Aware가 전체 spectrum에서 Pareto optimal임을 입증

---

## Phase 2: Synthetic Graph Control (구조적 인과 증명)

### 목표
"scale-free topology가 damage의 원인이다"를 correlation이 아닌 **causation**으로 증명

### 실험 설계

동일한 fact 수 (예: 6K turns → ~350 facts)에서 3가지 graph topology 생성:

| Topology | 생성 방법 | 기대 결과 |
|----------|----------|----------|
| **Erdős–Rényi** (ER) | 동일 edge 수, random 연결 | 균일 degree → damage 분산, 낮은 총 damage |
| **Small-world** (WS) | Watts-Strogatz 모델 | 중간 정도 hub → 중간 damage |
| **Scale-free** (BA) | Barabási-Albert 모델 | 큰 hub → 높은 damage (실제 데이터와 유사) |

### 핵심 비교 변수
- 동일 node 수, 동일 edge 수, 다른 degree distribution
- BFS damage, kill rate, hub_max degree
- κ (degree heterogeneity) vs damage correlation

### 기대 결과
- damage ∝ κ (degree heterogeneity) 관계 확인
- ER에서는 damage가 낮고 scale-free에서만 심각 → topology가 causal factor

---

## Phase 3: 2nd Benchmark

### 후보

| Benchmark | 장점 | 단점 |
|-----------|------|------|
| **MemoryArena** (2026) | multi-session interdependent tasks, 40-60% 성능 저하 보고 | 구조가 다를 수 있음 |
| **LongMemEval** (2024) | 115K+ 토큰, 장기 대화 메모리 | fact graph 구축 방법 다를 수 있음 |
| **Custom synthetic** | 완전 통제 가능 | ecological validity 약함 |

### 권장: MemoryArena
- session-interdependent tasks → cross-task contamination 재현 적합
- 이미 references.bib에 있음 (`memoryarena_2026`)

---

## Phase 4: Defense Ablation

### Attr-Aware 구성 요소 분해

| Component | 설명 | Ablation 방법 |
|-----------|------|--------------|
| **Subject-key directionality** | object→subject 방향만 전파 | 방향 제거 (bidirectional) |
| **Attribute matching** | 동일 attribute type만 전파 | attribute 필터 제거 |
| **In-degree dampening** | hub의 decay를 약화 | dampening 제거 (uniform decay) |
| **Depth limit** | depth=2 제한 | depth=1, 3, 4 비교 |

### 예상 결과 테이블

```
| Variant                    | Dam.  | Kill  | Forgetting Acc. |
|----------------------------|-------|-------|-----------------|
| Full Attr-Aware            | 0.3%  | 0%    | 94%             |
| - directionality           | ?     | ?     | ?               |
| - attribute filter         | ?     | ?     | ?               |
| - in-degree dampening      | ?     | ?     | ?               |
| - depth limit (depth=∞)   | ?     | ?     | ?               |
```

---

## Phase 5: Gold Dependency Labels

### 목표
Attr-Aware가 "맞는 전파를 한다"를 검증 (precision/recall of propagation targets)

### 방법
1. 10개 fact-change 시나리오에서 **사람이 annotation** (이미 controlled scenario 존재)
   - 각 시나리오의 20개 메모리에 대해 "이 메모리는 변경된 사실에 실제로 의존하는가?" 라벨링
   - 총 200개 (fact, memory) pair → binary label (dependent / independent)
2. BFS, Attr-Aware, 기타 baseline의 propagation target과 gold label 비교
3. Precision, Recall, F1 보고

### 기대 효과
- "단순히 전파를 안 해서 damage가 줄어든 착시" 비판 완전 해소
- Attr-Aware의 precision이 높음을 입증

---

## Phase 6: 추가 보강 (낮은 우선순위)

| 항목 | 내용 |
|------|------|
| 2nd LLM | GPT-4o-mini 또는 Llama-3.1-70B로 entity extraction 재현 |
| Pareto frontier 시각화 | forgetting accuracy vs collateral damage scatter plot |
| Real system validation | Mem0 graph-enabled mode에서 실제 propagation 구현 테스트 |
| Attack sophistication | black-box에서 frequency-based entity targeting (Zipf 활용) |

---

## 실행 순서 및 의존성

```
Phase 1 (Baseline 확대)     ████████░░  2주   ← 가장 높은 ROI
     │
Phase 4 (Defense Ablation)  ██████░░░░  1주   ← Phase 1과 병렬 가능
     │
Phase 2 (Synthetic Graph)   ████████░░  2주   ← Phase 1 완료 후
     │
Phase 5 (Gold Labels)       ██████░░░░  1주   ← 사람 annotation 필요
     │
Phase 3 (2nd Benchmark)     ██████████  2-3주 ← 가장 오래 걸림
     │
Phase 6 (추가 보강)          ████░░░░░░  1주   ← 선택적
────────────────────────────────────────────────
총 예상: 6-8주 (병렬 수행 시)
```

---

## 리뷰어 예상 질문 & 준비된 답변

### Q1. "누가 BFS를 실제로 쓰나? Straw man 아닌가?"
**A**: BFS는 association-graph propagation family의 가장 자연스러운 instantiation이다. Full paper에서는 weighted BFS, PPR, k-hop threshold 등 6개 전략을 비교하여, co-occurrence 기반 전파 전체가 구조적으로 위험함을 보인다. Attr-Aware만이 Pareto optimal.

### Q2. "MemoryAgentBench에 특화된 현상 아닌가?"
**A**: (Phase 2) synthetic graph에서 topology만으로 damage가 결정됨을 보이고, (Phase 3) MemoryArena에서 재현하여 benchmark 독립성 확인.

### Q3. "Attr-Aware가 진짜 올바른 전파를 하나?"
**A**: (Phase 5) 200개 human-annotated dependency label 대비 Attr-Aware의 propagation precision/recall 보고. 단순 recall 감소가 아닌 정확한 타겟팅 확인.

### Q4. "방어가 전파를 안 해서 damage가 줄어든 착시 아닌가?"
**A**: Table 2에서 forgetting accuracy 94% (BFS 96% 대비 2pp 차이). (Phase 4) ablation으로 각 component의 기여 분리. (Phase 5) gold label로 precision 확인.

### Q5. "Scale-free가 정말 원인인가?"
**A**: (Phase 2) 동일 fact/edge 수에서 ER, small-world, scale-free 비교. κ (degree heterogeneity)와 damage의 인과 관계 확인. ER에서는 damage 경미.

---

## 워크샵 → Full paper 전환 시 구조 변경

| Workshop (현재) | Full paper |
|----------------|-----------|
| 7페이지 | 9-10페이지 (본문) |
| BFS + Attr-Aware | 6-8 propagation strategies |
| 1 benchmark | 2 benchmarks + synthetic |
| 방어 결과만 | Defense ablation |
| Limitation에서 인정 | 실험으로 해소 |
| 교통공학 = 2 paragraph | 교통공학 = 1 paragraph (축소, novelty 본체로 안 세움) |

---

*이 계획은 워크샵 수락 후 실행. 워크샵 리뷰 피드백에 따라 우선순위 조정.*
