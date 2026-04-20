# SCALE Workshop 논문 Revision Plan

**작성일**: 2026-04-20
**작성자**: Claude Opus 4.6 (세션 B)
**마감**: 2026-04-24 AoE
**대상**: `paper/workshop.tex` — "Collateral Damage in Graph-based Memory Forgetting"
**현재 상태**: 8페이지 (appendix/references 제외), 컴파일 가능, bib placeholder 미수정
**목표**: 리뷰어 피드백 기반 revision → SCALE 제출 품질 달성

---

## 0. 진단 요약

외부 리뷰 피드백에서 핵심 문제 3가지를 식별:

| 계층 | 문제 | 심각도 | 수정 난이도 |
|------|------|--------|------------|
| **Trust Breaker** | 템플릿 에러, bib 오류, Algorithm 버그 | CRITICAL | 쉬움 |
| **Overclaiming** | "causal chain" 과장, "destroys" 오용, straw man 방어 약함 | HIGH | 중간 |
| **Clarity** | 메트릭 미정의, 수치 불일치, 시나리오 예시 부재 | MEDIUM | 중간 |

**핵심 판단**: 아이디어는 SCALE에 적합. 문제는 표현과 정밀도. "좋은 논문을 나쁘게 쓴 것"이므로 revision으로 해결 가능.

---

## 1. Phase A — Trust Breakers 제거 (최우선, ~30분)

신뢰를 파괴하는 요소를 먼저 제거한다. 리뷰어가 기술 내용에 도달하기 전에 이탈하는 것을 방지.

### A1. ICML 템플릿 AUTHORERR 해결
- **위치**: `workshop.tex` line 39-47
- **문제**: `\icmlauthor{Anonymous}{}`에 `\icmlaffiliation`, `\icmlcorrespondingauthor` 누락 → PDF에 AUTHORERR 출력
- **수정**: anonymous affiliation 추가
```latex
\icmlaffiliation{anon}{Anonymous Institution}
\icmlauthor{Anonymous}{anon}
\icmlcorrespondingauthor{Anonymous}{anonymous@example.com}
```
- **검증**: `latexmk -pdf workshop.tex` → PDF 1페이지에 에러 메시지 없음 확인

### A2. `\printAffiliationsAndNotice` footnote 제거
- **위치**: line 47
- **문제**: "Preliminary work. Under review by ICML" footnote가 workshop 제출에 부적절
- **수정**: `\printAffiliationsAndNotice{}` 유지하되, ICML 템플릿의 notice 출력 동작 확인 후 필요시 빈 문자열로 override

### A3. Algorithm 1 버그 수정
- **위치**: line 305, 314-315
- **문제 1**: `h` (현재 depth)가 함수 시그니처에 없음 → line 314 `\IF{$h < D$}`에서 미정의 변수 사용
- **문제 2**: `\textsc{Propagate}` — `\textsc`는 LaTeX에 없는 명령어 (올바른 것은 `\textsc` → `\textbf` 또는 `\Call`)
- **수정**:
  - REQUIRE에 `, h=0` 추가
  - `\textsc{Propagate}` → `\textbf{Propagate}` 또는 `\textsc` → `\Call` (algorithmic 패키지 호환)

### A4. references.bib placeholder 저자 (사용자 직접 수정)
- **위치**: `references.bib` line 368 `{KEPo Authors}`, line 377 `{LogicPoison Authors}`
- **상태**: 사용자가 직접 arXiv에서 확인 후 수정 예정
- **추가 확인 대상**: MemoryAgentBench, Mem0 저자 정보 정확성

---

## 2. Phase B — Overclaiming 완화 (핵심, ~40분)

실험 범위를 넘는 주장을 실험이 지지하는 수준으로 낮춘다. 이것이 Accept/Reject를 가르는 핵심 영역.

### B1. "causal chain" → "attribute-directed dependency chain" 일괄 교체

Algorithm 1은 subject-key/object-entity 매칭 heuristic이다. causal inference나 학습이 아니므로 "causal"은 과장.

| 위치 | 현재 | 변경 |
|------|------|------|
| Abstract (line 57) | `restricts cascades to genuine causal chains` | `restricts cascades to attribute-directed dependency chains` |
| Contribution 3 (line 89) | `Causal-chain filtering achieves` | `Attribute-directed filtering achieves` |
| Section 6 Method (line 299) | `restricts propagation to genuine downstream dependencies` | `restricts propagation to attribute-directed downstream dependencies` |
| Section 6 설명 (line 321) | `restricting propagation to downstream causal chains` | `restricting propagation to downstream attribute-directed chains` |
| Discussion (line 395) | `by enforcing causal-chain filtering` | `by enforcing attribute-directed filtering` |
| Discussion (line 397) | `propagation must follow causal dependency` | `propagation must follow attribute-level dependency` |
| line 92 | `causal-dependency-aware propagation` | `dependency-aware propagation` |
| line 58 | `causal-dependency filtering is essential` | `dependency-aware filtering is essential` |

**주의**: "causal"을 완전히 삭제하는 것이 아니라, "causal"은 Kumiho 등 formal system을 지칭할 때만 유지하고, 우리 method를 지칭할 때는 "attribute-directed"로 교체.

### B2. "destroys" → "degrades" 용어 수정

| 위치 | 현재 | 변경 |
|------|------|------|
| Finding 4 (line 264) | `A single fake fact destroys 5.2%` | `A single fake fact degrades 5.2%` |
| Finding 2 (line 206) | `destroyed memories scales linearly` | `damaged memories scales linearly` |

### B3. Finding 2 수치 불일치 해결
- **문제**: `143→1,179→2,465 complete losses`라고 하지만 Table 3에 Kill 컬럼이 없어서 검증 불가
- **옵션 A**: Table 3에 Kill 컬럼 추가 (투명성 극대화)
- **옵션 B**: Finding 2에서 Kill 절대 수치를 삭제하고 percentage만 유지
- **권장**: 옵션 B — 7페이지 제한에서 테이블 컬럼 추가는 공간 부담. "BFS damage ranges from 69--79\%, scaling linearly with memory size." 정도로 축약

### B4. Abstract "no LLM overhead" 범위 명시
- **위치**: line 57
- **현재**: `with no LLM overhead`
- **변경**: `with no LLM calls during propagation`
- **이유**: conflict detection에서 Gemma-4-31B-it를 사용하므로 "no LLM overhead" 전체는 거짓

### B5. Discussion 톤 완화

| 위치 | 현재 | 변경 |
|------|------|------|
| line 393 | `establish memory graph exploitation as a distinct attack surface` | `identify memory graph propagation as a potential attack surface` |
| line 401 | `Any system adopting graph-based propagation will be vulnerable` | `Systems adopting graph-based propagation may be vulnerable` |

### B6. Table 1 caption 관찰문으로 전환
- **위치**: line 118
- **현재**: `None propagate invalidation through entity connections.`
- **변경**: `We found no explicit invalidation propagation in their published descriptions.`

---

## 3. Phase C — Straw Man 방어 강화 (~15분)

"아무도 구현 안 한 BFS를 왜 공격하느냐"는 가장 날카로운 리뷰어 질문. 선제 방어 필요.

### C1. Section 4 Setup에 실험 범위 명시
- **위치**: line 185 뒤
- **추가**: 
```
BFS propagation is not implemented in any current production system; 
we simulate it as a stress test for a plausible design choice that 
existing graph prerequisites make architecturally straightforward.
```
- **효과**: "우리도 BFS가 실제 배포가 아님을 알고 있다"를 명시 → straw man 비판 선제 방어

### C2. Contribution 1번 범위 제한
- **위치**: line 85
- **현재**: `BFS propagation decays 69--79\% of valid memories`
- **변경**: `Under simulated BFS propagation on co-occurrence graphs, 69--79\% of valid memories are damaged`

---

## 4. Phase D — Clarity 개선 (~30분)

리뷰어가 계산해보고 혼란을 느끼는 지점을 선제 해소.

### D1. Metric 정의 추가
- **위치**: line 186 뒤 (Section 4 Setup)
- **추가**:
```
We define \textit{damage} as any memory weight decay ($w < 1.0$), 
\textit{kill} as weight below retrieval threshold ($w < 0.1$), 
and \textit{stale} as facts that should have been invalidated but remain unchanged.
```
- **효과**: 이후 모든 수치가 자명해짐

### D2. Section 3 시나리오 예시 추가
- **위치**: line 150 뒤
- **추가**:
```
For instance, updating ``the CEO of Acme is Alice'' should invalidate 
``Alice's direct reports include Bob'' (dependent) but not ``Acme was founded in 2010'' 
(co-occurring but independent).
```
- **효과**: 리뷰어가 10 scenarios의 구조를 즉시 이해

### D3. Black-box 해석 범위 좁히기
- **위치**: line 283
- **현재**: `Black-box attacks fail entirely (0\% hit rate), establishing that hub exploitation requires architectural knowledge`
- **변경**: `Naive random-entity black-box attacks fail (0\% hit rate); more sophisticated strategies targeting common or high-frequency entities remain unexplored, establishing that \textit{at minimum} gray-box knowledge is needed for the attack vector studied here`

### D4. Threat Model에 공격 경로 명시
- **위치**: line 239 뒤
- **추가**:
```
The attacker injects facts through the system's normal memory write interface. 
Conflict detection triggers when a new fact maps to an existing subject-key, 
initiating the propagation cascade under study.
```

### D5. Table caption 실험 구분 명시
- **문제**: Table 2 (forgetting) Attr=25% vs Table 3 (scale) Attr=15% — 다른 실험인데 리뷰어가 불일치로 오해
- **수정**: 
  - Table 2 caption에 `(controlled 10-scenario evaluation)` 추가
  - Table 3 caption에 `(full MemoryAgentBench FactConsolidation)` 추가

---

## 5. Phase E — SCALE Fit 강화 (선택, ~15분)

SCALE의 "efficient multimodal AI agents" 테마에 대한 연결고리 보강.

### E1. Efficiency 수치 명시
- **위치**: line 324 근처
- **추가**: `Graph traversal adds $<$10ms per invalidation step; the full \attraware{} pipeline processes 64K-scale graphs in $<$1s without GPU.`
- **효과**: SCALE의 "efficient" 키워드에 직접 연결

### E2. Limitation에 graph construction artifact 추가
- **위치**: line 416 뒤
- **추가**: `(5) Co-occurrence clique construction may amplify hub degrees compared to alternative graph topologies; clique vs.\ pairwise edge formation is an important ablation.`
- **효과**: 리뷰어가 지적할 약점을 선제 인정 → 신뢰도 상승

### E3. Multimodal 연결 (이미 존재, 확인만)
- line 67: multimodal agent architectures 언급 ✅
- line 421: multimodal memory graphs future work ✅
- 추가 수정 불필요

---

## 6. Phase F — 수정하지 않는 것 (명시적 비수정 목록)

리뷰어가 지적했지만 현실적으로 마감 전 해결 불가하거나, 현재 상태로 충분한 항목.

| 항목 | 리뷰어 지적 | 비수정 이유 |
|------|------------|------------|
| 2nd benchmark 추가 | 단일 벤치마크 일반화 한계 | 실험 재실행 불가 (마감 4일). Zipf 논증 + Limitations 명시로 대응 |
| 2nd LLM 실험 | Gemma만 사용 | GPU 실험 필요. entity extraction이 rule-based임을 강조 |
| Graph construction ablation | clique vs pairwise | 새 실험 필요. Limitation E2에서 인정 |
| Attr-Aware 15% residual 분류 | TP/FP 미구분 | 이미 Limitation (3)에 명시 |
| CI for 32K/64K | confidence interval 없음 | 추가 실험 필요. Appendix B에서 6K CI는 보고 |
| Contribution 5개 재구조화 | 리뷰어 제안 | 현재 3개가 7페이지에 더 적합. 5개는 과함 |
| Formal metric definitions (full) | damage/kill/stale 외 추가 | D1에서 핵심 3개만 정의. 나머지는 self-evident |
| "semantic network research (??)" | placeholder 지적 | 현재 소스에서 정상 인용 (`\citep{steyvers_semantic_2005}`). 리뷰어가 본 PDF가 컴파일 불완전 |

---

## 7. 실행 순서 및 타임라인

```
Phase A (Trust Breakers)     ████░░░░░░  30min   ← 반드시 먼저
Phase B (Overclaiming)       ██████░░░░  40min   ← 핵심
Phase C (Straw Man)          ███░░░░░░░  15min
Phase D (Clarity)            █████░░░░░  30min
Phase E (SCALE Fit)          ███░░░░░░░  15min   ← 선택
─────────────────────────────────────────────────
총 예상 작업 시간:           약 2시간 10분
```

### 의존성
```
A1 ─┐
A2 ─┤
A3 ─┼─→ 컴파일 확인 ─→ B1~B6 (병렬 가능) ─→ C1~C2 ─→ D1~D5 ─→ E1~E2 ─→ 최종 컴파일
A4 ─┘ (사용자)
```

### 분량 영향 추정
- 삭제/축소: Finding 2 Kill 수치 삭제 (−1줄)
- 추가: D1 메트릭 정의 (+2줄), D2 예시 (+2줄), C1 범위 명시 (+2줄), D4 공격 경로 (+2줄), E1 효율 (+1줄), E2 limitation (+1줄)
- **순 증가: ~9줄** → 현재 8페이지 내 소화 가능 (여유 있음)

---

## 8. 검증 체크리스트

수정 완료 후 최종 확인:

- [ ] `latexmk -pdf workshop.tex` 에러 0, 워닝 확인
- [ ] PDF 1페이지에 AUTHORERR 없음
- [ ] "causal chain" 검색 → 우리 method 지칭 시 0건 (Kumiho 지칭만 허용)
- [ ] "destroys" 검색 → 0건
- [ ] Algorithm 1에서 `h` 정의 확인
- [ ] Table 2, 3 caption에 실험 구분 명시
- [ ] Finding 2에 검증 불가능한 절대 수치 없음
- [ ] Black-box 해석이 "불가능"이 아닌 "naive 접근 실패"
- [ ] bib에 placeholder 저자 없음 (사용자 확인)
- [ ] 8페이지 이내 확인

---

## 9. FMAI 이중 제출 전략 (참고)

SCALE 제출 후 동일 실험으로 FMAI (Failure Modes in Agentic AI) 제출 가능:
- **마감**: 2026-05-08 (SCALE 후 2주)
- **분량**: 8페이지
- **프레이밍 차이**: SCALE = "agentic memory forgetting", FMAI = "failure mode diagnosis + repair"
- **수정 범위**: Introduction/Discussion 재작성, 나머지 동일
- 둘 다 non-archival + dual submission 허용 → 리스크 제로

---

## 10. 리뷰어 피드백 중 수용/비수용 판단 근거

### 수용한 지적 (Phase A~E에 반영)

1. **AUTHORERR** — 사실. PDF에 보이면 즉시 감점
2. **"causal chain" 과장** — 정당. Algorithm 1은 heuristic이지 causal inference 아님
3. **"destroys" 오용** — 정당. Kill 0.3%인데 destroys라 하면 5.2% 전체가 파괴된 것처럼 읽힘
4. **Finding 2 수치 불일치** — 정당. Kill 컬럼 없이 Kill 수치를 인용하면 검증 불가
5. **BFS straw man** — 부분 수용. 선제 방어 문구 추가하되, 논문 전체 프레이밍은 유지
6. **Black-box 과잉 해석** — 정당. "불가능"이 아니라 "naive baseline 실패"
7. **메트릭 정의 부재** — 정당. damage/kill/stale 구분이 본문에 없으면 혼란
8. **Table caption 구분** — 정당. 25% vs 15% 차이가 설명 없으면 불일치로 보임
9. **"no LLM overhead" 범위** — 정당. conflict detection에서 LLM 사용하므로 전체는 거짓

### 비수용한 지적 (과잉 해석 또는 마감 내 불가)

1. **Contribution 5개 재구조화** — 7페이지에 5개는 과함. 현재 3개가 더 응집력 있음
2. **"semantic network research (??)"** — 현재 소스에서 정상 인용. 리뷰어 측 컴파일 문제
3. **"no LLM overhead" → 완전 삭제** — 과잉. "during propagation" 범위 명시로 충분
4. **2nd benchmark/LLM 추가** — 마감 내 불가. Limitations에서 인정
5. **Graph construction ablation** — 새 실험 필요. Future work
6. **Attr-Aware recall/precision 측정** — 유효한 지적이지만 마감 내 불가

---

*이 문서는 세션 B (Claude Opus 4.6)의 revision 판단입니다. 다른 세션 agent의 계획과 비교하여 최종 수정 방향을 결정하세요.*
