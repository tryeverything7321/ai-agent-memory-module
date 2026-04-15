# Session Handoff — 2026-04-15 (Updated)
**작업 디렉토리**: `/home/mingyu1choi/PJT/memory_module`

---

## 완료된 작업 (이번 세션)

### Stage 1: 진단 (이전 세션 완료)
- 4개 전문 에이전트 리뷰 → `.review/2026-04-10-full-paper-review.md`
- 문헌 수집 967편 → 55편 선별 → `paper/literature_survey_2026.md`

### Stage 2-3: 보강/개선 (이번 세션 완료)
1. **references.bib 정비** — 오류 3건 수정, 핵심 논문 16편 추가
2. **Introduction 재작성** — macro context, nugget, GPS 리듬, steel-manning 추가
3. **Background 확장** — 3→5 subsections (Forgetting Problem, Memory Security 신설)
4. **Related Work 확장** — 4→7 categories (Knowledge Editing, Graph Unlearning, Memory Attacks 신설)
5. **Abstract 수정** — 수치 오류 수정 (68.9--79.0%), nugget 삽입
6. **Algorithm 1 기호 수정** — α→d_in (power-law α와 충돌 해소)
7. **Scale-free 언어 완화** — "exhibits" → "consistent with" (4곳)
8. **LaTeX 컴파일 확인** — 16페이지, 경고 없이 빌드 성공

---

## 남은 작업 (실험 재실행 필요)

### 실험 보강 (Important, 코드 수정 필요)
1. **Scale-free KS goodness-of-fit test** — Clauset et al. (2009) 절차 준수, log-normal 비교
2. **통계 분석 보강** — 풀링 정당화 또는 mixed-effects model, 음수 damage 설명
3. **Graph construction 상세 기술** — entity extraction, co-occurrence 정의를 Appendix에 추가

### 선택적 추가 실험 (Minor)
4. Gray-box 공격 실험 (현재 white/black만 있음)
5. Cross-task 실험 확장 (n=1 → n=5+)

---

## ⚠️ 충돌 방지
- **이 세션 범위**: `paper/` 디렉토리만
- **건드리지 말 것**: `serving_research/`, memory_module 코드 파일 (`api/`, `storage/`, `models.py` 등)
- 남은 실험 작업은 코드 파일 수정이 필요하므로 별도 세션에서 진행 권장
