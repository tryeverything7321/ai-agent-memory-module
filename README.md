# AI Agent Memory Module

## Repository Context

이 저장소는 두 단계의 작업이 함께 들어 있습니다.

1. **원래 main 브랜치 / MVP 프로젝트**
   - 목적: 사내 Chat 시스템을 위한 선제적 AI 메모리 모듈 구현.
   - 핵심 아이디어: 사용자의 업무 패턴을 장기 기억으로 저장하고, intent transition을 이용해 다음에 필요할 가능성이 높은 컨텍스트를 미리 검색/주입하는 "Anticipatory Memory Chains".
   - 구현 범위: FastAPI 서비스, hybrid retrieval(Vector + Graph + Metadata), Ebbinghaus-style decay, intent-transition prediction, self-evolving taxonomy 실험.
   - 이 README의 기존 내용은 주로 이 MVP 시스템 구현을 설명합니다.

2. **SCALE @ ICML 2026 workshop paper (`feat/deep-dive-analysis` / `paper/`)**
   - 목적: 위 MVP를 직접 홍보하는 것이 아니라, graph-based agent memory가 scale될 때 생길 수 있는 **forgetting propagation failure mode**를 분석.
   - 핵심 질문: graph memory system이 consistency를 위해 invalidation propagation을 도입하면, co-occurrence graph 위의 naive BFS propagation이 unrelated memories까지 손상시키는가?
   - 핵심 결론: co-occurrence is not dependency. Unfiltered propagation over entity co-occurrence graphs can create collateral forgetting through hub entities; dependency-aware propagation, such as the proposed ATTR-AWARE object-to-subject filter, substantially reduces this damage without LLM calls at propagation time.
   - 논문 파일과 실험 요약은 [`paper/`](paper/)에 있습니다. 특히 [`paper/submission_logic_summary.md`](paper/submission_logic_summary.md)는 논문의 주장, 실험 목적, reviewer-facing takeaway를 정리합니다.

따라서 root README의 architecture 설명은 원래 product/MVP 방향이고, workshop paper는 그와 별도로 **graph-based memory forgetting의 구조적 위험**을 분석한 연구 결과입니다.

사내 Chat 시스템용 **선제적 AI 메모리 모듈** — 단순 대화 기록이 아니라 사용자의 업무 패턴을 학습하고 다음 행동을 예측하는 "Anticipatory Memory Chains" 구현.

## Architecture

4-Layer Architecture (논문/연구 기반):

```
Layer 1: EXTRACTION — 대화에서 facts/entities/relations 추출 (LLM 비동기)
Layer 2: STORAGE    — Qdrant(vector) + NetworkX(graph) + SQLite(metadata)
Layer 3: DECAY      — Mnemosyne 망각 곡선: w(t) = e^(-λt) * (1 + boost * access_count)
Layer 4: PREDICTION — Intent Transition Graph → 선제적 컨텍스트 주입
```

### 데이터 흐름 (단일 메시지 처리)

```
사용자: "주간 보고서 작성해야 하는데"
        │
        ▼
  ┌─ api/routes.py: MemoryService.process_chat() ─────────────────┐
  │                                                                │
  │  1️⃣  IntentClassifier.classify()              prediction/intent.py
  │     "주간 보고" 키워드 매칭 → weekly_report                      │
  │                                                                │
  │  2️⃣  GraphStore.record_intent_transition()    storage/graph_store.py
  │     이전 intent → weekly_report 전이 기록                        │
  │                                                                │
  │  3️⃣  MemoryIndex.search()  [asyncio.gather]   storage/memory_index.py
  │     ├─ VectorStore.search()   → cosine 유사도  storage/vector_store.py
  │     ├─ MetadataStore.query()  → 시간/중요도    storage/metadata_store.py
  │     └─ GraphStore.neighbors() → 관계 탐색      storage/graph_store.py
  │     → RRF fusion: score(d) = Σ 1/(60 + rank)  top-5 반환      │
  │                                                                │
  │  4️⃣  ProactiveInjector.predict_and_fetch()    prediction/proactive.py
  │     weekly_report → issue_tracking (확률 0.85)                  │
  │     threshold(0.5) 초과 → 이슈 메모리 3건 프리페치               │
  │                                                                │
  │  5️⃣  Extractor.extract()  [비동기 후처리]      extraction.py
  │     "주간 보고서" → Fact(schedule, critical)                     │
  │     → dedup 확인(cosine>0.9) → Memory 생성 → 3 stores 저장     │
  └────────────────────────────────────────────────────────────────┘
        │
        ▼
  ChatResponse {
    response: "관련 기억: ... [예측된 컨텍스트] issue_tracking (85%): ..."
    memories_used: [SearchResult, ...]
    prediction: IntentPrediction { next: issue_tracking, weight: 0.85 }
  }
```

### 핵심 기능

| 기능 | 설명 |
|------|------|
| **하이브리드 검색** | Vector + Graph + Metadata → RRF fusion (k=60) |
| **Ebbinghaus 망각** | 중요도별 감쇠율 (ephemeral λ=0.3, critical λ=0.005) |
| **메모리 Dedup** | 임베딩 cosine > 0.9 → 기존 메모리 access_count 증가 |
| **선제적 예측** | Intent 전이 확률 > 50% 시 "예측된 컨텍스트" 레이블로 주입 |
| **User 격리** | X-User-ID 헤더 기반 메모리 네임스페이스 분리 |

## Project Structure

```
memory_module/
├── main.py              # FastAPI entrypoint
├── config.py            # Settings (env 기반)
├── models.py            # Pydantic 도메인 모델
├── extraction.py        # LLM 추출 + 규칙 분류
├── decay.py             # Ebbinghaus 망각 곡선
├── llm_client.py        # DooGPU LLM + Embedding 클라이언트
├── storage/
│   ├── vector_store.py  # Qdrant + in-memory fallback
│   ├── graph_store.py   # NetworkX (entity_graph + intent_graph)
│   ├── metadata_store.py # SQLite
│   └── memory_index.py  # RRF fusion (asyncio.gather 병렬)
├── prediction/
│   ├── intent.py        # 12-category 규칙 분류 (v1)
│   └── proactive.py     # Anticipatory Memory Chains
├── taxonomy/            # ★ v2: Self-evolving Taxonomy
│   ├── taxonomy_graph.py # NetworkX DiGraph 카테고리 그래프
│   ├── evolver.py       # 2-stage 분류 + decay sweep + mitosis/fusion
│   ├── bootstrap.py     # k-means 콜드스타트 + LLM 네이밍 + EPHEMERAL 생성
│   ├── lineage.py       # Phylogenetic DAG (진화 이벤트 기록)
│   └── persistence.py   # Taxonomy/Lineage JSON 디스크 저장/복원
├── api/routes.py        # MemoryService 통합 (v1/v2 호환)
├── docker-compose.yml   # Qdrant + App
├── demo_runner.py       # v1 합성 데이터 데모
├── demo_runner_v2.py    # v2 Taxonomy Evolution 데모 (198턴)
├── demo_runner_v2_long.py # v2 장기 시뮬레이션 (624턴, Mitosis/Extinction 검증)
├── analyze_results.py   # v1 분석 리포트
├── analyze_results_v2.py # v2 분석 리포트 (semantic accuracy 포함)
├── data/
│   ├── generate_synthetic.py       # 합성 대화 (v1)
│   ├── generate_realistic.py       # 리얼리스틱 데이터 (4유저, 28일, 200+턴)
│   ├── generate_long_simulation.py # 장기 시뮬레이션 (4유저, 56일, 624턴)
│   ├── synthetic_conversations.json
│   ├── realistic_conversations.json
│   ├── long_simulation.json        # 장기 시뮬레이션 데이터
│   └── demo_results_v2.json        # v2 데모 결과
├── docs/
│   ├── test_results.md             # TDD 과정 및 결과
│   ├── analysis_report.md          # v1 분석 리포트
│   ├── analysis_report_v2.md       # v2 Taxonomy Evolution 분석 리포트
│   └── technical_report.md         # 기술 블로그/포트폴리오용 문서
└── tests/               # 146 tests (TDD)
```

## Quick Start

```bash
# 가상환경 설정
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 테스트 실행 (146 tests)
pytest tests/ -v

# 서버 실행 (Qdrant Docker 필요)
docker-compose up -d qdrant
uvicorn main:app --reload

# --- v1 (Rule-based Intent) ---
PYTHONPATH=. python data/generate_synthetic.py
PYTHONPATH=. python demo_runner.py
PYTHONPATH=. python analyze_results.py

# --- v2 (Taxonomy Evolution) ---
PYTHONPATH=. python data/generate_realistic.py   # 4유저×28일 리얼리스틱 데이터
PYTHONPATH=. python demo_runner_v2.py             # Bootstrap + Evolution 데모
PYTHONPATH=. python analyze_results_v2.py         # v2 분석 리포트 (semantic accuracy 포함)

# --- v2 장기 시뮬레이션 (Mitosis/Extinction 검증) ---
PYTHONPATH=. python data/generate_long_simulation.py  # 4유저×56일×624턴
PYTHONPATH=. python demo_runner_v2_long.py            # 장기 시뮬레이션 (DooGPU 필요)
```

## 환경 변수 (.env)

```env
MEMORY_QDRANT_HOST=localhost
MEMORY_QDRANT_PORT=6333
MEMORY_SQLITE_PATH=memory.db
MEMORY_LLM_BASE_URL=http://localhost:8080/v1
MEMORY_EMBEDDING_BASE_URL=http://localhost:8080/v1
```

## v2: Self-evolving Taxonomy

v1의 12개 고정 Intent 카테고리를 **데이터 기반 동적 분류 체계**로 교체:

| 기능 | 설명 |
|------|------|
| **Bootstrap** | 첫 30개 메시지 → k-means(k=3~7, silhouette score) → LLM 네이밍 |
| **2-stage 분류** | 1차 centroid cosine match (~0ms) → 2차 LLM fallback (~1s) |
| **Taxonomy Decay** | Ebbinghaus 망각 곡선을 카테고리 자체에 적용 — 비활성 카테고리 자연 소멸 |
| **Mitosis (분열)** | intra-cluster variance > 0.5 → k-means(k=2) 분할 + LLM 네이밍 |
| **Fusion (병합)** | centroid cosine > 0.85 → 가중 평균 centroid + LLM 네이밍 |
| **Lineage DAG** | 모든 진화 이벤트(bootstrap/discovery/split/merge/extinction) 계통수 기록 |
| **EPHEMERAL LLM** | 하드코딩 패턴 대신 LLM이 도메인별 30개 ephemeral 패턴 자동 생성 |
| **Persistence** | TaxonomyGraph + Lineage JSON 디스크 저장/복원 (서버 재시작 대응) |
| **Semantic Accuracy** | v1↔v2 의미적 매핑 기반 분류 정확도 자동 평가 |

### Taxonomy Evolution Flow

```
User Messages (30개 버퍼링)
    │
    ▼  [Bootstrap]
k-means(k=auto) → LLM 클러스터 네이밍 → TaxonomyGraph 초기화
    │
    ▼  [Evolution Loop]
새 메시지 → centroid match? ──YES→ activate_category (centroid 증분 업데이트)
    │                          │
    NO                         ▼
    ▼                    register_memory
LLM classify_or_propose
    │
    ├─ 기존 카테고리 → activate
    └─ 신규 카테고리 → add_category + lineage.record_discovery
    │
    ▼  [50턴마다]
Decay Sweep → prune → re-classify orphans → mitosis → fusion
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Server | FastAPI |
| Vector DB | Qdrant (Docker) |
| Graph | NetworkX (in-memory, SQLite 직렬화) |
| Metadata | SQLite (WAL mode) |
| Embedding | BAAI/bge-m3 (1024-dim, DooGPU) |
| LLM | google/gemma-4-31B-it (DooGPU) |
| Clustering | scikit-learn (k-means + silhouette) |

## Test Coverage

| Module | Tests | Pass |
|--------|-------|------|
| Infra (MetadataStore, GraphStore, VectorStore) | 12 | ✅ |
| Extraction (fact/entity/relation/분류) | 11 | ✅ |
| Storage (RRF, dedup, isolation, degradation) | 8 | ✅ |
| Decay (Ebbinghaus, pruning, update) | 9 | ✅ |
| Prediction (intent, transition, injection) | 12 | ✅ |
| E2E Scenarios (4개 시나리오) | 11 | ✅ |
| Integration (Real LLM: Gemma 31B) | 5 | ✅ |
| TaxonomyGraph (CRUD, decay, split, merge, 직렬화) | 30 | ✅ |
| Lineage DAG (이벤트 기록, 직렬화) | 8 | ✅ |
| Evolver (2-stage 분류, sweep, mitosis, fusion) | 12 | ✅ |
| Bootstrap (k-means, LLM 네이밍, EPHEMERAL) | 12 | ✅ |
| v2 Integration (Persistence, JSON파싱, Semantic매핑) | 16 | ✅ |
| **Total** | **146** | **146 pass** |

## Demo Results (Real LLM + Real Embedding)

### v1 (Rule-based Intent, 60턴)

| 지표 | 결과 |
|------|------|
| Intent 분류 정확도 | **81.4%** (48/59) |
| Prediction Hit Rate | **40.7%** (목표 30% PASS) |
| 메모리 활용률 | 95% (57/60턴) |
| 평균 latency | 1,253ms/턴 |
| 에러 | 0건 |

상세 분석: [`docs/analysis_report.md`](docs/analysis_report.md)

### v2 (Taxonomy Evolution, 198턴, 4유저×28일)

| 지표 | 결과 |
|------|------|
| 총 턴 | **198** (4유저, 81세션, 28일) |
| Bootstrap 카테고리 | **7개** (k-means auto) |
| 최종 카테고리 | **6개** (Fusion 2회, Discovery 1회) |
| Discovery 이벤트 | **1회** (`technical_discussion` 자동 생성) |
| Fusion 이벤트 | **2회** (유사 카테고리 자동 병합) |
| 메모리 | **145개** (4유저 합산) |
| Semantic 정확도 | **38.7%** (exact match 3.1% → 의미적 매핑 기반) |
| Prediction 생성률 | **53.0%** (105/198턴) |
| 메모리 활용률 | **98.0%** (194/198턴) |
| 평균 latency | **1,458ms/턴** |
| 에러 | **0건** |

상세 분석: [`docs/analysis_report_v2.md`](docs/analysis_report_v2.md)

### v2 장기 시뮬레이션 (624턴, 4유저×56일)

| 지표 | 결과 |
|------|------|
| 총 턴 | **624** (4유저, 224세션, 56일, 4 phases) |
| Bootstrap 카테고리 | **7개** (k-means auto) |
| 최종 카테고리 | **4개** (Fusion 4회, Discovery 1회) |
| Fusion 이벤트 | **4회** (5개 카테고리 연속 병합 → strategic_tech_ops) |
| Discovery 이벤트 | **1회** (`tech_guide` 자동 생성) |
| Extinction (merge 경유) | **8개** (부모 카테고리 자연 소멸) |
| Mitosis | **0회** (개선 필요: 분열 조건 강화 예정) |
| 메모리 | **191개** (4유저 합산) |
| Prediction 생성률 | **62.3%** (389/624턴) |
| 메모리 활용률 | **99.4%** (620/624턴) |
| 평균 latency | **1,623ms/턴** |
| 에러 | **0건** |

상세 분석: [`docs/analysis_report_v2_long.md`](docs/analysis_report_v2_long.md)

## Research: Graph-aware Selective Forgetting

### 논문

**"Collateral Damage in Graph-based Memory Forgetting: Quantification, Exploitation, and Defense"**

AI 메모리 시스템의 graph-based invalidation propagation 취약성을 최초로 분석한 연구. 교통공학의 network failure propagation theory를 AI 메모리에 적용.

- LaTeX 소스: [`paper/main.tex`](paper/main.tex) (18페이지, Table 10+, Finding 11)
- 참고문헌: [`paper/references.bib`](paper/references.bib) (37개 entries)
- 리뷰 현황: [`.review/2026-04-10-full-paper-review.md`](.review/2026-04-10-full-paper-review.md) (2차 텍스트 리뷰 완료)
- 남은 실험 작업: [`.claude/todo-paper-experiments.md`](.claude/todo-paper-experiments.md) (7건)

### 논문 진행 상태

아래 표는 2026-04-15 시점의 초기 full-paper draft 상태를 기록한 것입니다. 이후 SCALE workshop 제출용으로 논문이 재정리되었고, 최종 제출본은 [`paper/workshop_20260427.pdf`](paper/workshop_20260427.pdf)입니다. 현재 제출 논문의 핵심 논리와 실험별 역할은 [`paper/submission_logic_summary.md`](paper/submission_logic_summary.md)를 참고하세요.

#### Historical status snapshot (2026-04-15)

| 단계 | 상태 |
|------|------|
| 1차 텍스트 리뷰 | 완료 (Intro/Background/Related Work 재작성, bib +16편) |
| 2차 텍스트 리뷰 | 완료 (alpha값 수정, bib 저자 교체, 구조 개선 16건) |
| 실험 보강 | **진행 중** (KS test, mixed-effects, TBD placeholder 등 7건) |
| 최종 제출 | 당시 미완료. SCALE workshop 제출본은 이후 `paper/workshop_20260427.pdf`로 정리됨 |

### 핵심 발견 (4 Contributions)

| # | Contribution | 핵심 수치 |
|---|-------------|----------|
| **C1** | Scale trend — BFS propagation의 collateral damage | 68.9-79.0% damage, hub degree 23->298 (~13x vs ~7.5x fact growth) |
| **C2** | Cross-task contamination — 무관한 task 오염 | EM -5.0pp, F1 -18.2pp |
| **C3** | Adversarial hub exploitation — 5 fake facts 공격 | 57.3% valid memory 파괴 (32K) |
| **C4** | Attribute-aware defense — 교통공학 방향성 전파 | 78-100% 방어율, BFS 대비 80x 효과 |

### Graph Topology Analysis

Entity co-occurrence graph의 heavy-tailed degree distribution 확인 (scale-free 특성과 일치):

| Scale | alpha (MLE) | k_min | KS D | Max Hub Degree |
|-------|------------|-------|------|---------------|
| 6K | 2.87 +/- 0.47 | 6 | 0.075 | 23 |
| 32K | 2.73 +/- 0.12 | 5 | 0.037 | 121 |
| 64K | 2.96 +/- 0.05 | 3 | 0.033 | 298 |

### 통계적 유의성

- **Wilcoxon signed-rank**: p=0.0022 (19 paired observations)
- **Bootstrap 95% BCa CI**: [2.82, 15.67]pp (0 제외)
- **Cohen's d**: 0.66-0.95 (medium-large effect)

### 실험 인프라

| Component | Specification |
|-----------|--------------|
| LLM | google/gemma-4-31B-it (DooGPU reserved3) |
| Embedding | BAAI/bge-m3 1024-dim (DooGPU reserved9) |
| Benchmark | MemoryAgentBench (ICLR 2026) |
| Context | 6K, 32K, 64K (FactConsolidation) + 65K (EventQA) |

### 프로젝트 파일 가이드

```
memory_module/
│
│  ═══ 논문 ���══
├── paper/
│   ├── main.tex              <- 논문 본문 (정본)
│   ├── references.bib        <- 참고문헌 (37편)
│   ├── main.pdf              <- 컴파일된 PDF
│   ├── figures/              <- 논문 그림
│   └── literature_survey_2026.md  <- 문헌조사 결과
│
├── .review/                  <- 리뷰 리포트
│   └── 2026-04-10-full-paper-review.md
├── .claude/
│   └── todo-paper-experiments.md  <- 남은 실험 작업 (7건)
│
│  ═══ 실험 코드 ═══
├── experiments/
│   ├── graph_forgetting.py        <- BFS propagation 실험 (C1)
│   ├── adversarial_attack.py      <- 공격 실험 (C3)
│   ├── benchmark_accurate_retrieval.py  <- Cross-task (C2)
│   ├── statistical_analysis.py    <- Wilcoxon, bootstrap, Bonferroni
│   ├── deep_dive_analysis.py      <- KS test, multi-run 통계
│   ├── deep_dive_experiments.py   <- Depth, black-box, degree-cap (C4)
│   ├── generate_figures.py        <- 논문 figure 생성
│   └── results/                   <- 실험 결과 JSON (6K/32K/64K)
│
│  ═══ 메모리 모듈 코어 (MVP, 안정) ═══
├── models.py                 <- Entity/Memory 데이터 모델
├── extraction.py             <- Entity extraction
├─��� decay.py                  <- Ebbinghaus 망각 곡선
├── storage/                  <- Graph + Vector + Metadata 저장소
├── taxonomy/                 <- Self-evolving taxonomy (v2)
├── prediction/               <- Intent prediction
├── tests/                    <- 146 tests
│
│  ═══ 참고 문서 ═══
├── docs/
│   ├── deep_dive_analysis.md      <- Topology 분석 결과
│   ├── statistical_analysis.md    <- 통계 유의성 리포트
│   ├── paper_draft_v1.md          <- 초기 드래프트 (historical)
│   └── paper_draft_v2.md          <- 중간 드래프트 (historical)
└── research_reference/            <- 외부 참고 자료
```

### 논문 빌드

```bash
cd paper
make          # pdflatex -> bibtex -> pdflatex x 2
# 또는
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

### 실험 재현

```bash
# 환경 설정
source .venv/bin/activate

# Scale trend (C1) — 6K/32K/64K context
PYTHONPATH=. python experiments/adversarial_attack.py --context_size 6k
PYTHONPATH=. python experiments/adversarial_attack.py --context_size 32k

# Cross-task (C2)
PYTHONPATH=. python experiments/benchmark_accurate_retrieval.py

# Deep-dive analysis (topology + depth + defense)
PYTHONPATH=. python experiments/deep_dive_analysis.py
PYTHONPATH=. python experiments/deep_dive_experiments.py

# Statistical analysis (기존 결과에서 Wilcoxon + bootstrap)
PYTHONPATH=. python experiments/statistical_analysis.py

# Figure generation
PYTHONPATH=. python experiments/generate_figures.py
```

---

## Intent Taxonomy (12 categories)

`weekly_report` · `issue_tracking` · `scheduling` · `knowledge_lookup` · `code_review` · `meeting_prep` · `data_analysis` · `team_communication` · `document_drafting` · `project_status` · `onboarding` · `troubleshooting`

## Research References

- [Mem0](https://arxiv.org/abs/2504.19413) (2025): Directed labeled KG + LLM conflict detection
- [MemGPT/Letta](https://arxiv.org/abs/2310.08560) (2023): OS-inspired virtual context management
- [A-Mem](https://arxiv.org/abs/2502.12110) (NeurIPS 2025): Zettelkasten-style agentic memory
- [MAGMA](https://arxiv.org/abs/2601.03236) (2026): Multi-graph agentic memory
- [Mnemosyne](https://arxiv.org/abs/2510.08601) (2025): Per-memory temporal decay (reverse sigmoid)
- [Zep](https://blog.getzep.com) (2025): Temporal knowledge graph
- [MemoryAgentBench](https://arxiv.org/abs/2502.XXXXX) (ICLR 2026): LLM agent memory benchmark

## Design Documents

- 설계 문서: APPROVED (8.4/10, 2라운드 adversarial review)
- Eng Review: PASS (Architecture 4건 해결, Performance P1 1건)
- 테스트 플랜: 42 코드 경로, TDD red-green-refactor

## License

Private — 실험/연구용 프로토타입
