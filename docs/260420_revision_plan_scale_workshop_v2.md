# SCALE Workshop 논문 Revision Plan v2 (통합)

**작성일**: 2026-04-20
**작성자**: Claude Opus 4.6 (세션 B, 리뷰 2건 통합)
**마감**: 2026-04-24 AoE
**대상**: `paper/workshop.tex` — "Collateral Damage in Graph-based Memory Forgetting"
**현재 상태**: 본문 6페이지 + appendix (7페이지 제한, ref/appendix 제외)
**입력**: 외부 리뷰 A (첫 번째 피드백) + 외부 리뷰 B (두 번째 피드백, 세션 간 비교용)

---

## 0. 두 리뷰 비교 분석

### 일치하는 지적 (확정 수정)

| 항목 | 리뷰 A | 리뷰 B | 판정 |
|------|--------|--------|------|
| "causal chain" 과장 | "attribute-keyed directional heuristic"으로 | "attribute-keyed directionality as conservative proxy" | **수정 확정** — 둘 다 같은 방향 |
| "destroys" → "degrades" | 명시 | 명시 | **수정 확정** |
| "no LLM overhead" → "during propagation" | 명시 | 명시 | **수정 확정** |
| Table 1 caption 관찰문 전환 | "we found no explicit..." | "published descriptions do not specify..." | **수정 확정** |
| Black-box 해석 범위 좁히기 | "naive random-entity baseline" | "under our random-entity black-box baseline" | **수정 확정** |
| Algorithm 1 `h` 미초기화 | REQUIRE에 h=0 추가 | 전체 재작성 제안 | **수정 확정** (방식은 아래 결정) |
| Metric 정의 필요 | damage/kill/stale 3개 | +stale retention, retrieval degradation, attack amplification = 5개 | **수정 확정** (범위는 아래 결정) |
| Section 3 시나리오 예시 | CEO/Acme 예시 | Alice/Orion 예시 | **수정 확정** |
| AUTHORERR 템플릿 | 명시 | 명시 | **수정 확정** |
| Straw man 선제 방어 | "simulate as stress test" 문구 추가 | "natural design extension" 프레이밍 | **수정 확정** |
| Limitation 보강 | graph construction artifact | clique stress-test + BFS not deployed | **수정 확정** |

### 의견이 갈리는 부분

| 항목 | 내 기존 계획 (v1) | 리뷰 B 제안 | 내 판단 |
|------|-------------------|-------------|---------|
| **Contribution 수** | 3개 유지 | 4개로 확장 | **4개 채택** — 리뷰 B의 4개 구조가 더 설득력 있음 (아래 상세) |
| **Abstract** | 타겟 수정 (3곳) | 전체 재작성 | **전체 재작성 채택** — 리뷰 B의 abstract가 객관적으로 더 안전하고 정확 |
| **Section 구조** | 현재 유지 + 문구 수정 | "Problem Setup" 섹션 신설 | **부분 채택** — 별도 섹션 신설은 분량 부담. Section 4 Setup에 정의 통합 |
| **Section 5 제목** | "Adversarial Hub Exploitation" 유지 | "Hub-Targeted Amplification"으로 변경 | **채택** — "exploitation"은 보안 논문 톤. "amplification"이 stress-test 프레이밍에 맞음 |
| **Cross-task 위치** | 현재 위치 유지 (4.4) | 더 전면 배치 | **부분 채택** — 위치는 유지하되 Introduction에서 더 강조 |
| **Algorithm 재작성** | 최소 수정 (h 추가, textsc 수정) | queue-based 전체 재작성 | **최소 수정 유지** — 마감 4일에 Algorithm 전체 재작성은 위험. 핵심 버그만 수정 |
| **Metric 정의 수** | 3개 (damage, kill, stale) | 5개 (+retrieval degradation, attack amplification) | **3+1 채택** — damage, kill, stale + retrieval degradation. attack amplification은 self-evident |
| **Multimodal 연결** | 기존 문구 유지 (이미 수정됨) | Discussion에 별도 paragraph | **리뷰 B 문구 채택** — 더 안전하고 정확한 표현 |

---

## 1. 핵심 프레이밍 전환 (가장 중요한 변경)

### Before (현재)
> "실제 시스템 취약점 폭로" 톤
> - "establish memory graph exploitation as a distinct attack surface"
> - "restricts cascades to genuine causal chains"
> - "A single fake fact destroys 38.1%"

### After (목표)
> "자연스럽지만 위험한 설계 선택을 stress-test하고, failure mode와 mitigation을 제시"
> - "identify memory graph propagation as a potential failure mode"
> - "uses attribute-keyed directionality as a conservative proxy for dependency"
> - "A single fake fact degrades 38.1%"

이 전환은 단순 단어 교체가 아니라 **논문 전체의 voice**를 바꾸는 것. Abstract, Introduction, Discussion 모두 이 톤에 맞춰야 함.

---

## 2. Phase A — Trust Breakers 제거 (~30분)

### A1. ICML 템플릿 AUTHORERR 해결
- **위치**: line 39-47
- **수정**: anonymous affiliation + corresponding author 추가
```latex
\icmlaffiliation{anon}{Anonymous Institution}
\icmlauthor{Anonymous}{anon}
\icmlcorrespondingauthor{Anonymous}{anonymous@example.com}
```

### A2. `\printAffiliationsAndNotice` footnote 확인
- "Preliminary work. Under review by ICML" 출력 여부 확인 → 부적절하면 제거

### A3. Algorithm 1 버그 수정
- REQUIRE에 `$h{=}0$` (initial depth) 추가
- `\textsc{Propagate}` → `\textbf{Propagate}` (LaTeX 명령어 오류)
- 전체 재작성은 하지 않음 — 마감 리스크 > 개선 효과

### A4. references.bib (사용자 직접 수정)
- `{KEPo Authors}`, `{LogicPoison Authors}` placeholder
- MemoryAgentBench, Mem0, Zep 저자 정보 확인

---

## 3. Phase B — Abstract 재작성 (~20분)

리뷰 B의 abstract를 기반으로 재작성. 현재 abstract의 3가지 위험 (causal chain, attacker exploiting, no LLM overhead)을 모두 해소.

### 현재 Abstract (위험 요소 표시)
```
AI memory systems maintain entity graphs for retrieval but handle 
invalidation individually...
[⚠️] restricts cascades to genuine causal chains
[⚠️] An attacker exploiting this mechanism
[⚠️] with no LLM overhead
```

### 목표 Abstract (리뷰 B 기반, 조정)
```
Agent memory systems increasingly use entity graphs for retrieval and 
consolidation, but invalidation is handled at the level of individual 
facts—leaving dependent facts silently stale. Propagating invalidation 
through graph edges is a natural way to maintain consistency, yet 
co-occurrence edges do not encode dependency. We study this design 
choice by implementing BFS invalidation propagation over co-occurrence 
graphs derived from MemoryAgentBench. Across 6K–64K turns, BFS 
propagation reduces stale retention but decays 69–79% of valid memories 
and degrades cross-task retrieval F1 by 10.1pp. Hub-targeted 
invalidations amplify this failure: five injected facts degrade 57.3% 
of valid memories under white-box access. To mitigate over-propagation, 
we propose ATTR-AWARE propagation, a lightweight attribute-keyed 
directional filter that limits cascades to plausible dependency paths 
without LLM calls during propagation, achieving 78–100% defense 
effectiveness. Our results show that graph-based memory forgetting 
requires dependency-aware propagation rather than raw co-occurrence 
traversal.
```

**변경 포인트**:
- "genuine causal chains" → "plausible dependency paths"
- "attacker exploiting" → "hub-targeted invalidations amplify"
- "no LLM overhead" → "without LLM calls during propagation"
- "MemoryAgentBench" 명시 → controlled study임을 분명히
- cross-task F1 결과를 abstract에 포함 (strongest evidence 강조)

---

## 4. Phase C — Contribution 재구조화 (~15분)

### 현재 (3개, 숫자 중심)
```
1. Damage quantification: BFS propagation decays 69–79%...
2. Adversarial exploitation: 5 injected facts...
3. ATTR-AWARE defense: Causal-chain filtering achieves...
```

### 목표 (4개, 구조 중심)
```
1. Failure formulation: invalidation propagation as a retention-forgetting 
   trade-off in graph-based agent memory.
2. Controlled quantification: on MemoryAgentBench-derived co-occurrence 
   graphs, naive BFS propagation decays 69–79% of valid memories across 
   6K–64K scales and degrades unrelated retrieval.
3. Hub amplification analysis: high-degree entities amplify invalidation 
   damage under gray/white-box knowledge, turning memory maintenance 
   into a potential attack surface.
4. Lightweight mitigation: ATTR-AWARE propagation, an attribute-keyed 
   directional filter that reduces collateral damage without LLM calls 
   during propagation.
```

**왜 4개가 더 나은가**:
- Contribution 1이 "문제 정의" 자체를 claim → 리뷰어가 "이 문제를 처음 formalize했다"를 인정하기 쉬움
- "Controlled quantification"이 실험 범위를 명시 → straw man 비판 선제 방어
- "Hub amplification"이 "adversarial exploitation"보다 정확 — stress-test 프레이밍에 맞음
- "Lightweight"가 SCALE의 efficiency 테마에 연결

---

## 5. Phase D — Overclaiming 완화 (~30분)

### D1. "causal" 용어 일괄 교체

**원칙**: "causal"은 Kumiho/AGM 등 formal system을 지칭할 때만 유지. 우리 method에는 사용 금지.

| 위치 | 현재 | 변경 |
|------|------|------|
| Abstract (전체 재작성으로 해결) | — | — |
| Contribution 3 (재구조화로 해결) | — | — |
| line 92 결론문 | `causal-dependency-aware propagation` | `dependency-aware propagation` |
| line 58 Abstract 마지막 | `causal-dependency filtering is essential` | `dependency-aware filtering is essential` |
| line 185 Setup | `downstream causal chains only` | `attribute-directed chains only` |
| line 299 Method 소개 | `restricts propagation to genuine downstream dependencies` | `restricts propagation to attribute-directed downstream dependencies` |
| line 321 설명문 | `downstream causal chains` | `downstream attribute-directed chains` |
| line 395 Discussion | `causal-chain filtering` | `attribute-directed filtering` |
| line 397 원칙문 | `causal dependency` | `attribute-level dependency` |
| line 404 guardrail 문장 | `to causal chains` | `to plausible dependency chains` |

### D2. "destroys" / "destroyed" 교체

| 위치 | 현재 | 변경 |
|------|------|------|
| Finding 4 (line 264) | `destroys 5.2%` | `degrades 5.2%` |
| Finding 2 (line 206) | `destroyed memories` | `damaged memories` |

### D3. Finding 2 수치 불일치 해결
- **문제**: `143→1,179→2,465 complete losses`가 Table 3에서 검증 불가 (Kill 컬럼 없음)
- **해결**: Kill 절대 수치 삭제, percentage만 유지
- **변경**: `"BFS damage ranges from 69–79\%, with absolute damage counts scaling linearly with memory size."`

### D4. "no LLM overhead" 범위 명시
- Abstract에서 해결 (Phase B)
- line 324: 이미 "no LLM calls at propagation time" → OK
- line 395: `no LLM overhead` → `no LLM calls during propagation`

### D5. Discussion 톤 완화

| 위치 | 현재 | 변경 |
|------|------|------|
| line 393 | `establish memory graph exploitation as a distinct attack surface` | `identify memory graph propagation as a potential failure mode that creates an attack surface` |
| line 401 | `Any system adopting...will be vulnerable` | `Systems adopting...may be vulnerable` |

### D6. Table 1 caption
- **현재**: `None propagate invalidation through entity connections.`
- **변경**: `We found no explicit invalidation propagation in their published descriptions.`

### D7. Section 5 제목 변경
- **현재**: `Adversarial Hub Exploitation`
- **변경**: `Hub-Targeted Amplification`
- **이유**: "exploitation"은 보안 논문 톤. "amplification"이 stress-test 프레이밍에 맞고, 실험 내용도 정확히 기술 (hub의 degree가 damage를 amplify)

### D8. Finding 5 Black-box 해석 완화
- **현재**: `Black-box attacks fail entirely (0\% hit rate), establishing that hub exploitation requires architectural knowledge of graph structure`
- **변경**: `Under our random-entity black-box baseline, attacks fail to hit hub entities (0\% hit rate). More sophisticated strategies targeting high-frequency entities remain unexplored; our results establish that \textit{at minimum} gray-box knowledge of graph structure is needed for the attack vector studied here.`

---

## 6. Phase E — Clarity 개선 (~30분)

### E1. Metric 정의 추가 (Section 4 Setup, line 186 뒤)

```latex
We define four metrics:
\textit{damage}---any memory weight reduction ($w < 1.0$) from propagation;
\textit{kill}---weight below retrieval threshold ($w < 0.1$);
\textit{stale retention}---outdated facts that should have been invalidated 
but remain unchanged;
\textit{retrieval degradation}---EM or F1 decrease on unrelated downstream tasks.
```

4개 정의: damage, kill, stale retention, retrieval degradation.
attack amplification은 별도 정의 불필요 (injected facts 대비 damage ratio로 자명).

### E2. Section 3 시나리오 예시 (line 150 뒤)

```latex
For instance, updating ``the CEO of Acme is Alice'' to ``the CEO of Acme is Bob'' 
should invalidate ``Alice approves Acme milestones'' (dependent) but not 
``Acme was founded in 2010'' (co-occurring but independent).
```

### E3. Straw man 선제 방어 (Section 4 Setup, line 185 뒤)

```latex
BFS propagation is not deployed in any current production system; we implement 
it as a stress test of a plausible design choice that existing graph prerequisites 
make architecturally straightforward. Our results should be interpreted as 
characterizing this design choice, not as a claim about current system behavior.
```

두 문장으로 straw man 비판을 완전 차단. 리뷰 B의 제안 + 내 기존 계획 통합.

### E4. Threat Model 공격 경로 명시 (line 239 뒤)

```latex
The attacker injects facts through the system's normal memory write interface. 
Conflict detection triggers when a new fact maps to an existing subject-key, 
initiating the propagation cascade under study.
```

### E5. Table caption 실험 구분

| Table | 추가 문구 |
|-------|----------|
| Table 2 (forgetting) | `(controlled 10-scenario evaluation)` |
| Table 3 (scale) | `(full MemoryAgentBench FactConsolidation)` |

### E6. Contribution 1 범위 명시
- **현재**: `BFS propagation decays 69–79% of valid memories`
- **변경**: Phase C의 4-contribution 구조로 해결 — "on MemoryAgentBench-derived co-occurrence graphs" 명시

### E7. ATTR-AWARE collateral 25% 솔직한 표현
- Table 2 Finding 1 (line 174): `reducing collateral damage by half` → `reducing collateral damage, though 25\% residual collateral indicates room for improvement`

---

## 7. Phase F — SCALE Fit 강화 (~15분)

### F1. Efficiency 수치 명시 (line 324 근처)
```latex
Graph traversal adds $<$10\,ms per invalidation step; the full \attraware{} 
pipeline processes 64K-scale graphs in $<$1\,s without GPU.
```

### F2. Limitation 보강 (2개 추가, line 416 뒤)

```latex
(5) Co-occurrence clique construction may amplify hub degrees compared to 
alternative graph topologies; this should be interpreted as a stress-test setting.
(6) No current deployed memory system implements the BFS invalidation policy 
evaluated here; we evaluate a natural design extension that may arise as 
systems seek consistency beyond per-fact updates.
```

리뷰 B가 강력 권장한 2문장. 논문을 약하게 만드는 것이 아니라 리뷰어 공격 포인트를 선제 차단.

### F3. Multimodal 연결 (Discussion, 리뷰 B 문구 채택)

현재 line 421 (Future work 3번)을 교체:

```latex
(3) Although our experiments use text-derived fact graphs, the underlying 
issue is not text-specific: multimodal agents increasingly maintain episodic, 
semantic, and visual memories that share entity references, and the same 
co-occurrence-versus-dependency distinction arises when updates in one 
modality should or should not invalidate entries in another.
```

기존 "visual scene graphs" 문구보다 더 안전하고 정확. WorldMM 같은 검증 안 된 인용을 피하면서도 multimodal 연결을 만듦.

---

## 8. Phase G — 수정하지 않는 것 (명시적 비수정)

| 항목 | 두 리뷰 모두 지적 | 비수정 이유 |
|------|------------------|------------|
| 2nd benchmark | O | 마감 내 불가. Zipf 논증 + Limitation (1) |
| 2nd LLM | O | GPU 실험 필요. rule-based extraction 강조 |
| Graph construction ablation | O | 새 실험 필요. Limitation (5)에서 인정 |
| Attr-Aware 15% residual 분류 | O | Limitation (3)에 명시 |
| CI for 32K/64K | 리뷰 A만 | Appendix B에서 6K CI 보고 |
| "Problem Setup" 독립 섹션 신설 | 리뷰 B만 | 분량 부담. Section 4 Setup에 정의 통합 |
| Algorithm 전체 재작성 (queue-based) | 리뷰 B만 | 마감 리스크 > 개선 효과. 핵심 버그만 수정 |
| Cross-task 위치 이동 | 리뷰 B만 | 현재 위치 유지 (4.4). Intro에서 강조로 대체 |
| 5개 contribution | 리뷰 A만 (리뷰 B는 4개) | 4개 채택. 5개는 과함 |

---

## 9. 실행 순서 및 타임라인

```
Phase A (Trust Breakers)       ████░░░░░░  30min   ← 반드시 먼저
Phase B (Abstract 재작성)      ████░░░░░░  20min   ← 핵심
Phase C (Contribution 재구조)  ███░░░░░░░  15min
Phase D (Overclaiming 완화)    █████░░░░░  30min   ← 가장 많은 수정
Phase E (Clarity 개선)         █████░░░░░  30min
Phase F (SCALE Fit)            ███░░░░░░░  15min
─────────────────────────────────────────────────────
총 예상 작업 시간:             약 2시간 20분
```

### 의존성 (변경 없음)
```
A1~A3 ─→ 컴파일 확인 ─→ B (Abstract) ─→ C (Contribution) ─→ D1~D8 ─→ E1~E7 ─→ F1~F3 ─→ 최종 컴파일
A4 (사용자, 병렬)
```

### 분량 영향
- **삭제**: Finding 2 Kill 절대수치 (−1줄), 현재 abstract 교체 (±0)
- **추가**: metric 정의 (+3줄), 시나리오 예시 (+2줄), straw man 방어 (+3줄), 공격 경로 (+2줄), limitation 2개 (+3줄), efficiency (+1줄), multimodal (+3줄), Finding 5 확장 (+2줄)
- **순 증가: ~18줄** → 현재 6페이지 → 7페이지 이내 충분히 소화 가능 (1페이지 여유)

---

## 10. 검증 체크리스트 (v2)

### 컴파일
- [ ] `latexmk -pdf workshop.tex` 에러 0
- [ ] PDF 1페이지에 AUTHORERR 없음
- [ ] 7페이지 이내 (ref/appendix 제외)

### 용어 일관성
- [ ] `grep -i "causal" workshop.tex` → 우리 method 지칭 시 0건 (Kumiho/AGM만 허용)
- [ ] `grep "destroys\|destroyed" workshop.tex` → 0건
- [ ] `grep "no LLM overhead" workshop.tex` → 0건 ("no LLM calls during propagation"만)
- [ ] `grep "exploitation" workshop.tex` → Section 제목에 0건

### 정밀도
- [ ] Finding 2에 검증 불가능한 절대 수치 없음
- [ ] Table 2/3 caption에 실험 구분 명시
- [ ] Algorithm 1에서 `h` 정의 확인
- [ ] Black-box 해석이 "naive baseline" 범위로 제한

### 프레이밍
- [ ] Abstract에 "MemoryAgentBench" 명시 (controlled study)
- [ ] Contribution에 "co-occurrence graphs" 범위 명시
- [ ] Straw man 방어 문구 존재 (Section 4 Setup)
- [ ] Limitation (5), (6) 추가됨

### bib (사용자)
- [ ] placeholder 저자 없음
- [ ] MemoryAgentBench/Mem0/Zep 저자 정확

---

## 11. v1 대비 v2 변경 요약

| 항목 | v1 | v2 | 변경 이유 |
|------|-----|-----|----------|
| Abstract | 3곳 타겟 수정 | 전체 재작성 | 리뷰 B의 abstract가 더 안전하고 일관적 |
| Contribution | 3개 유지 | 4개로 확장 | "failure formulation" 자체가 contribution이라는 리뷰 B 논리에 동의 |
| Section 5 제목 | "Adversarial Hub Exploitation" | "Hub-Targeted Amplification" | stress-test 프레이밍에 맞는 제목 |
| Metric 정의 | 3개 | 4개 (+retrieval degradation) | cross-task가 strongest evidence이므로 정의 필요 |
| Limitation | 1개 추가 (graph artifact) | 2개 추가 (+BFS not deployed) | straw man 선제 방어 강화 |
| Multimodal 문구 | 기존 유지 | 리뷰 B 문구 교체 | 더 안전하고 정확 |
| Finding 5 | 범위 좁히기만 | 범위 좁히기 + 미탐색 영역 명시 | 정직한 한계 인정 |
| 총 수정 항목 | 23개 | 28개 | 5개 추가 (Abstract, Contribution, Section 제목, Limitation, Multimodal) |

---

## 12. FMAI 이중 제출 전략 (유지)

두 리뷰 모두 FMAI (Failure Modes in Agentic AI, 마감 5/8)를 Plan B로 지지.
- SCALE 프레이밍: "agentic memory forgetting + stress-test + mitigation"
- FMAI 프레이밍: "failure mode diagnosis + reproducible trigger + repair"
- 같은 실험, 다른 Introduction/Discussion
- 둘 다 non-archival + dual submission 허용

---

*v2는 세션 B (Claude Opus 4.6)의 통합 판단입니다. 두 외부 리뷰의 일치 지적은 모두 수용, 의견 분기는 근거 기반으로 선택했습니다.*

---

## 13. 세션 A (별도 Claude Opus 4.6)의 교차 검증 코멘트

> 아래는 `.review/260420_revision_plan.md`를 작성한 별도 세션이 이 문서를 읽고 남긴 비교 분석 결과입니다.

### 이 문서(세션 B v2)의 강점 — 실행 기준으로 채택
- LaTeX 코드 블록이 있어서 바로 적용 가능
- 검증 체크리스트 10개 항목 포함
- Abstract 전면 재작성 결정이 맞음 (부분 수정보다 톤 일관성 확보)
- Section 5 제목 변경 ("Exploitation" → "Amplification") — stress-test 프레이밍에 일관적
- `\textsc` 버그, footnote 확인, 공격 경로 문장, efficiency 수치 등 추가 발견

### 보완이 필요한 점
1. **시간 추정 2h 20min은 과소**. bib WebSearch 검증(1-2h) + Abstract/Contribution 재작성 후 톤 일관성 확인(1h) 감안하면 **현실적으로 5-7시간**.
2. **bib 검증을 "사용자 직접 수정"으로 돌렸는데**, 다음 세션에서 WebSearch로 직접 확인하는 게 더 효율적. 특히 MemoryAgentBench 저자(Huang vs Hu)와 Mem0 저자는 인용이 본문 곳곳에 영향을 미침.
3. **Finding 1 (174줄)**: "reducing collateral damage by half"를 "reducing collateral damage, though 25% residual indicates room for improvement"로 바꾸는 게 더 솔직. 이 문서 E7에서 제안했지만 강조가 약함.
4. **Phase D1의 "causal" 교체 시 주의**: Kumiho/AGM 맥락에서 "causal"은 유지해야 함. `grep -i "causal" workshop.tex` 후 하나씩 판단 필요 — 일괄 치환하면 안 됨.

### 판단이 일치한 항목 (높은 신뢰도로 수정 확정)
두 세션이 독립적으로 같은 결론에 도달한 것:
- "genuine causal" → "attribute-directed/keyed" 계열로 완화
- "destroys" → "degrades"
- Algorithm h 초기화
- "no LLM overhead" → "no LLM calls during propagation"
- Black-box "fail entirely" → "under random-entity baseline"
- Metric 정의 4개 추가
- Straw man 방어 문장 2개
- Limitation (5)(6) 추가
- Contribution 4개 구조
- Finding 2 Kill 절대수치 제거

### 절대 하지 말 것 (두 세션 공통)
- Section 구조 전면 재편
- Algorithm queue-based 전체 재작성
- 새 실험 추가
- "causal" 완전 삭제 (Kumiho/AGM 맥락 유지)

### 상세 비교는 `.review/260420_revision_plan.md`와 `.claude/session-handoff.md` 참조
