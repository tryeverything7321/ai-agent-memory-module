# Adversarial Review Report — 2026-04-16
**논문**: "Collateral Damage in Graph-based Memory Forgetting"
**리뷰어**: Technical Reviewer, Logic Reviewer, Research Analyst, Writing Reviewer (4-agent parallel)
**목적**: NeurIPS/ICML 수준 adversarial review로 약점 사전 식별

---

## 심각도 요약

| 등급 | 개수 | 비고 |
|------|------|------|
| Critical | 8 | 논문 reject 사유 가능 |
| Major | 22+ | 상당한 수정 필요 |
| Minor | 16+ | 주로 문체/표기 |

---

## CRITICAL 이슈

### C1. Forgetting Accuracy 미측정 (논리+기술 리뷰어 동시 지적)

BFS propagation의 **피해(collateral damage)**만 측정하고, **이득(forgetting accuracy improvement)**을 측정하지 않음.
- "Propagation 없음" Baseline의 forgetting accuracy가 보고되지 않음
- Attr-Aware가 no-propagation보다 **왜** 나은지 증거 없음
- 최악의 경우 결론이 "propagation 하지 마라"로 축약됨

**리뷰어 예상 공격**: "약의 부작용만 보고하고 효능은 보고하지 않았다."

**대응 방안**: MemoryAgentBench의 forgetting accuracy metric으로 Baseline / BFS / Attr-Aware 3자 비교 실험 추가

---

### C2. Straw Man 논증 (논리+문헌 리뷰어 동시 지적)

아무도 구현하지 않은 naive BFS propagation을 직접 만들고, 직접 공격하고, 직접 방어법을 제시하는 자기참조적 구조.
- "Crash testing" 비유로 방어하지만, crash test는 **실제 배포될 차량**을 테스트
- 실제 시스템이 propagation을 구현한다면 naive BFS가 아닌 더 정교한 방식을 선택할 가능성 높음
- "architecturally inevitable"이라는 주장이 **검증 불가능한 예측**에 의존

**리뷰어 예상 공격**: "BFS가 naive하다는 건 자명하다. 아무도 구현 안 한 이유가 바로 이것이다."

**대응 방안**:
1. "inevitable" → "architecturally natural" 또는 "increasingly plausible"로 완화
2. 실제 시스템이 propagation을 구현하려 한 증거 또는 사용자 요청 사례 제시
3. Contribution 프레이밍을 "novel attack/first demonstration" → "systematic risk quantification" 으로 전환

---

### C3. Kumiho (arXiv:2603.17244) 미인용 (문헌 리뷰어)

2026년 3월 출판. AGM belief revision 프레임워크를 graph-native memory에 적용:
- "어떤 fact를 수정하면 어떤 downstream fact가 영향받는지" 형식적으로 다룸
- Hansson의 "Relevance" 공리 = "수정 시 관련 없는 belief는 보존" → Attr-Aware와 목적 동일
- Typed dependency edges + versioned revision semantics 제공

**리뷰어 예상 공격**: "Attr-Aware는 belief revision의 재발명이다."

**대응 방안**:
1. Related Work에 Kumiho 인용 + 명시적 차별화
2. 차별점 강조: Kumiho = 형식적 보장(이론), 본 논문 = empirical 취약점 분석 + 공격 시나리오
3. 상호 보완적 관계로 포지셔닝

---

### C4. 단일 벤치마크 / 단일 LLM / 단일 Graph Construction (기술+논리 리뷰어)

- MemoryAgentBench 1개
- Gemma-4-31B-it 1개
- Rule-based entity extraction 1개
- Propagation parameter: depth=2, decay=0.5 고정

"구조적(structural) 문제"라는 주장에 비해 증거 범위가 극히 제한적.

**대응 방안**:
1. 최소 1개 추가 벤치마크 (MemoryArena 또는 LongMemEval)
2. LLM 2종 비교 (예: Gemma + Llama)
3. depth/decay sensitivity analysis를 본문으로 승격

---

### C5. Scale-free 주장의 자기모순 (기술+논리 리뷰어)

- 64K에서 KS test가 power-law를 **기각** ($p=0.009$)
- Log-normal과 **구분 불가** ($p>0.1$)
- 그러면서 "consistent with scale-free"라고 주장

**대응 방안**: "scale-free" → "heavy-tailed"로 통일. Percolation theory 논증은 heavy-tail 조건으로 재구성

---

### C6. MaRS (arXiv:2512.12856) 미인용 (문헌 리뷰어)

6가지 forgetting policy 프레임워크. forgetting 관련 선행연구를 과소 대표.

**대응 방안**: Related Work의 forgetting 섹션에 MaRS, "Forgetful but Faithful" 추가

---

### C7. Belief Revision 문헌(AGM) 회피 (문헌 리뷰어)

"Causal dependency"는 belief revision에서 수십 년간 다뤄진 개념. 교통공학만 인용하고 AGM 프레임워크를 무시한 것은 novelty 과장 효과.

**대응 방안**: Background 또는 Related Work에 AGM 프레임워크 + Kumiho 논의 추가

---

### C8. Algorithm 1 vs 실제 코드 불일치 (기술 리뷰어)

의사코드에 fact_registry 참조 없음. "downstream successors of e" 정의 불명확. 재현성 저해.

**대응 방안**: Algorithm 1 의사코드를 실제 코드와 일치하도록 수정

---

## MAJOR 이슈

### M1. Attr-Aware ≈ "전파하지 마라"와 구분 불명확
- 15% 잔여 damage 중 정당한 무효화 vs false positive 미구분
- "No propagation" baseline과의 직접 비교 부재
- Defense Rate 공식 미정의: `1 - (Attr_Damage / BFS_Damage)`라면 no-propagation이 100%

### M2. "Inevitable" 3회 반복 (line 101, 558, 650)
- 검증 불가능한 예측을 과장
- Abstract의 "natural"과 본문의 "inevitable" 불일치

### M3. Subject-key Matching의 Precision/Recall 미보고
- Conflict detection trigger의 정확성이 전체 실험의 전제 조건
- 부정확한 trigger로 시작된 propagation을 측정하고 있을 가능성

### M4. 32K EM Floor 문제
- Baseline EM 0-4%에서 attack의 실질적 영향 측정 불가
- "57.3% memory destruction"이 실제 기능적 손상인지 불확실

### M5. Multi-run 통계 약점
- 개별 조건 Welch p>0.1 (1-fact: 0.126, 3-fact: 0.169, 5-fact: 0.171)
- Pooled Wilcoxon p=0.0022이지만 서로 다른 effect size 합산
- CV~150%, 19개 관측치/7개 그룹 → mixed-effects model에 부족한 샘플

### M6. 합리적 Baseline 누락
- BFS만 비교 대상. Random walk, embedding similarity, LLM-based causal judgment 등 비교 없음
- 특히 depth-1만 전파하는 shallow propagation baseline 부재

### M7. Transportation 비유와 Algorithm 1의 괴리
- 비유: "directional link failure model에서 영감"
- 실제 알고리즘: keyword filtering (subject entity 포함 여부 체크)
- 방향성(directionality)이 아니라 키워드 매칭이 핵심인데 비유가 오도

### M8. KEPo, LogicPoison, KG-RAG Poisoning 미인용
- Graph 구조를 공격 벡터로 활용하는 최신 연구 다수 누락
- "소수 주입 → 대규모 피해" 패턴은 이미 확립된 문헌

### M9. Intro에서 시스템 상세 → Background에서 재반복
- Zep/MAGMA/Mem0가 Introduction(line 68-71)과 Background(line 132-139)에서 이중 기술
- Intro에서는 gap만 언급하고 상세는 Background로 미루는 것이 효율적

### M10. 용어 불일치
- "damage" / "decay" / "collateral damage" 혼용
- "fact" / "memory" / "knowledge" 혼용
- 정의를 한 곳에 모아야 함

---

## MINOR 이슈

### 문체
- "weaponize" / "becomes the weapon" — 선정적 (Abstract, Finding 8)
- "The consistency gap has a clear shape." — 구어체, 모호
- Finding 4, 9가 100단어+ 단일 문단 → 분리 필요
- "co-occurrence ≠ causal dependency" 4회 반복 (2회면 충분)
- "std" 약어 미정의 → "SD" 또는 "standard deviation"

### 표기/기술
- $G=(V,E,L)$ 정의가 Introduction에만 있고 Algorithm 1에서 미참조
- DiGraph를 BFS에서 undirected로 취급한다는 사실이 부록에만 있음
- $\kappa$ 지표의 중요성/임계값 미설명
- mem0_2024 cite key vs year=2025 불일치
- "6% 미만" — 원문은 "at most 7%"

### 누락 인용 (Minor)
- RippleCOT (arXiv:2410.03122) — ripple effect 문헌
- "The Missing Knowledge Layer in Cognitive Architectures" (arXiv:2604.11364)

---

## 대응 우선순위 제안

### Phase 1: 실험 추가 (Critical 해소)
1. **No-propagation vs BFS vs Attr-Aware 3자 비교** — forgetting accuracy 포함 (C1 해소)
2. **Scale-free → heavy-tailed 전환** (C5 해소)
3. **Algorithm 1 의사코드 수정** (C8 해소)

### Phase 2: 문헌 보강
4. **Kumiho 인용 + 차별화** (C3 해소)
5. **MaRS, AGM belief revision 추가** (C6, C7 해소)
6. **KEPo, LogicPoison 등 그래프 공격 문헌 추가** (M8 해소)

### Phase 3: 텍스트 수정
7. **"inevitable" → 완화 표현** (M2 해소)
8. **용어 통일** (M10 해소)
9. **Intro/Background 중복 제거** (M9 해소)
10. **문체 정리** (선정적 표현, 긴 문장 분리)

### Phase 4: 추가 실험 (여력 있을 때)
11. 2번째 벤치마크 추가 (C4 부분 해소)
12. Depth/decay sensitivity analysis 본문 승격
13. Subject-key matching precision/recall 보고 (M3 해소)

---

## 리뷰어 예상 반박 Top 5

1. **"Straw man"**: "BFS가 naive하다는 건 자명하다. 아무도 구현 안 한 이유가 바로 이것이다."
2. **"Attr-Aware = belief revision 재발명"**: "Kumiho가 이미 형식적으로 해결했다."
3. **"단일 조건"**: "하나의 벤치마크, 하나의 모델로 일반화할 수 없다."
4. **"Scale-free 모순"**: "64K에서 기각하고도 scale-free라 주장하는 것은 모순이다."
5. **"So what?"**: "그냥 propagation 안 하면 되는 거 아닌가?"
