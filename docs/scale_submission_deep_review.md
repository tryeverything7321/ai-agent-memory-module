# SCALE Workshop 제출 심층 리뷰 — 4-Agent 통합 분석

**분석일**: 2026-04-20
**리뷰어**: Technical Reviewer, Logic Reviewer, Research Analyst, Writing Reviewer
**대상**: "Collateral Damage in Graph-based Memory Forgetting" → SCALE @ ICML 2026

---

## 🔴 RED FLAGS — 반드시 해결해야 할 문제 (3건)

### RF1. BDR 자기모순 (Logic Reviewer 발견)

**논문 자체 메트릭이 논문의 핵심 주장을 반박합니다.**

Table 7의 Benefit-Damage Ratio:
- No-Propagation: **0.840** (최고)
- Attr-Aware: 0.752
- BFS: 0.651

→ 논문 자체가 만든 메트릭으로 보면 **"전파하지 않는 것이 가장 좋은 trade-off"**입니다. 그런데 Finding 12에서 "propagation is necessary"라고 결론짓습니다.

**왜 심각한가**: 리뷰어가 "So what? Just don't propagate"라고 물으면 논문 전체의 동기가 무너집니다.

**해결 방안**:
1. BDR 공식 자체를 재설계하거나, BDR을 삭제하고 다른 관점으로 전환
2. "16% stale이 production에서 어떤 functional harm을 유발하는지" 실증 추가
3. 또는 프레이밍 전환: "전파가 필요하다"가 아니라 **"전파를 시도하면 이렇게 위험하다, 시도하려면 반드시 Attr-Aware가 필요하다"**

→ 3번이 가장 현실적. "propagation is necessary" 주장을 약화하고, "if you propagate, do it right" 메시지로 전환.

---

### RF2. Algorithm 1 라인 참조 오류 (Technical Reviewer 발견)

**[main.tex:506]** "without the semantic filter (line 9)"라고 쓰지만:
- Line 9는 `in_degree` 계산 (semantic filter 아님)
- Semantic filter는 **line 5** (`M_down = facts where e is subject`)

또한 시간복잡도 표기(line 512)에서 `|K_changed|`가 Algorithm 내에서 정의되지 않음.

**해결**: 라인 번호 수정 + 복잡도 재기술.

---

### RF3. references.bib placeholder 저자 (Technical + Research Analyst 발견)

- `{KEPo Authors}`, `{LogicPoison Authors}`로 실제 저자 정보 없음
- `mplus_2025`의 존재 자체가 불확실 (가짜 인용 가능성)

**해결**: 제출 전 반드시 arXiv에서 정확한 저자 정보 확인 및 수정.

---

## 🟡 MAJOR CONCERNS — 해결하면 Accept 확률 크게 상승 (5건)

### MC1. "Straw Man" 프레이밍이 아직 약함

**4개 에이전트 모두 지적.** 핵심 문제:
- CASCADE 비유(line 72)가 오히려 **typed-relation 전파의 자연스러움**을 시사 → co-occurrence BFS가 "natural next step"이라는 주장을 약화
- "architecturally natural"이라면서 아무도 구현 안 한 이유에 대한 설명 부족

**해결**: 프레이밍을 "propagation is inevitable" → **"propagation is increasingly plausible, and its failure modes must be understood before adoption"**으로. Kumiho와의 관계를 "경쟁" → **"complementary evidence"**로 재포지셔닝.

---

### MC2. Table 7 위치 문제 (Logic + Research Analyst 발견)

논문의 가장 근본적 전제("전파가 필요하다")를 뒷받침하는 실험이 **C4 섹션 (Section 6) 안에 매몰**되어 있음. 리뷰어는 C1-C3를 읽는 동안 "왜 전파가 필요한데?"라는 의문을 3개 섹션 동안 풀지 못함.

**해결**: 7페이지 축약 시 Table 7을 **Section 2 (Background) 끝 또는 Section 3 (C1) 앞**으로 이동.

---

### MC3. Abstract의 power-law α값이 오해 유발

Abstract에서 `α = 2.73--2.96`만 보고하고, 64K에서 KS test가 기각(p=0.009)된 사실을 언급하지 않음. 본문에서는 정직하게 보고하지만, abstract만 읽는 리뷰어는 오해할 수 있음.

**해결**: Abstract에서 α값 삭제하거나, "heavy-tailed (not strictly scale-free)"를 명시.

---

### MC4. Venue Fit 미세 약점 — Multimodal 요소 부재

SCALE의 풀네임이 "Scalable Learning and Optimization for **Efficient Multimodal** AI Agents". 이 논문에는:
- Multimodal 요소 없음 (텍스트 전용)
- Scaling/efficiency 최적화보다 security/reliability 분석

**완화**: "Memory of Agents" 트랙의 "forgetting" 토픽에 정확히 매칭되므로 reject 사유는 아님. 다만 Introduction에서 "multimodal agent systems that maintain persistent memory" 정도의 연결 문구 추가 권장.

---

### MC5. Attr-Aware 15% residual damage + Baseline 수치 불일치

- Table 5: Attr-Aware 25% collateral damage (controlled scenarios)
- Table 6: Attr-Aware 0.3% (6K adversarial)
- 두 실험의 차이가 명확히 설명되지 않음
- Table 3 baseline (EM=15%, F1=67.1%) vs Table 4 baseline (EM=20%, F1=70.9%) 불일치 — temp=0.0인데 왜 다른지?

**해결**: 축약 시 표 통합으로 자연스럽게 해결. 불일치 원인(다른 데이터셋 split)을 각주로 설명.

---

## 🟢 MINOR / 워크샵에서 수용 가능 (6건)

| 이슈 | 판정 | 이유 |
|------|------|------|
| 단일 벤치마크 | 수용 가능 | Zipf 논증 + Limitations 명시 |
| 단일 LLM | 수용 가능 | 실험이 LLM-agnostic (rule-based extraction) |
| Subject-key precision/recall 미보고 | 수용 가능 | 7페이지 공간 부족, Limitations 한 줄 추가 |
| 32K EM floor | 수용 가능 | 이미 Limitation에 명시, F1로 보완 |
| 통계 검정력 (19 obs) | 수용 가능 | 솔직한 보고 + mixed-effects 시도 |
| Comparison baseline 부족 | 수용 가능 | degree-cap 비교 5개가 이미 존재 |

---

## 📐 축약 전략 (21 → 7 페이지)

### 삭제/부록 이동 대상

| 항목 | 절감 |
|------|------|
| Introduction 시스템 상세 (Zep/MAGMA/Mem0) — Background에서만 설명 | ~0.8p |
| Background §2.1을 표 1개로 압축 | ~1.0p |
| Background §2.5 (Evaluation Framework) → C1 Setup으로 통합 | ~0.5p |
| C2 (Cross-task) 전체 → 부록 | ~1.5p |
| C3 Depth analysis (Table 10, Figure 2) → 부록 | ~0.8p |
| Related Work 5개 카테고리 → 각 2-3문장 | ~1.5p |
| Discussion → Limitations 3줄 + Conclusion 통합 | ~0.7p |
| Graph construction appendix → 유지 (부록) | 0p |

**총 절감: ~6.8페이지 → 본문 ~14페이지가 ~7페이지로**

### Finding 축소: 12개 → 8개

유지: F1, F2, F3, F4, F6, F8, F11, F12
삭제/흡수: F5(F2와 중복), F7(F8에 흡수), F9(본문 흡수), F10(부록으로)

### 핵심 테이블 유지 (7개 → 5개로 축소)

1. Table 1 (Scale trend — C1 핵심)
2. Table 4 (Adversarial attack — C3 핵심)
3. Table 5 or 6 (Black/gray/white box — C3 보조, 통합 가능)
4. Table 7 (Forgetting accuracy 3-way — 위치 이동!)
5. Table 8 (Defense comparison — BFS vs cap=5 vs Attr-Aware 3행으로 축소)

### 재구성된 논문 구조 (7페이지)

```
Abstract (150단어)
1. Introduction (1.5p) — 문제 + 4 findings 요약 + contributions
2. Background & Related Work (1.5p) — 시스템 표 + forgetting gap + security + transport analogy + related work 통합
3. Why Propagation Matters (0.5p) — Table 7 (forgetting accuracy) ← 여기로 이동!
4. Collateral Damage at Scale (1.0p) — C1 핵심 + topology
5. Adversarial Hub Exploitation (1.0p) — C3 + black/gray/white box
6. Attr-Aware Defense (1.0p) — Algorithm 1 + defense comparison
7. Discussion & Conclusion (0.5p) — implications + limitations 3개 + future work 2개
Appendix: C2 (cross-task), depth analysis, graph construction, multi-run stats
```

---

## 💡 4-Agent 합의 사항

### "제출해야 하는가?"에 대한 일치된 판단: **YES, 단 RF1-RF3 해결 후**

| 에이전트 | 판정 | 조건 |
|---------|------|------|
| Technical | 제출 권장 | bib placeholder 수정, Algorithm 라인 참조 수정 |
| Logic | 조건부 제출 | **BDR 자기모순 반드시 해결**, Table 7 위치 이동 |
| Research Analyst | 제출 권장 | Kumiho 재포지셔닝, C2를 부록으로 |
| Writing | 제출 권장 | Abstract 150단어, Finding 8개로 축소 |

### Accept 확률 (해결 전 vs 후)

| 상태 | 추정 |
|------|------|
| 현재 그대로 21p 제출 (불가) | N/A |
| 7p 축약만 | 40-50% |
| 7p + RF1-RF3 해결 | **55-65%** |
| 7p + RF + MC1-MC2 해결 | **60-70%** |

---

## ⏰ 4일 작업 계획 (제안)

### Day 1 (4/21): RF 해결 + 구조 재설계
- [ ] RF1: BDR 자기모순 → 프레이밍 전환 ("if you propagate, do it right")
- [ ] RF2: Algorithm 1 라인 참조 + 시간복잡도 수정
- [ ] RF3: references.bib placeholder 저자 확인/수정
- [ ] MC2: Table 7 위치를 Section 3 앞으로 이동

### Day 2 (4/22): 축약 작업
- [ ] ICML 2026 LaTeX 템플릿 적용
- [ ] Abstract 150단어로 축약 (α값 삭제)
- [ ] Background + Related Work 통합 (1.5p)
- [ ] C2 전체 → 부록 이동
- [ ] Finding 12→8 축소

### Day 3 (4/23): 마무리 + LLM/Agent disclosure
- [ ] Introduction 재작성 (1.5p)
- [ ] 톤 정리 (catastrophically, destroyed, kill 교체)
- [ ] LLM/Agent usage disclosure 섹션 추가 (CFP 필수)
- [ ] 전체 읽기 + 일관성 확인

### Day 4 (4/24): 컴파일 + 제출
- [ ] LaTeX 컴파일 → 7페이지 확인
- [ ] 익명화 재확인
- [ ] PDF 제출
