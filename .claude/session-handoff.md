# Session Handoff — 2026-04-20 (Updated)
**작업 디렉토리**: `/home/mingyu1choi/PJT/memory_module`
**브랜치**: `feat/deep-dive-analysis`
**타겟**: ICML 2026 워크샵 페이퍼

---

## 완료된 작업

### 세션 2026-04-20 (ICML 워크샵 준비)
1. **Forgetting Accuracy 3-arm 결과를 본문에 통합** — Table 7 (forgetting_accuracy) + Finding 12 추가
   - Abstract에 "16% stale" 동기 추가, Introduction "Four findings"로 확장, Conclusion에 Attr-Aware 94% 수치 반영
2. **선정적 용어 정리** — catastrophic 10→2회, destroy 9→3회, blast radius/devastating/toxic 제거
3. **누락 인용 추가** — AGM framework (1985), Hansson Relevance postulate (1999) bib + citation 추가
4. **LaTeX 컴파일 확인** — 21페이지, undefined refs 0, bibtex warning 2 (기존 minor)

### 이전 세션 (2026-04-15)
- 4개 전문 에이전트 리뷰 → `.review/2026-04-10-full-paper-review.md`
- 문헌 수집 967편 → 55편 선별 → `paper/literature_survey_2026.md`
- Introduction/Background/Related Work/Abstract 대폭 재작성
- references.bib 정비 (오류 3건 수정, 16편 추가)
- 실험 보강 7건 완료 → `.claude/todo-paper-experiments.md` (전부 ✅)

### 이번 세션 (2026-04-16)
1. **Introduction/Background 팩트체크** — Zep/MAGMA/Mem0 기술 과장 수정 (dd6e9f6)
   - 웹/논문 검증 후 "contradiction metadata" → "bi-temporal validity windows" 등 정확한 표현으로 교체
2. **Adversarial Review 실행** — 4개 리뷰어 병렬 투입
   - Technical Reviewer, Logic Reviewer, Research Analyst, Writing Reviewer
   - 결과: `.review/2026-04-16-adversarial-review.md` (Critical 8건, Major 22건+)
3. **대응 계획 수립** — 3개 연구 에이전트로 조사 후 계획 작성
   - Kumiho 논문 분석 + 차별화 전략
   - MaRS + forgetting 문헌 조사 + Related Work 초안
   - Forgetting accuracy 실험 설계 (코드 구조 분석 완료)
   - 결과: `.review/2026-04-16-response-plan.md`

---

## 남은 작업 (ICML 워크샵 기준)

### 완료됨 ✅
- ~~Scale-free → heavy-tailed 전환~~ (이전 세션에서 완료)
- ~~Algorithm 1 의사코드 수정~~ (이전 세션에서 완료)
- ~~문헌 보강 — Kumiho, MaRS, KEPo~~ (이전 세션에서 완료)
- ~~선정적 표현 완화~~ (2026-04-20 완료)
- ~~Forgetting Accuracy 본문 통합~~ (2026-04-20 완료)
- ~~AGM/Hansson 인용 추가~~ (2026-04-20 완료)

### 워크샵 제출 전 (선택)
1. **ICML 워크샵 템플릿 적용** — 워크샵별 상이, CFP 확인 필요
2. **Abstract 축소** — 현재 ~200단어 → 150단어 권장
3. **2번째 LLM 실험 (Llama)** — 일반화 강화 (nice-to-have)

### Full paper 승격 시
4. **2번째 벤치마크 추가** — MemoryArena 또는 LongMemEval
5. **Subject-key matching precision/recall** — M3 해소
6. **Learned propagation policy** — GNN 기반 (ICML main fit 강화)

---

## 핵심 참고 파일
- `.review/2026-04-16-adversarial-review.md` — 전체 리뷰 결과
- `.review/2026-04-16-response-plan.md` — 대응 계획 (Phase 1-4)
- `.claude/todo-paper-experiments.md` — 이전 실험 TODO (전부 완료)

## ⚠️ 충돌 방지
- **이 세션 범위**: `paper/`, `.review/` 디렉토리
- **건드리지 말 것**: `serving_research/`, memory_module 코드 파일
