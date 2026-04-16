# TODO: 논문 실험 보강 작업
**생성일**: 2026-04-15
**완료일**: 2026-04-16
**상태**: ✅ 전체 완료
**컨텍스트**: `paper/main.tex` 리뷰 후 텍스트 수정 완료. 아래 7개 작업 모두 완료됨.
**참고 파일**: `.review/2026-04-10-full-paper-review.md` (전체 리뷰 리포트)

---

## 1. [Critical] Scale-free KS Goodness-of-Fit Test — ✅ 완료 (b48fc6d)

Table 4에 KS stat, bootstrap p-value, log-normal 비교 likelihood ratio 모두 반영.
`powerlaw` 패키지 사용, Clauset et al. (2009) 방법론 준수.

---

## 2. [Critical] 통계 분석 보강 — ✅ 완료 (95d22e8)

Mixed-effects model 구현 (attack_strength = fixed, run = random intercept).
Appendix C에 테이블 + 해석 반영. 3-fact underpowered 상태 인정, 5-fact p=0.020 유의.

---

## 3. [Important] Graph Construction 상세 기술 — ✅ 완료 (b48fc6d)

Appendix D (`app:graph_construction`)에 entity extraction pipeline, co-occurrence 정의, subject-key regex 예시 반영.

---

## 4. [Minor] Gray-box 공격 실험 — ✅ 완료 (95d22e8, b48fc6d)

Gray-box 실험 결과: 100% hit rate, 20.9% damage (white-box의 52%).
Table 5 + Finding 9에 3-tier 비교 반영.

---

## 5. [Minor] Cross-task 실험 확장 — ✅ 완료 (95d22e8, 08e751c)

Top-5 hub entity에서 BFS propagation 실행.
Table 6에 5-hub 평균±std 반영. Finding 6 업데이트 완료.

---

## 6. [Important] TBD Placeholder 채우기 — ✅ 완료 (08e751c)

TBD 0개 확인. Table 6 (cross-task multi-hub), Table 5 (gray-box) 모두 실측값 반영.

---

## 7. [Minor] 3-fact 조건 통계 유의성 문제 — ✅ 완료 (#2와 함께 처리)

Mixed-effects model로 전체 효과 추정. 개별 조건의 underpowered 상태는 Appendix C에서 명시적 인정.

---

## 추가 텍스트 방어 (2026-04-16) — ✅ 완료 (08e751c, 041fc9c)

| 수정 | 커밋 |
|------|------|
| Intro "destructive baseline" 리프레이밍 | 08e751c |
| C4 복잡도 분석 (O, no LLM) | 08e751c |
| Zipf's law 일반화 근거 | 08e751c |
| Black-box 0% 리프레이밍 | 08e751c |
| `\Cref{app:graph}` 라벨 수정 + bib 누락 추가 | 041fc9c |
