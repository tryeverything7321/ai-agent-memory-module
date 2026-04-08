# Anticipatory Memory Chains: 사내 Chat AI의 선제적 기억 시스템

> 단순 대화 기록이 아니라 사용자의 업무 패턴을 학습하고 다음 행동을 예측하는 AI 메모리 모듈

---

## 1. 문제 정의

사내 Chat 시스템의 AI 어시스턴트는 매 대화를 "처음"부터 시작한다. 지난주 논의한 프로젝트 상황, 사용자의 업무 패턴, 반복되는 질문 유형을 기억하지 못한다. 사용자는 매번 컨텍스트를 다시 설명해야 한다.

**목표:** 사용자가 "주간 보고서 작성해야 하는데"라고 말하면, 이전 보고서 관련 메모리를 검색하고, 다음으로 이슈 트래킹을 할 확률이 85%라는 것을 예측하여 관련 정보를 미리 준비하는 시스템.

## 2. 아키텍처

### 4-Layer Pipeline

```
사용자 메시지
    |
    v
+-- Layer 1: EXTRACTION --+     "주간 보고서 작성해야 하는데"
|  LLM 비동기 추출          |     -> Fact("주간 보고서 일정", critical)
|  facts / entities / rels |     -> Entity("보고서", schedule)
+-------------------------+     -> Relation("보고서" --belongs_to--> "팀")
    |
    v
+-- Layer 2: STORAGE ------+     3중 하이브리드 저장소
|  Vector (Qdrant/cosine)  |     -> 임베딩 유사도 검색
|  Graph  (NetworkX)       |     -> 엔티티 관계 탐색
|  Meta   (SQLite/WAL)     |     -> 시간/중요도 필터
+-------------------------+
    |  asyncio.gather
    |  RRF fusion: score(d) = sum(1/(60+rank))
    v
+-- Layer 3: DECAY --------+     Ebbinghaus 망각 곡선
|  w(t) = e^(-lambda*t)    |     ephemeral:  lambda=0.3  (7일 내 소멸)
|       * (1 + boost*n)    |     important:  lambda=0.05
+-------------------------+     critical:   lambda=0.005 (200일 유지)
    |
    v
+-- Layer 4: PREDICTION ---+     Intent Transition Graph
|  현재 intent -> 다음 intent|     weekly_report -> issue_tracking (85%)
|  threshold > 0.5 시 주입  |     -> 관련 메모리 3건 프리페치
+-------------------------+
    |
    v
ChatResponse {
  response: "관련 기억: ... [예측된 컨텍스트] issue_tracking (85%): ..."
  memories_used: [SearchResult, ...]
  prediction: { next: issue_tracking, weight: 0.85 }
}
```

### 핵심 설계 결정

| 결정 | 선택 | 이유 |
|------|------|------|
| 임베딩 모델 | BAAI/bge-m3 (1024-dim) | 한국어+영어 혼용 사내 채팅에 최적화 |
| 벡터 DB | Qdrant (Docker) | 필터링+페이로드 지원, 무료 |
| 그래프 | NetworkX (in-memory) | 프로토타입 속도, SQLite 직렬화 |
| 망각 곡선 | 곱셈형 Mnemosyne | 접근 빈도가 decay를 boost하는 직관적 모델 |
| 검색 융합 | RRF (k=60) | 스코어 정규화 불필요, 안정적 |
| LLM | Gemma 4 31B (DooGPU) | 사내 GPU 클러스터, 외부 API 의존 없음 |

## 3. v2: Self-evolving Taxonomy

### 문제: 고정 카테고리의 한계

v1은 12개 고정 Intent 카테고리(weekly_report, scheduling, ...)를 사용했다. 실제 운영에서 발생하는 문제:

1. **카테고리 누락**: "Redis 캐시 전략" 같은 기술 토론이 knowledge_lookup으로 뭉뚱그려짐
2. **카테고리 중복**: scheduling과 meeting_prep의 경계가 모호
3. **도메인 종속**: 팀/조직마다 업무 패턴이 다른데 카테고리가 고정

### 해결: 데이터 기반 동적 분류 체계

```
Phase 1: Bootstrap (첫 30 메시지)
    |
    v
k-means(k=auto, silhouette score) -> LLM 클러스터 네이밍
    |
    v
Phase 2: Evolution Loop
    |
    +-> 새 메시지 -> centroid cosine match? --YES-> activate (증분 업데이트)
    |                                         |
    |   NO                                    v
    |   v                              register_memory
    |   LLM classify_or_propose
    |   |
    |   +-- 기존 -> activate
    |   +-- 신규 -> add_category + lineage.record_discovery
    |
    +-> 50턴마다 Decay Sweep:
        |
        +-- Prune: weight < 0.1 -> 소멸 (Extinction)
        +-- Re-classify: 고아 메모리 재배치
        +-- Mitosis: variance > 0.5 -> k-means(k=2) 분열
        +-- Fusion: centroid cosine > 0.85 -> 가중 평균 병합
```

### 진화 메커니즘 상세

#### Mitosis (분열)

카테고리 내부의 임베딩 분산(intra-cluster variance)이 임계값(0.5)을 초과하면, 내부적으로 이질적인 주제가 섞여 있다는 신호. k-means(k=2)로 분할하고 LLM이 각 하위 그룹에 이름을 부여.

**유도 시나리오:** "기술토론" 카테고리에 DB, Frontend, DevOps, ML 등 이질적 주제가 유입되면 분열 발생.

#### Fusion (병합)

두 카테고리의 centroid cosine 유사도가 0.85를 초과하면 의미적으로 겹치는 것으로 판단. 가중 평균 centroid로 병합하고 LLM이 통합 이름을 생성.

**실험 관찰:** `schedule_management + team_communication -> team_collaboration -> team_meeting_prep` (2회 연속 병합)

#### Extinction (소멸)

Ebbinghaus 망각 곡선을 카테고리 자체에 적용. 오래 사용하지 않은 카테고리의 decay weight가 임계값(0.1) 아래로 떨어지면 자연 소멸. 소속 메모리는 가장 가까운 카테고리로 재분류.

**유도 시나리오:** 신입 온보딩 완료 후 "onboarding" 카테고리 사용 중단 -> 망각 곡선에 의해 자연 소멸.

## 4. 실험 결과

### v1: Rule-based Intent (198턴, 4유저)

| 지표 | 결과 |
|------|------|
| Intent 분류 정확도 | **81.4%** (48/59, exact match) |
| Prediction Hit Rate | **40.7%** (목표 30% 달성) |
| 메모리 활용률 | 95% (57/60턴에서 관련 메모리 검색 성공) |
| 평균 latency | 1,253ms/턴 |

### v2: Taxonomy Evolution (198턴, 4유저 x 28일)

| 지표 | 결과 |
|------|------|
| Bootstrap 카테고리 | **7개** (k-means, silhouette 자동 결정) |
| 최종 카테고리 | **6개** (Fusion 2회, Discovery 1회) |
| Exact match 정확도 | 3.1% (카테고리 **이름** 불일치) |
| **Semantic match 정확도** | **38.7%** (의미적 매핑 기반) |
| 메모리 활용률 | **98.0%** (194/198턴) |
| Prediction 생성률 | 53.0% (105/198턴) |
| 평균 latency | 1,458ms/턴 (v1 대비 +16%) |
| 에러 | **0건** |

### 진화 타임라인

```
Turn  29: BOOTSTRAP   7개 카테고리 생성 (k-means auto)
Turn  63: DISCOVERY   technical_discussion 자동 발견
                      trigger: "Redis 캐시 만료 전략 어떤 게 좋을까?"
Turn  79: SWEEP       변화 없음
Turn 129: FUSION      schedule_management + team_communication
                      -> team_collaboration
Turn 179: FUSION      meeting_preparation + team_collaboration
                      -> team_meeting_prep
```

### 주요 발견

1. **Fusion이 가장 활발한 진화 메커니즘.** 실제 업무 채팅에서 일정 관리와 팀 커뮤니케이션은 의미적으로 겹친다. 시스템이 이를 자동 감지하여 2회 연속 병합.

2. **Discovery가 누락된 카테고리를 보충.** Bootstrap에서 7개 카테고리를 생성했지만 "기술 토론"이 빠졌다. Turn 63에서 Redis 관련 질문을 트리거로 `technical_discussion`이 자동 생성되어 최종 61 members로 가장 큰 카테고리가 됨.

3. **Semantic vs Exact 정확도 차이가 핵심.** v2 exact match 3.1%는 카테고리 이름이 다를 뿐 (scheduling vs schedule_management). Semantic mapping 기반 38.7%는 실제 분류 품질을 더 정확히 반영. 과도한 Fusion으로 team_meeting_prep이 너무 넓어진 것이 개선 포인트.

4. **198턴에서 Mitosis/Extinction 미발생.** 분열 조건(variance > 0.5)과 소멸 조건(weight < 0.1)이 충족되려면 500+ 턴 또는 명시적 사용 패턴 전환이 필요. 장기 시뮬레이션(624턴, 56일, 4 phase)으로 검증 예정.

## 5. 기술 스택

```
Python 3.12 / FastAPI
|
+-- Embedding: BAAI/bge-m3 (1024-dim, DooGPU reserved9)
+-- LLM: google/gemma-4-31B-it (DooGPU reserved3)
+-- Vector DB: Qdrant (Docker, cosine similarity)
+-- Graph: NetworkX (entity_graph + intent_graph, 2 instances)
+-- Metadata: SQLite (WAL mode, aiosqlite)
+-- Clustering: scikit-learn (k-means + silhouette_score)
+-- Testing: pytest + pytest-asyncio (146 tests)
```

## 6. 코드 구조

```
memory_module/                    # 총 21 파일
|-- main.py                       # FastAPI entrypoint
|-- config.py                     # 환경 변수 + decay/prediction 파라미터
|-- models.py                     # Pydantic 도메인 모델 (11 models)
|-- extraction.py                 # LLM fact/entity/relation 추출
|-- decay.py                      # Ebbinghaus 망각 곡선
|-- llm_client.py                 # DooGPU LLM + Embedding 클라이언트
|-- api/routes.py                 # MemoryService 통합 (v1/v2 호환)
|-- storage/
|   |-- vector_store.py           # Qdrant + in-memory fallback
|   |-- graph_store.py            # NetworkX 2-graph (entity + intent)
|   |-- metadata_store.py         # SQLite WAL
|   +-- memory_index.py           # RRF fusion (asyncio.gather)
|-- prediction/
|   |-- intent.py                 # 12-category rule-based (v1)
|   +-- proactive.py              # Anticipatory Memory Chains
|-- taxonomy/                     # v2: Self-evolving Taxonomy
|   |-- taxonomy_graph.py         # NetworkX DiGraph 카테고리 그래프
|   |-- evolver.py                # 2-stage classify + sweep + mitosis/fusion
|   |-- bootstrap.py              # k-means cold-start + LLM naming
|   |-- lineage.py                # Phylogenetic DAG (진화 이벤트)
|   +-- persistence.py            # JSON 디스크 저장/복원
+-- tests/                        # 146 tests (TDD)
    |-- test_extraction.py        # 11 tests
    |-- test_storage.py           #  8 tests
    |-- test_decay.py             #  9 tests
    |-- test_prediction.py        # 12 tests
    |-- test_scenarios.py         # 11 tests
    |-- test_integration.py       #  5 tests
    |-- test_taxonomy_graph.py    # 30 tests
    |-- test_lineage.py           #  8 tests
    |-- test_evolver.py           # 12 tests
    |-- test_bootstrap.py         # 12 tests
    +-- test_v2_integration.py    # 16 tests (v2 통합)
```

## 7. 연구 기반

| 논문/프레임워크 | 적용 포인트 |
|----------------|------------|
| Mnemosyne (2025) | Edge-based temporal decay + boosting |
| A-Mem (OpenReview) | Agentic memory 패턴 |
| MAGMA (2026) | Multi-graph agentic memory |
| EverMemOS (2026) | Self-organizing memory OS |
| M+ (ICML 2025) | Co-trained retriever with latent memory |
| Mem0 / MemGPT | Production memory framework 참조 |

핵심 차별점:
- **Anticipatory Memory Chains**: 단순 검색이 아닌 Intent Transition Graph 기반 선제적 예측
- **Self-evolving Taxonomy**: 데이터 기반 동적 카테고리 진화 (생물학적 분류 체계 메타포)
- **Ebbinghaus on Taxonomy**: 망각 곡선을 카테고리 자체에 적용하는 새로운 접근

## 8. 향후 작업

| 과제 | 상태 | 설명 |
|------|------|------|
| 장기 시뮬레이션 (624턴) | 데이터 생성 완료 | Mitosis/Extinction 검증 |
| Fusion threshold 조정 | 계획 | 0.85 -> 0.9로 상향하여 과도한 병합 방지 |
| centroid EMA | 계획 | 증분 업데이트를 Exponential Moving Average로 개선 |
| EPHEMERAL 프롬프트 | 개선 완료 | few-shot + JSON 추출 강화 |
| Semantic accuracy | 구현 완료 | v1-v2 의미적 매핑 자동 평가 |
| Persistence | 구현 완료 | JSON 디스크 저장/복원 |
| Real-time 웹소켓 | 미시작 | FastAPI WebSocket 연동 |
| Multi-tenant | 미시작 | X-User-ID 기반 네임스페이스 격리 완료, ACL 추가 필요 |

---

*Private, 실험/연구용 프로토타입. 146 tests, 0 errors.*
