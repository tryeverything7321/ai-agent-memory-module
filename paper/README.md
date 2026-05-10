# Collateral Damage in Graph-based Memory Forgetting

ICML 2026 SCALE Workshop 논문.

이 디렉토리는 root README의 "AI Agent Memory Module / Anticipatory Memory Chains" 구현 설명과 구분되는 연구 논문 작업 공간입니다. 원래 main 브랜치의 목표는 enterprise assistant용 장기 메모리 모듈 구현이었고, 이 논문은 그 구현 방향에서 한 단계 더 나아가 **graph-based memory systems가 forgetting/invalidation propagation을 도입할 때 생길 수 있는 구조적 collateral damage**를 분석합니다.

## Main Project vs. Workshop Paper

| 구분 | main / MVP 프로젝트 | SCALE workshop paper |
|------|----------------------|----------------------|
| 목표 | 사용자 업무 패턴을 기억하고 다음 컨텍스트를 선제적으로 주입하는 memory module 구현 | graph-based agent memory에서 unfiltered invalidation propagation의 구조적 위험 분석 |
| 핵심 기능/질문 | hybrid retrieval, decay, intent prediction, taxonomy evolution | co-occurrence graph에서 BFS-style propagation이 unrelated memories를 손상시키는가 |
| 그래프 사용 | retrieval, relation storage, intent transition | forgetting propagation의 failure mode와 hub-mediated blast radius 분석 |
| 주요 주장 | agent memory can be proactive and adaptive | co-occurrence is not dependency; dependency-aware propagation is needed |
| 산출물 | FastAPI service, storage/indexing modules, demo runners, tests | workshop paper, scale experiments, attack/defense analysis, ATTR-AWARE filter |

## 논문의 핵심

논문은 현재 시스템들이 naive BFS invalidation을 이미 배포했다고 주장하지 않습니다. 대신, graph-augmented memory systems가 consistency maintenance를 위해 propagation-style invalidation을 탐색할 경우, existing co-occurrence graph infrastructure 위에서 unfiltered traversal이 구조적 실패 모드를 만들 수 있음을 proactive stress test로 분석합니다.

핵심 메커니즘:

1. Agent memory systems increasingly organize facts in entity graphs.
2. Consistency maintenance makes propagation tempting when a fact changes.
3. Co-occurrence edges do not encode dependency.
4. Naive BFS propagation follows hub entities and applies nonzero decay to many unrelated valid memories.
5. ATTR-AWARE uses object-to-subject directional filtering as a lightweight dependency-aware guardrail.

실험의 큰 흐름:

- **Propagation trade-off**: no propagation은 stale memory를 남기고, BFS는 collateral damage를 만들며, ATTR-AWARE는 둘 사이의 practical compromise를 보임.
- **Scale trend**: 6K--64K MemoryAgentBench FactConsolidation에서 BFS가 valid memories의 69--79%에 nonzero decay를 적용.
- **Topology analysis**: heavy-tailed entity degree와 hub reachability가 damage를 구조적으로 설명.
- **Cross-task contamination**: named-entity hubs가 unrelated Accurate Retrieval F1을 -10.0pp / -11.9pp 낮춤.
- **Structural amplification**: hub-targeted facts가 propagation damage를 증폭할 수 있음.
- **Defense/ablation**: ATTR-AWARE와 weighted/threshold baselines를 비교하고, directional filtering이 핵심임을 보임.

더 자세한 실험별 역할과 reviewer-facing interpretation은 [`submission_logic_summary.md`](submission_logic_summary.md)를 참고하세요.

## 제출 파일

| 파일 | 용도 |
|------|------|
| `workshop_20260427.pdf` | **최종 제출본** (SCALE workshop blind PDF) |
| `workshop.tex` | blind 제출용 LaTeX source |
| `workshop_20260427.tex` | dated source snapshot |
| `workshop_v3_final.tex` | 내부 검토/동기화용 source |
| `references.bib` | 참고문헌 |

과거 파일인 `workshop.pdf`, `workshop_v3_final.pdf`, `workshop_20260428.pdf`는 이전 버전 또는 내부 검토용 산출물일 수 있습니다. 제출/공유 시에는 `workshop_20260427.pdf`를 기준으로 확인하세요.

## 버전 히스토리

| 버전 | 파일 | 설명 |
|------|------|------|
| v0 | `workshop_v0_original.tex` | 최초 제출본 |
| v1 | `workshop_v1_reviewer3_response.tex` | Reviewer 3 대응 (ablation, 인용 추가) |
| v2 | `workshop_v2_pre_reframe.tex` | n=100 업데이트 + 4-agent audit 반영 |
| **v3** | **`workshop_v3_final.tex`** | **현재 최신 (톤 리프레이밍 + direction ablation)** |

`workshop.tex`는 blind 버전으로, body는 `workshop_v3_final.tex`와 동일.

## 변경 이력 (04/23 ~ 04/24)

### Round 1: Reviewer 3 대응 (v0 → v1)

- 9개 propagation 전략 비교 테이블 (Table 6) 추가
- Ablation 실험: direction vs dampening 분리 (4 variants)
- Decay sensitivity 분석 (Table 8: BFS variants)
- 인용 3건 추가: Xiong et al. (2025), Xu et al. (2026), Devarangadi et al. (2026)
- BFS "stress test" caveat 강화
- n=10 → n=100 EM/F1 업데이트 (Table 6)

### Round 2: 4-Agent Audit (v1 → v2-pre)

- Algorithm 1: `δ` → `δ^{h+1}` (hop exponent 수정)
- Algorithm REQUIRE: 미사용 변수 `a` 제거
- "3.7%" → "1.4pp" 수치 오류 수정
- Figure caption: "Dashed" → "Dotted"
- "damage rate" → "damage" 용어 통일 (6곳)
- "the authors" → "the author" (단독 저자)
- Molloy-Reed threshold 인용 추가
- Cross-task section 확장 (worst hub 수치)
- Generalizability 범위 한정 ("Zipfian frequency patterns")
- Limitation 3 확장 (ATTR-AWARE false negative rate 미측정 인정)
- Future Work (4), (5) 추가 (LLM diversity, alternative filters)
- Related Work: TMS (Doyle 1979), GraphRAG (Edge 2024) 추가
- 불필요 bib 항목 21개 삭제 (49 → 28)

### Round 3: 톤 리프레이밍 + 실험 보강 (v2-pre → v2-final)

**톤 전환 (방어적 → 설득적)**
- Abstract: "stress test" 제거 → "dangerous without safeguards"
- Abstract: "suggest" → "show", "establish"
- Abstract: ablation 결과 승격 ("directional filtering accounts for entire damage reduction")
- Intro: "이 논문 없었으면 production에서 69-79% damage" 시나리오 추가
- Intro: contribution 4개 → 3개 압축 (failure formulation 삭제, ablation 추가)
- Intro closing: "proactive safety study" → 구체적 scenario 기반
- Discussion: Limitation **7개 → 4개** 압축
- Discussion: Future Work **5개 → Limitation (4)에 통합**
- Discussion: "Generalizability" paragraph → "Implications"에 흡수
- Finding 6: EM/F1 convergence 설명 4문장 → 2문장 압축
- Finding 7: 3문장 → 2문장 압축
- BFS caveat (L196): 방어적 톤 → 직접적 톤

**데이터 수정**
- Cross-task worst hub: **-18.2pp → -11.9pp** (데이터 오류 수정)
- F1 수치 통일: 10.1pp → **10.2pp** (Appendix 테이블과 일치)

**Appendix A 확장**
- 3줄 → 5-hub 개별 테이블 (degree, affected memories, F1 drop)
- Hub degree-F1 상관관계 정량화 (r = -0.98)
- ATTR-AWARE per-hub 결과 포함

**Direction Ablation 실험 (신규)**
- downstream (o→s): 0.29% damage — 현재 ATTR-AWARE, **최적**
- upstream (s→o): 1.16% damage — 같은 subject의 다른 속성 공격
- bidirectional: 1.45% damage — 양방향 합집합
- BFS: 39.83% damage — 무방향 탐색
- 핵심 발견: 세 방향 모두 BFS 대비 ≥96% 감소, downstream이 strictly optimal
- Limitation (4): "open question" → "empirically confirmed" 전환

## 실험 결과 파일

`experiments/results/` 디렉토리:

| 파일 | 내용 |
|------|------|
| `reviewer_experiments_6k_1777026232.json` | **최신** — ablation (dampening + direction 7 variants) |
| `reviewer_experiments_6k_1777006481.json` | 9개 전략 비교 (n=100) |
| `reviewer_experiments_6k_1777006256.json` | ablation (dampening 4 variants, n=100) |
| `reviewer_experiments_32k_1776907355.json` | 32K scale 실험 |
| `reviewer3_wbfs_at_scale_6k_1776920013.json` | WBFS θ별 비교 |
| `reviewer3_typed_relation_6k_*.json` | typed-relation graph 비교 |
| `reviewer3_organic_residual_6k_*.json` | organic residual 분석 |
| `organic_wbfs_6k_1777018257.json` | organic WBFS 실험 |
| `residual_analysis.json` | ATTR damage memory 분류 |

## 실험 인프라

- LLM: Gemma-4-31B-it served through an OpenAI-compatible local endpoint
- Embedding: BAAI/bge-m3 (1024-dim)
- Benchmark: MemoryAgentBench (ICLR 2026) — FactConsolidation, EventQA
- Scales: 6K / 32K / 64K turns

## 컴파일

```bash
cd paper/
pdflatex workshop_v3_final.tex
bibtex workshop_v3_final
pdflatex workshop_v3_final.tex
pdflatex workshop_v3_final.tex
```

Blind 버전 동기화:
```bash
head -51 workshop.tex > /tmp/header.tex
sed -n '53,$p' workshop_v3_final.tex > /tmp/body.tex
cat /tmp/header.tex /tmp/body.tex > workshop.tex
# 이후 동일하게 pdflatex 3회
```
