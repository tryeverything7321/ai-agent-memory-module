# SCALE Workshop (ICML 2026) 제출 수용 가능성 분석

**분석일**: 2026-04-20
**마감**: 2026-04-24 AoE (4일 남음)
**페이지**: 7페이지 (참고문헌/부록 제외)
**현재 분량**: 21페이지 (본문 ~14페이지 + 부록 ~7페이지)
**워크샵 장소/일시**: 서울, 2026-07-10

---

## 1. Venue Fit 분석 — 가장 중요한 판단

### SCALE CFP에 명시된 Topics

**"Memory of Agents" 트랙에 정확히 매칭되는 항목:**
- ✅ "Memory consolidation, retrieval, and **forgetting** for long-horizon tasks" — **논문의 핵심 주제**
- ✅ "Robustness to noisy or missing multimodal inputs" — adversarial 공격은 robustness 문제
- △ "Short-, long-term, and hierarchical multimodal memory designs" — memory 구조 관련이나 multimodal은 아님

**"Evaluation and Benchmarking" 트랙도 부분 매칭:**
- ✅ "Robustness to noise and distribution shift" — adversarial injection은 distribution shift의 일종
- △ "Real-world, deployment-focused evaluation protocols"

### Fit 평가: **Strong fit (8/10)**

CFP가 "forgetting"을 명시적으로 언급하는 워크샵은 드뭄. SCALE이 이걸 Topics of Interest에 넣었다는 건 이 방향의 연구를 의도적으로 찾고 있다는 신호. 이전에 검토한 MemFM(Memorization in Foundation Models)은 학습 데이터 memorization 주제로 완전히 부적합했는데, SCALE은 정반대로 적합.

---

## 2. 논문의 강점 (Accept 요인)

### S1. 명확한 문제 정의 + 실질적 발견
- "co-occurrence ≠ causal dependency"는 직관적이면서 실증적으로 뒷받침됨
- BFS 69-79% damage → 숫자가 강렬함. 워크샵에서 "wow factor" 있음

### S2. 공격 시나리오의 참신성
- 기존 메모리 공격(MINJA, AgentPoison)은 content injection
- 이 논문은 **시스템 자체의 forgetting 메커니즘을 무기화** — 구조적으로 다른 공격 벡터
- 5 fake facts → 57.3% 파괴는 인상적인 수치

### S3. Defense의 실용성
- Attr-Aware는 LLM 호출 불필요, 10ms 이하 오버헤드
- 78-100% 방어율은 좋은 숫자
- 교통공학 analogy가 interdisciplinary appeal 제공

### S4. 통계적 리거
- Wilcoxon signed-rank, bootstrap BCa CI, mixed-effects model
- 워크샵 페이퍼 치고는 과할 정도로 철저함 → 긍정적 신호

### S5. 시의성
- 2025-2026 메모리 시스템 급증 (Mem0, Zep, MAGMA)
- MITRE ATLAS에 메모리 조작이 공식 기법으로 등재
- SCALE이 서울에서 열리고, 교통공학 전문성이 드러남 → 지역적 관심도

---

## 3. 논문의 약점 (Reject 위험)

### ⚠️ W1. 단일 벤치마크 (CRITICAL — 가장 큰 리스크)

**현상**: MemoryAgentBench 하나만 사용
**리뷰어 공격**: "하나의 벤치마크에서 관찰한 패턴을 일반화할 수 없다"
**실질적 위험도**: **중간-높음**

**하지만 워크샵 기준에서:**
- 워크샵 페이퍼는 main conference와 달리 "일반화"보다 "새로운 관점" 우선
- Limitations에 이미 명시적으로 언급하고 있음
- Zipf's law 기반 일반화 논증이 이론적 보완 역할
- **완화 전략**: Limitations에서 "single benchmark"을 인정하되, 이론적 근거(Zipf → heavy-tail → hub 형성)가 벤치마크 독립적임을 강조

**판정: 워크샵에서는 수용 가능. 다만 리뷰어 1명이 꼬집으면 Major revision 사유.**

---

### ⚠️ W2. 단일 LLM (MAJOR)

**현상**: Gemma-4-31B-it만 사용
**리뷰어 공격**: "LLM에 따라 entity extraction 품질이 달라지면 결론이 바뀌지 않나?"

**실질적 위험도**: **중간**

**완화 요인:**
- 이 논문의 핵심은 LLM 성능이 아니라 **그래프 구조**의 취약성
- Entity extraction은 rule-based (LLM 무관)
- Conflict detection에서 LLM을 쓰지만, subject-key matching이 주요 trigger
- 그래프 위상(topology)이 결론을 결정하므로 LLM 변경의 영향은 제한적

**판정: 논문 내에서 이미 실험이 LLM-agnostic한 이유를 설명 가능. 워크샵에서는 OK.**

---

### ⚠️ W3. Straw Man 우려 (MAJOR)

**현상**: 아무도 구현하지 않은 BFS propagation을 직접 만들고 공격
**리뷰어 공격**: "BFS가 naive한 건 자명. 아무도 구현 안 한 이유가 그것이다."

**실질적 위험도**: **중간-높음** (워크샵에서도 가장 날카로운 질문이 될 것)

**완화 요인:**
- 논문이 "architecturally natural next step"으로 프레이밍을 이미 완화함
- MemoryAgentBench forgetting accuracy <6%가 propagation 필요성의 실증
- "16% stale" 결과가 no-propagation의 문제를 정량화
- 교통공학 "crash testing" 비유가 방어 논리 제공
- **핵심**: Kumiho 인용 + 차별화가 이미 Related Work에 있음

**판정: 워크샵에서는 "새로운 위험 정량화"로 충분. 포스터에서 이 질문은 반드시 나올 것이므로 30초 답변 준비 필요.**

---

### ⚠️ W4. Attr-Aware의 15% 잔여 damage 미분류 (MAJOR)

**현상**: 잔여 14.8-15.8% damage 중 legitimate cascade vs false positive 미구분
**리뷰어 공격**: "Defense가 완벽하지 않은데 그 나머지가 뭔지도 모른다?"

**실질적 위험도**: **중간**

**완화 요인:**
- 15%는 BFS 69-79%에 비해 충분히 낮음
- "Defense Rate" 78-100%라는 수치 자체가 설득력 있음
- 워크샵에서는 "충분히 좋은 결과"로 인정받을 가능성 높음

**판정: Future work으로 충분. 7페이지 축약 시 이 이슈를 깊이 다룰 공간도 없음.**

---

### ⚠️ W5. Subject-key Precision/Recall 미보고 (MAJOR)

**현상**: 전체 실험이 subject-key matching에 의존하는데 이 자체의 정확도가 보고 안 됨
**리뷰어 공격**: "trigger 자체가 틀리면 모든 결과가 의미 없다"

**실질적 위험도**: **중간-높음**

**완화 요인:**
- Appendix C에 subject-key 생성 규칙을 투명하게 공개함
- Rule-based이므로 일관성은 높음 (stochastic LLM보다 재현성 좋음)
- 그래프 수준 분석의 결론(hub 취약성)은 개별 key 정확도에 덜 민감

**판정: 워크샵 7페이지에서 이걸 추가할 공간은 없음. Limitations에 한 줄 추가 권장.**

---

### ⚠️ W6. 32K EM Floor Effect (MINOR)

**현상**: 32K에서 baseline EM이 0-4%라서 adversarial impact 측정이 의미 없음
**이미 Limitations에 명시**: "32K EM floor" (Limitation 5)

**판정: 이미 대응됨. F1 수치로 보완하고 있음.**

---

### ⚠️ W7. Comparison Baseline 부족 (MINOR for workshop)

**현상**: BFS vs Attr-Aware 2개만 비교
**현재 대응**: degree-capped BFS (cap=5/10/20/50)가 Table 8에 있음 → 5개 baseline

**판정: Degree-cap 비교까지 포함하면 워크샵 기준에서는 충분.**

---

## 4. 21 → 7 페이지 축약 전략

현재 21페이지에서 7페이지로 축약해야 함. 이것은 단순 축소가 아니라 **재구성**이 필요.

### 남길 것 (Main body, 7페이지)
| 섹션 | 현재 분량 | 축약 후 | 핵심 |
|------|-----------|---------|------|
| Abstract | 15줄 | 10줄 | 숫자 중심 압축 |
| Introduction | 3페이지 | 1.5페이지 | 4 findings만 유지, 시스템 상세는 Background로 |
| Background | 3페이지 | 1페이지 | Graph systems + forgetting gap만. Security/transport 1문단씩 |
| C1 (Scale) | 2.5페이지 | 1페이지 | Table 1 + Finding 1-3 |
| C3 (Adversarial) | 2페이지 | 1페이지 | Table 4 + gray/black-box 요약 |
| C4 (Defense) | 2페이지 | 1페이지 | Algorithm 1 + Table 7(forgetting accuracy) + defense comparison |
| Related Work | 2.5페이지 | 0.5페이지 | 핵심 5편만 |
| Discussion+Conclusion | 2페이지 | 1페이지 | Implications + Limitations 3줄 |

### 부록으로 이동
- C2 (Cross-task contamination) — 가장 약한 contribution, 부록으로
- Graph topology 상세 분석 (Table 2)
- Multi-run 통계 전체 (Table 9, 10)
- Graph construction details (Appendix C)

### 삭제
- 시스템 상세 중복 (Intro + Background 겹침)
- Future Work 상세 (1줄로 압축)
- Depth analysis 표 (Figure 2로 대체하거나 부록)

---

## 5. 종합 판정

### Accept 확률 추정: **55-65%**

| 요인 | 영향 | 비중 |
|------|------|------|
| Venue fit (forgetting 명시) | ++ 강한 긍정 | 25% |
| 참신한 공격 벡터 | ++ 긍정 | 20% |
| 실증적 수치의 강렬함 | + 긍정 | 15% |
| 단일 벤치마크 | - 부정 | -15% |
| Straw man 우려 | - 부정 | -10% |
| 통계적 리거 | + 긍정 | 10% |
| 21→7 축약 품질 | ? 미지수 | 15% |

### 리스크 시나리오

**Best case (Accept, ~35%)**:
- 리뷰어가 "forgetting" 트랙에 관심 있는 Memory 전문가
- "새로운 공격 벡터 발견"으로 novelty 인정
- 단일 벤치마크는 워크샵 수준에서 감안

**Base case (Borderline/Weak Accept, ~30%)**:
- 리뷰어가 straw man 지적하되, 정량 분석의 가치는 인정
- "minor revision" 또는 "poster only"
- 단일 벤치마크가 약한 감점

**Worst case (Reject, ~35%)**:
- 리뷰어가 "BFS는 자명하게 나쁘다, novelty 없다" 입장
- 또는 "단일 벤치마크 + 단일 LLM = 일반화 불가"
- Kumiho 대비 contribution 미약하다는 판단

### 합격선을 넘기려면 반드시 해야 할 것 (4일 내)

1. **21→7 축약** — 이것 없이는 제출 자체 불가. ICML 2026 LaTeX 템플릿 적용
2. **LLM/Agent usage disclosure 섹션** 추가 (CFP 필수 요구사항, 페이지 제한 미포함)

### 하면 좋은 것 (시간 되면)

3. 2nd LLM 실험 (Llama-3 등) — "LLM-agnostic" 주장 보강
4. Subject-key precision/recall 1줄 보고
5. Attr-Aware 15% residual damage 분류 (legitimate vs FP)

### 하지 않아도 되는 것 (워크샵 기준)

- 2nd 벤치마크 추가 (Zipf 논증으로 충분)
- Learned propagation (Future work)
- Depth/decay sensitivity full sweep

---

## 6. 핵심 판단: 제출해야 하나?

### **YES — 제출하는 것을 권장**

**이유:**
1. **Non-archival** — 불합격이어도 손해 없음. 다른 venue에 재제출 가능
2. **Dual submission 허용** — 동시 제출 가능
3. **SCALE의 forgetting 토픽 매칭** — 이보다 적합한 venue를 찾기 어려움
4. **서울 개최** — 현장 참석 용이
5. **7페이지 축약 자체가 가치** — full paper 승격 시에도 workshop version이 피드백 확보 채널

**최악의 경우에도:**
- 리뷰어 피드백 → full paper 개선에 직접 활용
- 포스터 세션 → 연구 네트워크 형성
- 제출 이력 → 연구 타임라인 기록

---

## 부록: SCALE 워크샵 상세

- **마감**: 2026-04-24 AoE
- **알림**: 2026-05-15
- **포맷**: ICML 2026 LaTeX style
- **트랙**: Main (7p), Benchmarking/Dataset (7p), Late-Breaking (3p)
- **리뷰**: Double-blind
- **필수**: LLM/Agent usage disclosure section
- **특이사항**: Dual submission 허용, Non-archival
