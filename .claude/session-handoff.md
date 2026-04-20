# Session Handoff — 2026-04-20 (Revision Session 준비)
**작업 디렉토리**: `/home/mingyu1choi/PJT/memory_module`
**브랜치**: `feat/deep-dive-analysis`
**타겟**: ICML 2026 SCALE Workshop, **마감 4/24 AoE**
**다음 세션 목적**: workshop.tex revision 실행

---

## 이번 세션에서 한 일

1. **외부 리뷰 2건 분석** — 사용자가 다른 세션(또는 외부 LLM)에서 받은 상세 리뷰 2건을 workshop.tex와 대조 검증
2. **Revision 계획 작성 2건**:
   - 이 세션: `.review/260420_revision_plan.md` (MUST/SHOULD/NICE 분류, 교차 검증 분석)
   - 다른 세션(세션 B): `docs/260420_revision_plan_scale_workshop_v2.md` (Phase A~G, 실행용 LaTeX 코드 포함)
3. **두 계획 비교 분석** 완료 — 아래 "실행 가이드" 참조

---

## 다음 세션이 해야 할 일: workshop.tex Revision

### 읽어야 할 파일 (우선순위순)
1. **`docs/260420_revision_plan_scale_workshop_v2.md`** — 실행 기준 문서. LaTeX 코드 블록이 있어서 바로 적용 가능
2. **`.review/260420_revision_plan.md`** — 판단 근거 문서. 왜 이렇게 수정하는지, 뭘 수정 안 하는지의 이유
3. **`paper/workshop.tex`** — 수정 대상 (470줄)
4. **`paper/references.bib`** — bib 수정 대상 (404줄)

### 두 계획의 교차 분석 결론 (이 세션에서 도출)

**세션 B(docs/) 계획을 실행 기준으로 삼되, 아래 보완 사항 반영:**

#### 세션 B 계획대로 실행할 것
- Phase A: 템플릿 AUTHORERR, Algorithm `h` 초기화 + `\textsc` 버그, bib placeholder
- Phase B: Abstract 전면 재작성 (세션 B가 제시한 대안 abstract 사용)
- Phase C: Contribution 4개로 재구조화
- Phase D: "causal" 일괄 교체, "destroys" → "degrades", Finding 2 수치, Discussion 톤
- Phase E: Metric 정의, Section 3 예시, straw man 방어, 공격 경로, Table caption
- Phase F: Efficiency 수치, Limitation 2개 추가, multimodal 문구
- Phase G: 수정하지 않는 것 목록 준수

#### 보완해야 할 것 (세션 B에 없거나 부족한 것)
1. **시간 추정**: 세션 B의 "2시간 20분"은 과소. **현실적으로 5-7시간** 예상. 특히 bib 검증(1-2h)과 Abstract/Contribution 재작성 후 전체 톤 일관성 확인(1h)이 오래 걸림
2. **bib 검증은 WebSearch로 직접 확인** — 두 리뷰 모두 지적한 P0 항목:
   - `memoryagentbench_2026`: 저자가 Huang/Zhang/Lin인지 Hu/Wang/McAuley인지 arXiv에서 확인
   - `mem0_2024`: 저자가 Chheda/Singh/Srinivasan인지 Chhikara/Khant/Aryan/Singh/Yadav인지 확인
   - `kepo_2026`, `logicpoison_2026`: `{KEPo Authors}`, `{LogicPoison Authors}` → 실제 저자명 조사
   - `zep_2025`: blog reference → arXiv paper로 업그레이드 가능 여부
3. **Section 5 제목 변경**: "Adversarial Hub Exploitation" → "Hub-Targeted Amplification" — 세션 B가 제안, 이 세션도 동의
4. **Finding 1 (174줄)**: "reducing collateral damage by half" → "reducing collateral damage, though 25% residual collateral indicates room for improvement" — 더 솔직한 표현

#### 절대 하지 말 것
- Section 구조 전면 재편 (Background+Section3 합치기) — 마감 4일 전에 위험
- Algorithm 전체 재작성 (queue-based) — h 초기화 + textsc만 수정
- 새 실험 추가 (2nd LLM, 2nd benchmark 등) — Phase 3/Full paper 때
- Cross-task section 위치 이동 — Intro에서 강조하는 것으로 대체
- "causal" 완전 삭제 — Kumiho/AGM 지칭 시에는 유지

---

## 실행 순서 권장

```
1단계: bib 검증 (WebSearch) — 가장 먼저. 결과에 따라 본문 인용도 바뀔 수 있음
2단계: Phase A (Trust Breakers) — 템플릿, Algorithm 버그
3단계: Phase B+C (Abstract + Contribution) — 핵심 프레이밍 변경
4단계: Phase D (Overclaiming 완화) — 가장 많은 수정, "causal" grep 확인
5단계: Phase E+F (Clarity + SCALE Fit) — 문장 추가
6단계: 최종 컴파일 + 검증 체크리스트 (세션 B v2 문서 "10. 검증 체크리스트" 참조)
```

## 검증 체크리스트 (수정 완료 후)

```
[ ] latexmk -pdf workshop.tex 에러 0
[ ] PDF 1페이지에 AUTHORERR 없음
[ ] 7페이지 이내 (ref/appendix 제외)
[ ] grep -i "causal" → 우리 method 지칭 시 0건 (Kumiho/AGM만 허용)
[ ] grep "destroys\|destroyed" → 0건
[ ] grep "no LLM overhead" → 0건 ("no LLM calls during propagation"만)
[ ] grep "exploitation" → Section 제목에 0건
[ ] Algorithm 1에서 h 정의 확인
[ ] bib에 placeholder 저자 없음
[ ] Finding 2에 검증 불가능한 Kill 절대수치 없음
[ ] Table 2/3 caption에 실험 구분 명시
[ ] Abstract에 "MemoryAgentBench" 명시 (controlled study)
[ ] Contribution에 "co-occurrence graphs" 범위 명시
[ ] Straw man 방어 문구 존재 (Section 4 Setup)
[ ] Limitation (5), (6) 추가됨
```

---

## 이전 세션 기록 (참고)

### 세션 2026-04-20 (ICML 워크샵 준비 — 이전)
1. Forgetting Accuracy 3-arm 결과 본문 통합
2. 선정적 용어 정리 (catastrophic 10→2회 등)
3. AGM/Hansson 인용 추가
4. LaTeX 컴파일 확인 — 21페이지(main.tex), undefined refs 0

### 세션 2026-04-16
1. Introduction/Background 팩트체크
2. Adversarial Review 4개 리뷰어 병렬 실행 → `.review/2026-04-16-adversarial-review.md`
3. 대응 계획 수립 → `.review/2026-04-16-response-plan.md`

---

## 핵심 참고 파일
| 파일 | 용도 |
|------|------|
| `docs/260420_revision_plan_scale_workshop_v2.md` | 실행 기준 (LaTeX 코드 포함) |
| `.review/260420_revision_plan.md` | 판단 근거 (교차 분석) |
| `.review/2026-04-16-adversarial-review.md` | 이전 리뷰 결과 |
| `.review/2026-04-16-response-plan.md` | 이전 대응 계획 |
| `paper/workshop.tex` | 수정 대상 |
| `paper/references.bib` | bib 수정 대상 |

## 충돌 방지
- **이 세션 범위**: `.review/`, `.claude/session-handoff.md`
- **다음 세션 범위**: `paper/workshop.tex`, `paper/references.bib`
- **건드리지 말 것**: `serving_research/`, memory_module 코드 파일, `paper/main.tex` (full paper는 별도)
