# Orchestrator Synthesis: Full Paper Review
**Date**: 2026-04-10
**Scope**: main.tex 전체 (Introduction, Background, Methodology, Results, Related Work)
**Agents**: Technical Reviewer, Logic Reviewer, Research Analyst, Paper Crawler

---

## Overview

논문 "Collateral Damage in Graph-based Memory Forgetting"은 시의적절한 연구 질문을 다루지만, **Background/Introduction의 동기 부여 부족**, **핵심 문헌 누락 (11+편)**, **기술적 주장의 엄밀성 부족 (scale-free, 통계)**, **논리 흐름의 편향**이 주요 약점이다. 방법론 자체는 합리적이나 보강이 필요하다.

---

## Critical Issues (5 items)

### C1. [Literature] 핵심 메모리 공격 문헌 미인용
- *Found by*: Research Analyst, Paper Crawler
- *Principle*: E1, E2
- MINJA (NeurIPS 2025, 98% 주입 성공률), AgentPoison (NeurIPS 2024, 80% 공격 성공), ER-MIA (2026), Memory Poisoning Attack & Defense (2026) 등 **메모리 특화 공격 논문이 전혀 인용되지 않음**. Reviewer에게 "최신 문헌을 모른다"는 인상을 줌.
- *Suggested action*: references.bib에 추가하고, Related Work의 "Adversarial attacks" 카테고리를 대폭 확장. Introduction에서 adversarial 동기 부여에 활용.

### C2. [Literature] Graph Unlearning / Belief Revision 분야 완전 누락
- *Found by*: Research Analyst, Paper Crawler
- *Principle*: E1
- ScaleGUN, OpenGU (graph unlearning), ChainEdit (ACL 2025, ripple effect), RippleEdits (TACL 2024), AGM belief revision in KGs 등. 논문의 문제는 본질적으로 "그래프에서 정보 제거 시 cascade"이므로 machine unlearning과의 관계를 반드시 논의해야 함.
- *Suggested action*: Related Work에 "Machine Unlearning & Knowledge Revision" 카테고리 신설.

### C3. [Technical] Scale-free 주장이 Clauset et al. (2009) 모범 사례 미준수
- *Found by*: Technical Reviewer
- *Lines*: main.tex:183-208
- KS goodness-of-fit test 미보고, 대안 분포(log-normal, exponential) 비교 없음, k_min=2가 추정이 아닌 가정. "scale-free properties"라는 단정적 표현은 "consistent with heavy-tailed/scale-free properties"로 약화 필요.
- *Suggested action*: (1) KS test + p-value 추가, (2) log-normal vs power-law 우도비 검정 추가, (3) k_min 추정 절차 기술, (4) 언어 완화.

### C4. [Technical] 통계 분석의 방법론적 문제
- *Found by*: Technical Reviewer
- *Lines*: main.tex:540-566
- 공격 강도별(1/3/5 facts) 풀링하여 Wilcoxon 검정하는 것은 방법론적으로 의문. 서로 다른 treatment level을 혼합하여 n을 부풀림. 3-fact/5-fact의 개별 p-value는 비유의적(0.169, 0.171). Attr-Aware의 음수 damage 값(-0.1) 미설명.
- *Suggested action*: (1) 풀링 정당화를 명시하거나 mixed-effects model 사용, (2) 음수 값 설명 추가, (3) 개별 검정의 underpowered 상태를 더 솔직히 인정.

### C5. [Structure] Introduction에 Nugget이 없고 broader context 부재
- *Found by*: Logic Reviewer, Research Analyst
- *Principle*: A6 (GPS), A7 (Nugget)
- 핵심 통찰 "co-occurrence ≠ causal dependency"가 Conclusion 마지막 문장에서야 등장. Introduction 첫 문단이 바로 기술적 세부사항으로 진입하여 "왜 지금 이 문제가 중요한가"(시장 성장, 벤치마크 실패, 보안 사고)에 답하지 않음.
- *Suggested action*: (1) Intro 첫 문단에 macro-level 동기 부여 추가, (2) Nugget을 Abstract 2번째 문장과 Intro 1번째 단락 마지막에 명시.

---

## Important Issues (8 items)

### I1. [Technical] Co-occurrence graph 구축 방법 미기술
- *Found by*: Technical Reviewer
- *Lines*: main.tex:505
- Entity extraction 방법, co-occurrence 정의, edge direction 규칙, window size 등이 없음. 재현성의 가장 큰 gap.
- *Suggested action*: Method 섹션 또는 Appendix에 graph construction subsection 추가.

### I2. [Technical] decay_per_hop=0.5, depth=2 정당화 없음
- *Found by*: Technical Reviewer
- *Lines*: main.tex:509
- 두 하이퍼파라미터 모두 선택 근거 없음. Sensitivity analysis 미제공.
- *Suggested action*: 최소한 depth와 decay에 대한 ablation study 결과 또는 선택 근거 기술.

### I3. [Structure] Background와 Related Work 간 심각한 중복
- *Found by*: Logic Reviewer
- *Lines*: main.tex:100-106 vs 419-425
- 동일한 6개 시스템이 거의 같은 설명으로 두 번 나열됨. "architecturally natural" 표현도 3회 반복.
- *Suggested action*: Background에서 상세 서술, Related Work는 positioning 관점으로 차별화. 반복 표현 제거.

### I4. [Structure] Intro의 narrative bias — steel-manning 부재
- *Found by*: Logic Reviewer
- *Lines*: main.tex:62-67
- "왜 typed-relation graph를 먼저 시도하지 않는가?", "왜 depth 제한이 충분하지 않은가?" 등 명백한 반론에 대한 선제 대응이 없음.
- *Suggested action*: Background에서 대안적 접근법을 검토하고 기각하는 논증 추가.

### I5. [Citation] references.bib 오류 다수
- *Found by*: Technical Reviewer
- chen_network_2012: key는 2012, entry는 year={2007}
- perez_prompt_injection_2022: 실제로는 Schulhoff et al. 2023 (HackAPrompt), 원래 prompt injection 논문이 아님
- mem0_2024: key는 2024, year={2025}
- mplus_2025, mitre_atlas_2023, guardrails_survey_2024: 정의됨but 미인용
- *Suggested action*: 각 오류 수정, 미사용 엔트리 제거 또는 본문에서 인용.

### I6. [Technical] Algorithm 1의 α 기호 충돌
- *Found by*: Technical Reviewer
- *Lines*: main.tex:354 vs 190-208
- Algorithm 1에서 α = in-degree, Section 3.3에서 α = power-law exponent. 혼동 유발.
- *Suggested action*: Algorithm의 α를 d_in 또는 η로 변경.

### I7. [Literature] 그래프 기반 에이전트 메모리 survey 미인용
- *Found by*: Research Analyst, Paper Crawler
- "Graph-based Agent Memory: Taxonomy, Techniques, and Applications" (2026)는 분야의 분류 체계를 제공하며 반드시 인용 필요. MemoryArena (2026), LongMemEval (ICLR 2025)도 벤치마크 landscape 완성을 위해 필요.
- *Suggested action*: Background에 추가.

### I8. [Technical] Abstract 수치 오류
- *Found by*: Technical Reviewer
- *Lines*: main.tex:51
- "68.9--78.5%"라고 기술하지만, Table 2에서 32K는 79.0%. "68.9--79.0%"가 정확.
- *Suggested action*: 수정.

---

## Minor Issues (6 items)

### M1. Sec 2.3 (MemoryAgentBench)이 Background보다 Experimental Setup에 적합
### M2. Sec 2.1→2.2, 2.2→2.3 전환 bridge 부재
### M3. "Superlinear hub degree growth" — 3개 데이터 포인트로 superlinear 주장은 약함
### M4. Cross-task 실험(C2)이 n=1 (Debbie 엔티티) — 일반화 불가
### M5. Attr-Aware의 비교 baseline이 degree capping뿐 — semantic threshold 등 추가 필요
### M6. Gray-box 공격 실험 미수행 — threat model에 정의만 하고 실험 없음

---

## Patterns Observed

1. **문헌 조사 부족**: 메모리 공격(MINJA, AgentPoison), graph unlearning, belief revision, 최신 survey 등 핵심 분야가 통째로 누락. 인용 수 16개는 이 주제 범위 대비 매우 적음.
2. **기술적 엄밀성 vs 접근성 균형 실패**: Scale-free 주장과 통계 분석에서 엄밀한 절차가 빠진 반면, 결론은 단정적. Clauset et al. (2009) 인용하면서 그 방법론을 따르지 않음.
3. **Narrative의 순환적 반복**: "architecturally natural" 3회, 시스템 나열 2회, "catastrophically flawed" 2회. Introduction/Background/Related Work 간 구조적 중복.
4. **Proactive safety research 프레이밍 부재**: 가장 강력한 positioning("아직 구현되지 않은 위험을 미리 분석")이 명시되지 않음.

---

## Recommendations (우선순위순)

1. **Introduction 재구성**: macro-level 동기 → nugget 명시 → GPS 리듬 적용 → steel-manning 추가
2. **Background 대폭 확장**: Memory Security Landscape subsection 신설, 벤치마크 결과로 forgetting 어려움 입증
3. **Related Work 3개 카테고리 추가**: Machine Unlearning, Memory-specific Attacks, Belief Revision
4. **references.bib 정비**: 오류 수정 + 최소 10편 핵심 문헌 추가
5. **Scale-free 분석 보강**: KS test, 대안 분포 비교, 언어 완화
6. **Graph construction 상세 기술**: entity extraction, co-occurrence definition, edge direction
7. **통계 분석 보강**: 풀링 정당화 또는 대안 분석, 음수 값 설명

---

## Next Steps (2026-04-15 업데이트)

- [x] Introduction 재작성 (section-drafter) — 완료
- [x] Background ���장 (section-drafter) — 완료 (3→5 subsections)
- [x] Related Work 확장 (section-drafter) — 완료 (4→7 categories)
- [x] references.bib 업데이트 (직접 편집) — 완료 (+16편, 오류 3건 수정)
- [x] Abstract 수치 수정 + nugget 삽입 — 완료
- [x] Algorithm 1 α 기호 충돌 해소 — 완료 (α→d_in)
- [x] Scale-free 언어 완화 — 완료 (Abstract, Finding 4, Conclusion)
- [x] "architecturally natural" 반복 제거 — 완료 (3회→1회, Discussion/Conclusion 표현 변경)
- [x] "superlinear" 주장 완화 — 완료 (4곳 → "disproportionately" + 3-point caveat)
- [x] decay_per_hop/depth 정당화 추가 — 완료 (Experimental Setup에 근거 문단 추가)
- [x] 미인용 bib 엔트리 해소 — 완료 (mplus_2025, guardrails_survey_2024 본문 인용 추가)
- [x] **α 값 불일치 수정** — 완료 (2.30-2.48 → 2.73-2.96, 5곳 일괄 수정)
- [x] **κ 정의 추가** — 완료 (Finding 4에 κ ≡ ⟨k²⟩/⟨k⟩ 정의 삽입)
- [x] **bib "Various" 저자 10건 실명 교체** — 완료 (ermia, memory_poisoning, chainedit 등)
- [x] **누락 인용 3편 추가** — 완료 (hu_memory_age_2025, li_memos_2025, chen_lane_resilience_2024)
- [x] **Algorithm 1 hop 변수 명확화** — 완료 (h 파라미터 + 재귀 호출 명시)
- [x] **"first to implement" 한정어** — 완료 ("in external non-parametric memory stores")
- [x] **"architecturally inevitable" 완화** — 완료 ("architecturally likely")
- [x] **섹션 전환 bridge 추가** — 완료 (C2, C3 앞에 도입 문단)
- [x] **Discussion 7.2 확장** — 완료 (2문장→5문장)
- [x] **Intro findings/contributions 중복 축소** — 완료 (findings 간결화)
- [x] **CASCADE 비유 반복 제거** — 완료 (Sec 2.1에서 삭제)
- [x] **"simply traversing" 제거** — 완료
- [x] **인용 없는 주장 수정** — 완료 ("Microsoft Copilot" → 일반화된 표현)
- [x] **perez→greshake 키 이름 수정** — 완료
- [x] **data_poisoning_2021 미사용 엔트리 삭제** — 완료
- [ ] Scale-free KS goodness-of-fit test (실험 재실행 필요)
- [ ] 통계 분석 보강: 풀링 정당화, 음수 damage 설명 (실험 재실행 필요)
- [ ] Graph construction 상세 기술 추가 (entity extraction, co-occurrence 정의)
- [ ] TBD placeholder 채우기: Table 6, 8 + Finding 6, 9 (실험 필요)
- [ ] 3-fact Wilcoxon p=0.146 유의성 인정 (실험/텍스트)
- [ ] Gray-box 공격 실험 추가 (선택적)
- [ ] Cross-task 실험 확장 n>1 (선택적)

---

## 생성된 파일 목록

| 파일 | 내용 |
|------|------|
| `paper/literature_survey_2026.md` | 55편 문헌 서베이 (6개 영역) |
| `paper/papers.json` | 분류된 253편 JSON |
| `paper/papers_raw.json` | 원본 967편 JSON |
