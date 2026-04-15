# TODO: 논문 실험 보강 작업
**생성일**: 2026-04-15
**컨텍스트**: `paper/main.tex` 리뷰 후 텍스트 수정 완료. 아래는 **코드 수정 + 실험 재실행**이 필요한 남은 작업.
**참고 파일**: `.review/2026-04-10-full-paper-review.md` (전체 리뷰 리포트)

---

## 1. [Critical] Scale-free KS Goodness-of-Fit Test

**문제**: 현재 power-law exponent α를 MLE로 추정만 했고, Clauset et al. (2009) 모범사례를 따르지 않음. 논문에서 이 논문을 인용하면서 그 방법론을 안 따르면 reviewer가 즉시 지적함.

**해야 할 것**:
1. `powerlaw` Python 패키지 사용 (`pip install powerlaw`)
2. 각 스케일(6K, 32K, 64K)의 degree distribution에 대해:
   - `k_min` 자동 추정 (KS distance 최소화)
   - Power-law fit의 KS statistic + bootstrap p-value 계산
   - Log-normal, exponential, stretched exponential과 likelihood ratio test 수행
3. 결과를 `paper/main.tex` Table 4 (`tab:topology`)에 KS stat, p-value 컬럼 추가
4. Finding 4 텍스트를 결과에 맞게 업데이트 (현재 "future validation steps"라고 적어둠 — 결과 나오면 삭제)

**관련 코드 위치**: 
- `experiments/deep_dive_analysis.py` (line 68-102): 이미 KS 근사 구현 있음 — `powerlaw` 패키지로 교체 필요
- `experiments/generate_figures.py`: degree distribution 시각화
- `analyze_results.py`, `analyze_results_v2.py`: 상위 분석 스크립트
**관련 데이터**: `experiments/results/` 디렉토리의 기존 실험 결과 JSON에서 그래프 데이터 추출

---

## 2. [Critical] 통계 분석 보강

**문제**: 
- 공격 강도별(1/3/5 facts) 결과를 풀링하여 Wilcoxon 검정 → 서로 다른 treatment level 혼합하여 n 부풀림
- 3-fact, 5-fact 개별 p-value가 비유의적 (0.169, 0.171)
- Attr-Aware의 음수 damage 값 (-0.1) 미설명

**해야 할 것**:
1. **Option A** (권장): 풀링 대신 mixed-effects model 사용
   - `statsmodels` 또는 `lme4` (R) — attack_strength를 fixed effect, run을 random effect로
   - 개별 attack strength의 underpowered 상태를 인정하되, mixed model로 전체 효과 추정
2. **Option B**: 풀링을 정당화하는 논증 추가
   - "BFS vs Attr-Aware 차이가 모든 attack strength에서 일관된 방향"임을 근거로
3. 음수 damage 값 설명: Attr-Aware에서 weight normalization 과정의 부동소수점 오차인지, 실제로 weight가 증가하는 경우가 있는지 코드 확인
4. 결과를 Appendix C 테이블 업데이트

**관련 코드 위치**: 
- `experiments/statistical_analysis.py`: Wilcoxon signed-rank, permutation test, Bonferroni 보정 이미 구현됨
- `experiments/deep_dive_analysis.py` (line 317+): multi-run 통계 분석 (t-test, Cohen's d)
- `analyze_results_v2.py`: 상위 분석 스크립트에서 통계 호출

---

## 3. [Important] Graph Construction 상세 기술

**문제**: Entity extraction, co-occurrence 정의, edge direction, window size 등이 논문에 전혀 없음. 재현성의 가장 큰 gap.

**해야 할 것**:
1. 코드에서 entity extraction 로직 확인 (`extraction.py` 또는 관련 파일)
   - Rule-based? NER? LLM-based?
   - Subject-key regex 패턴 확인
2. Co-occurrence 정의 확인
   - 같은 fact 내 동시출현? 같은 conversation turn?
   - Edge direction 규칙
   - Edge weight 할당
3. `paper/main.tex`에 Appendix D로 추가 (또는 기존 Appendix A 확장)
   - Entity extraction pipeline 설명
   - Co-occurrence 정의 + 예시
   - Subject-key regex 패턴 예시

**관련 코드 위치**: 
- `extraction.py`: entity extraction 로직
- `storage/graph_store.py`: 그래프 저장/조회, co-occurrence edge 생성 로직
- `storage/memory_index.py`, `storage/metadata_store.py`: 메모리 인덱싱
- `models.py`: Entity/Memory 데이터 모델 정의

---

## 4. [Minor] Gray-box 공격 실험

**문제**: Threat model에 black/gray/white 3단계를 정의했지만 gray-box 실험이 없음. "gray-box or higher knowledge is required"라고 주장하면서 근거 없음.

**해야 할 것**:
1. Gray-box 공격 설계: hub entity를 정확히는 모르지만, 어떤 entity가 자주 등장하는지 대략적으로 아는 공격자
   - 예: fact registry 없이 entity frequency만 아는 경우
   - 예: 상위 N개 entity 이름은 알지만 subject-key 규칙은 모르는 경우
2. 6K 스케일에서 pilot 실험 실행
3. Hit rate와 damage를 white-box(100%), black-box(0%)와 비교
4. 결과를 Table 5 (`tab:blackbox`) 확장

---

## 5. [Minor] Cross-task 실험 확장

**문제**: 현재 n=1 (Debbie 엔티티)만으로 cross-task contamination 결론. 일반화 불가.

**해야 할 것**:
1. 상위 5-10개 hub entity에서 BFS propagation 각각 실행
2. 각각의 EM/F1 변화 측정
3. 평균 + 분산 보고
4. Table 3 (`tab:cross_task`) 확장 또는 별도 테이블

---

## 6. [Important] TBD Placeholder 채우기 — Cross-task Multi-hub & Gray-box

**문제** (2차 리뷰에서 4개 에이전트가 동시 지적):
- Table 6 (`tab:cross_task_multi`): 5-hub 평균 결과 전부 TBD (L344-345)
- Table 8 (`tab:blackbox`): gray-box 행 전부 TBD (L411)
- Finding 6 (L352): TBD 값 포함 — 데이터 없이 일반화 주장
- Finding 9 (L419): gray-box 데이터 없이 "monotonic relationship" 주장

**해야 할 것**:
- Task #5 (cross-task 확장)와 Task #4 (gray-box)의 결과가 이 TBD를 채움
- **만약 실험이 불가능하면**: TBD가 포함된 Table과 Finding을 삭제하고, 기존 단일 결과만으로 논문 구성. "future work"으로 명시.
- Finding 6은 단일-hub 결과(이미 존재)만 보고하도록 축소
- Finding 9는 white-box vs black-box 이진 비교만 보고

**주의**: TBD가 남은 상태로 제출하면 즉시 reject.

---

## 7. [Minor] 3-fact 조건 통계 유의성 문제

**문제**: Wilcoxon p=0.146 (3-fact 조건)으로 비유의적이지만 다른 조건과 동등하게 취급.

**해야 할 것**:
- 3-fact 조건의 비유의성을 본문에서 명시적으로 인정 ("approaches but does not reach significance")
- 또는 mixed-effects model (Task #2)로 전체 효과를 추정하여 개별 조건의 underpowered 상태를 보완

---

## 실행 순서 권장

```
1. Graph construction 코드 분석 (#3) — 코드 파악이 #1, #2의 선행 조건
2. Scale-free KS test (#1) — 기존 데이터로 가능, 코드 추가만
3. 통계 분석 보강 (#2) + 3-fact 유의성 (#7) — 기존 데이터로 가능
4. Cross-task 확장 (#5) → Table 6 TBD 채우기 (#6) — 새 실험 필요
5. Gray-box 실험 (#4) → Table 8 TBD 채우기 (#6) — 새 실험 필요
⚠️ #4, #5 실험이 불가능하면: TBD 포함 Table/Finding 삭제 후 기존 결과로 논문 재구성
```

## 핵심 파일 맵

```
memory_module/
├── extraction.py               # entity extraction 로직
├── models.py                   # Entity/Memory 데이터 모델
├── storage/
│   ├── graph_store.py          # co-occurrence graph 구축/조회
│   ├── vector_store.py         # 벡터 저장소
│   ├── memory_index.py         # 메모리 인덱싱
│   └── metadata_store.py       # 메타데이터 저장
├── analyze_results.py          # v1 분석 스크립트
├── analyze_results_v2.py       # v2 분석 스크립트 (상위 오케스트레이션)
├── experiments/
│   ├── deep_dive_analysis.py   # KS test 근사, multi-run 통계 (수정 대상)
│   ├── statistical_analysis.py # Wilcoxon, permutation, Bonferroni (수정 대상)
│   ├── adversarial_attack.py   # 공격 실험 (gray-box 추가 대상)
│   ├── graph_forgetting.py     # BFS propagation 실험
│   ├── generate_figures.py     # 논문 figure 생성
│   └── results/                # 실험 결과 JSON (6K/32K/64K)
└── paper/
    └── main.tex                # 논문 본문
```

## 환경 참고
- Python venv: `/home/mingyu1choi/PJT/memory_module/.venv`
- 활성화: `source .venv/bin/activate`
- 주요 패키지: numpy, scipy, networkx, sklearn, matplotlib
- 추가 필요: `pip install powerlaw` (KS test용), `pip install statsmodels` (mixed-effects model용)
