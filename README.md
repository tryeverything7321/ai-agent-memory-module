# AI Agent Memory Module

> **ICML 2026 SCALE Workshop** 제출 논문의 구현체입니다.

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

## Research References

- Mnemosyne (2025): Edge-based temporal decay + boosting
- A-Mem (OpenReview): Agentic Memory
- MAGMA (2026): Multi-graph agentic memory
- EverMemOS (2026): Self-organizing memory OS
- M+ (ICML 2025): Co-trained retriever with latent memory
- Mem0, Letta/MemGPT: Production memory frameworks

## Intent Taxonomy (12 categories)

`weekly_report` · `issue_tracking` · `scheduling` · `knowledge_lookup` · `code_review` · `meeting_prep` · `data_analysis` · `team_communication` · `document_drafting` · `project_status` · `onboarding` · `troubleshooting`

## Design Documents

- 설계 문서: APPROVED (8.4/10, 2라운드 adversarial review)
- Eng Review: PASS (Architecture 4건 해결, Performance P1 1건)
- 테스트 플랜: 42 코드 경로, TDD red-green-refactor

## License

Private — 실험/연구용 프로토타입
