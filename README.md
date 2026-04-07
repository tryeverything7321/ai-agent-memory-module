# AI Agent Memory Module

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
├── storage/
│   ├── vector_store.py  # Qdrant + in-memory fallback
│   ├── graph_store.py   # NetworkX (entity_graph + intent_graph)
│   ├── metadata_store.py # SQLite
│   └── memory_index.py  # RRF fusion (asyncio.gather 병렬)
├── prediction/
│   ├── intent.py        # 12-category 규칙 분류
│   └── proactive.py     # Anticipatory Memory Chains
├── api/routes.py        # MemoryService 통합
├── docker-compose.yml   # Qdrant + App
├── demo_runner.py       # 합성 데이터 전체 실행 (Real LLM + Embedding)
├── analyze_results.py   # 데모 결과 → 분석 리포트 생성
├── data/
│   ├── generate_synthetic.py  # 합성 대화 데이터 생성
│   ├── synthetic_conversations.json  # 3유저, 30세션, 120턴
│   └── demo_results.json      # 데모 실행 결과
├── docs/
│   ├── test_results.md        # TDD 과정 및 결과
│   └── analysis_report.md     # 정량 분석 리포트
└── tests/               # 68 tests (TDD)
```

## Quick Start

```bash
# 가상환경 설정
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 테스트 실행
pytest tests/ -v

# 서버 실행 (Qdrant Docker 필요)
docker-compose up -d qdrant
uvicorn main:app --reload

# 합성 데이터 생성
PYTHONPATH=. python data/generate_synthetic.py

# 데모 실행 (Real LLM + Embedding, DooGPU 접근 필요)
PYTHONPATH=. python demo_runner.py

# 분석 리포트 생성
PYTHONPATH=. python analyze_results.py
```

## 환경 변수 (.env)

```env
MEMORY_QDRANT_HOST=localhost
MEMORY_QDRANT_PORT=6333
MEMORY_SQLITE_PATH=memory.db
MEMORY_LLM_BASE_URL=http://localhost:8080/v1
MEMORY_EMBEDDING_BASE_URL=http://localhost:8080/v1
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
| **Total** | **68** | **68 pass** |

## Demo Results (Real LLM + Real Embedding)

합성 대화 60 유저턴을 Gemma 31B + bge-m3로 실행한 정량 결과:

| 지표 | 결과 |
|------|------|
| Intent 분류 정확도 | **81.4%** (48/59) |
| Prediction Hit Rate | **40.7%** (목표 30% PASS) |
| 메모리 활용률 | 95% (57/60턴) |
| 평균 latency | 1,253ms/턴 |
| 에러 | 0건 |

```bash
# 데모 실행
PYTHONPATH=. python demo_runner.py

# 분석 리포트 생성
PYTHONPATH=. python analyze_results.py
```

상세 분석: [`docs/analysis_report.md`](docs/analysis_report.md)

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
