# 테스트 결과 보고서

## 개요

AI Agent Memory Module의 TDD(Test-Driven Development) 과정과 결과를 기록합니다.
Mock 기반 단위 테스트 → 실제 LLM 연동 통합 테스트까지의 전체 여정.

---

## 1. 테스트 전략: 어떻게 시작했나

### 설계 단계에서 정의한 것들

- **Eng Review**에서 42개 코드 경로를 매핑하고, TDD red-green-refactor 방식에 합의
- 외부 의존성(LLM, Qdrant)은 **Protocol 패턴**으로 추상화하여 Mock/Real 교체 가능하게 설계
- Phase별로 **테스트 먼저 작성(RED) → 구현(GREEN)** 순서 준수

### Mock vs Real 전략

| Component | 단위 테스트 (Mock) | 통합 테스트 (Real) |
|-----------|-------------------|-------------------|
| LLM API | `MockLLMClient` (규칙 기반) | `DooGPULLMClient` (Gemma 31B) |
| Qdrant | in-memory dict fallback | Docker (미연동) |
| SQLite | `:memory:` | `:memory:` |
| NetworkX | in-memory | in-memory |
| Embedding | `MockEmbeddingProvider` (hash→vector) | Mock (embedding API 미제공) |

---

## 2. Phase별 TDD 과정

### Phase 1: 인프라 (12 tests)

```
RED:  MetadataStore, GraphStore, VectorStore 테스트 작성 → 전부 ModuleNotFoundError
GREEN: storage/*.py 구현 → 11/12 pass
FIX:  GraphStore import 누락 → 12/12 pass ✅
```

**검증 내용:**
- SQLite CRUD, 배치 조회 (N+1 방지), 프루닝
- NetworkX 엔티티/관계 추가, 1-hop 탐색, intent 전이 확률 계산
- 벡터 저장/검색, cosine similarity dedup, 그래프 직렬화/복원

### Phase 2: Extraction Layer (11 tests)

```
RED:  extraction.py 없음 → 11 failed
GREEN: extraction.py 구현 → 11/11 pass ✅
```

**검증 내용:**
| 테스트 | 입력 | 기대 결과 | 실제 결과 |
|--------|------|-----------|-----------|
| E1 단일 fact | "다음 주 대만 출장" | fact에 "출장" 포함 | ✅ |
| E2 복수 entity | "김팀장이 판교 오피스에서 회의" | 김팀장, 판교 추출 | ✅ |
| E5 ephemeral | "ㅋㅋ 오키" | importance: ephemeral | ✅ |
| E7 critical | "내일 3시 이사회 참석 일정" | importance: critical | ✅ |
| E8 한국어 판별 | "네 알겠습니다" | ephemeral (15자 이하 + 단순 응답) | ✅ |
| E9 LLM 실패 | ConnectionError 발생 | raw text fallback 저장 | ✅ |
| E10 빈 입력 | "" | facts=[], 에러 없음 | ✅ |

### Phase 3: Storage Layer (8 tests)

```
GREEN: Phase 1 인프라 위에 추가 테스트 → 8/8 pass ✅
```

**핵심 검증:**
- **RRF fusion**: 3개 소스(Vector/Metadata/Graph) 결과를 `score(d) = Σ 1/(60 + rank)` 로 합산 → "대만" 관련 메모리가 "코드 리뷰"보다 상위
- **User isolation**: user_pm의 메모리를 user_dev가 검색 불가 (Vector fallback에서 user_id 필터링 버그 발견 → 수정)
- **Graceful degradation**: Qdrant 연결 실패해도 Metadata+Graph만으로 결과 반환

### Phase 4: Decay Engine (9 tests)

```
RED:  decay.py 없음 → import error
GREEN: decay.py 구현 → 9/9 pass ✅
```

**Ebbinghaus 망각 곡선 검증:**

| 시나리오 | λ | 경과일 | access | 계산값 | 기대 |
|----------|-----|--------|--------|--------|------|
| D1 기본 | 0.3 | 7일 | 0 | 0.122 | 임계치(0.1) 근접 |
| D2 boost | 0.3 | 8일 | 1 | 0.095 | boost로 연명 |
| D3 critical | 0.005 | 30일 | 0 | 0.861 | 30일 후에도 활성 |
| D2 극한 | 0.3 | 365일 | 100 | <0.01 | 곱셈형이라 결국 소멸 |

**곱셈형 수식의 의미:** `w(t) = e^(-λt) * (1 + boost * access_count)` — access_count가 아무리 높아도 `e^(-λt)`가 0에 수렴하면 전체도 0. 이것이 Eng Review에서 수정한 핵심 버그 (기존 가산형은 무한 성장 가능).

### Phase 5: Prediction Layer (12 tests)

```
RED:  prediction/*.py 없음 → import error
GREEN: intent.py + proactive.py 구현 → 12/12 pass ✅
```

**Intent 분류 규칙 검증:**

| 입력 | 기대 intent | 실제 | 매칭 방식 |
|------|-------------|------|-----------|
| "주간 보고서 작성" | weekly_report | ✅ | "주간 보고" 키워드 |
| "오늘 리뷰할 PR 있어?" | code_review | ✅ | "PR", "리뷰" 키워드 |
| "500 에러가 나는데" | troubleshooting | ✅ | "500", "에러" 키워드 |
| "규칙에 안 걸리는 문장" | knowledge_lookup | ✅ | 기본 fallback |

**선제적 예측 검증:**
- transition_weight > 0.5 → 예측 메모리 주입 + "예측된 컨텍스트" 레이블 ✅
- transition_weight ≤ 0.5 (분산) → 주입하지 않음 (None 반환) ✅

### Phase 6: E2E 시나리오 (11 tests)

```
RED:  user isolation 버그 → 10/11 pass
FIX:  VectorStore fallback에 user_id 필터 추가 → 11/11 pass ✅
```

**4개 시나리오 검증 결과:**

#### SC1: 기본 기억

```
입력: "우리 팀 다음 주 목요일에 대만 출장이야"
  → 저장됨 (importance: critical, λ=0.005)
  → "출장 건 어떻게 됐지?" 검색 → 해당 메모리 반환 ✅
```

#### SC2: 하이브리드 검색

```
3건 저장: "대만 출장", "대만 맛집 딘타이펑", "코드 리뷰 PR"
  → "대만 여행" 검색 → 대만 관련 메모리가 코드 리뷰보다 상위 ✅
  → user_pm 메모리를 user_dev가 검색 → 결과 없음 ✅
```

#### SC3: 선제적 예측 (Anticipatory Memory Chains)

```
패턴 학습: "주간 보고서" → "지난주 이슈" 4회 반복
  → 5번째 "주간 보고서 작성" 시:
    - IntentClassifier → weekly_report
    - TransitionGraph → issue_tracking (weight > 0.5)
    - ProactiveInjector → 이슈 관련 메모리 프리페치 ✅
```

#### SC4: 망각과 갱신

```
ephemeral (λ=0.3):
  7일 후 → w=0.122 (임계치 근접) ✅
  10일 후 → w=0.050 (프루닝 대상) ✅

critical (λ=0.005):
  30일 후 → w=0.861 (여전히 활성) ✅

팩트 갱신: "판교로 이사" → "이사 취소"
  → 기존 is_valid=false + 새 메모리 생성 ✅
```

---

## 3. 실제 LLM 연동: 어떻게 됐나

### 연동 대상

| 항목 | 값 |
|------|-----|
| API | DooGPU LiteLLM Proxy (reserved3) |
| 모델 | `google/gemma-4-31B-it` (31B 파라미터) |
| 인증 | `api_key="EMPTY"` |
| 프로토콜 | OpenAI SDK 호환 |

### Mock vs 실제 LLM 비교

| 기능 | Mock 결과 | Gemma 31B 결과 | 차이 |
|------|-----------|----------------|------|
| **Fact 추출** | 원문 그대로 저장 | "우리 팀이 다음 주에 대만으로 출장을 간다" (정규화) | LLM이 문장을 깔끔하게 정제 |
| | 1개 fact | 2개 fact ("출장 예정" + "김팀장 동행") | 복합 정보를 개별 fact으로 분리 |
| **엔티티** | 정규식 패턴만 | "김팀장"(person), "A프로젝트"(project) | 타입까지 정확 |
| **관계** | "X가 Y 담당" 패턴만 | (김팀장, 대만, visit) | 암시적 관계도 추출 |
| **Ephemeral** | 패턴 + 글자수 | "상대방의 의견에 동의함" → ephemeral | 의미 이해 후 판단 |
| **중요도** | 키워드 매칭 | "다음 달에 판교로 이사해" → critical | 3/3 정확 |
| **Intent** | 키워드 매칭 | 동일 (규칙으로 충분한 케이스) | LLM은 모호한 입력에서 차이 |

### 통합 테스트 결과 (5 tests)

```
tests/test_integration_llm.py::test_schedule_extraction     PASSED  (critical ✅)
tests/test_integration_llm.py::test_ephemeral_detection     PASSED  (ephemeral ✅)
tests/test_integration_llm.py::test_entity_extraction       PASSED  (김팀장, A프로젝트 ✅)
tests/test_integration_llm.py::test_full_chat_pipeline      PASSED  (2개 메모리 저장 + 검색 ✅)
tests/test_integration_llm.py::test_intent_transition       PASSED  (weight: 1.00 ✅)
```

**E2E 파이프라인 실행 흐름:**

```
입력: "우리 팀 다음 주에 대만 출장 가야 해"
  → Gemma 추출: {fact: "대만 출장", importance: critical}
  → Memory 생성: id=xxx, λ=0.005, weight=1.0
  → VectorStore 저장 (mock embedding)
  → SQLite 저장

입력: "김팀장이 결제 모듈 버그 수정 담당이야"
  → Gemma 추출: {fact: "김팀장 결제 모듈 담당", importance: important}
  → 2번째 응답에서 이미 1번째 메모리가 검색됨:
    "관련 기억: 우리 팀이 다음 주에 대만으로 출장을 간다"

검색: "출장 일정"
  → RRF fusion → 2건 반환 ✅
```

---

## 4. 발견된 버그와 수정

| # | 발견 시점 | 버그 | 원인 | 수정 |
|---|-----------|------|------|------|
| 1 | Phase 1 | GraphStore import 누락 | test에서 `GraphStore` 직접 사용하나 import 안 함 | `from storage.graph_store import GraphStore` 추가 |
| 2 | Phase 6 (SC2) | User isolation 실패 | VectorStore fallback이 user_id 필터 없이 전체 검색 | `_fallback_search`에 `_memory_users` 필터 추가 |

---

## 5. 최종 요약

### 테스트 현황

| 파일 | 테스트 수 | LLM 유형 | 실행 시간 |
|------|----------|----------|-----------|
| test_infra.py | 12 | Mock | 0.04s |
| test_extraction.py | 11 | Mock | 0.02s |
| test_storage.py | 8 | Mock | 0.04s |
| test_decay.py | 9 | Mock | 0.02s |
| test_prediction.py | 12 | Mock | 0.02s |
| test_scenarios.py | 11 | Mock | 0.18s |
| test_integration_llm.py | 5 | Gemma 31B | 27.92s |
| **Total (v1)** | **68** | | **~28s** |

---

## 5. v2 Taxonomy Evolution 테스트 (2026-04-08)

### 추가된 테스트 파일

| 파일 | Tests | 대상 | 소요 |
|------|-------|------|------|
| test_taxonomy_graph.py | 30 | TaxonomyGraph CRUD, decay, split, merge, 직렬화 | 0.8s |
| test_lineage.py | 8 | PhylogeneticLineage 이벤트 기록, DAG, 직렬화 | 0.1s |
| test_evolver.py | 12 | TaxonomyEvolver 2-stage 분류, sweep, mitosis, fusion | 0.3s |
| test_bootstrap.py | 12 | TaxonomyBootstrap k-means, LLM 네이밍, EPHEMERAL | 0.4s |
| test_v2_integration.py | 16 | v2 통합: Persistence, JSON 파싱, MemoryService v2, Semantic 매핑 | 0.9s |
| **Total (v2 추가분)** | **78** | | **~2.5s** |

### v2 통합 테스트 상세 (test_v2_integration.py)

| ID | 테스트 | 설명 |
|----|--------|------|
| INT1 | test_v1_mode_unchanged | use_taxonomy=False 시 v1 동작 유지 |
| INT2 | test_v2_bootstrap_phase | Bootstrap phase에서 buffering 상태 확인 |
| INT4 | test_load_taxonomy_state | 저장된 taxonomy 상태 복원 |
| INT5 | test_save_load_roundtrip | Persistence save → load round-trip |
| INT6 | test_exists_and_delete | Persistence exists/delete 동작 |
| INT7 | test_normal_json | _extract_json_array 정상 JSON 파싱 |
| INT8 | test_json_with_surrounding_text | 설명 텍스트 포함 JSON 추출 |
| INT9 | test_prefix_continuation | prefix + LLM continuation 합치기 |
| INT10 | test_unparseable_returns_none | 파싱 불가 시 None 반환 |
| INT11 | test_semantic_match/no_match | Semantic mapping 정확도 검증 |

### 전체 테스트 현황 (v1 + v2)

| 파일 | Tests | 소요 |
|------|-------|------|
| test_infra.py | 12 | 0.04s |
| test_extraction.py | 11 | 0.02s |
| test_storage.py | 8 | 0.04s |
| test_decay.py | 9 | 0.02s |
| test_prediction.py | 12 | 0.02s |
| test_scenarios.py | 11 | 0.18s |
| test_integration_llm.py | 5 | 27.92s |
| test_taxonomy_graph.py | 30 | 0.8s |
| test_lineage.py | 8 | 0.1s |
| test_evolver.py | 12 | 0.3s |
| test_bootstrap.py | 12 | 0.4s |
| test_v2_integration.py | 16 | 0.9s |
| **Total** | **146** | **~26s** |

### 실행 명령어

```bash
# Mock 테스트만 (빠름, ~2s)
pytest tests/ -v --ignore=tests/test_integration_llm.py

# 실제 LLM 포함 전체 (DooGPU 접근 필요, ~26s)
pytest tests/ -v

# v2 통합 테스트만
pytest tests/test_v2_integration.py -v

# Taxonomy 관련 테스트만
pytest tests/test_taxonomy_graph.py tests/test_evolver.py tests/test_bootstrap.py tests/test_lineage.py tests/test_v2_integration.py -v
```

### 미검증 항목

| 항목 | 이유 | 향후 계획 |
|------|------|-----------|
| 실제 Qdrant Docker | 로컬에 Docker 미설정 | docker-compose up 후 연동 |
| 장기 시뮬레이션 (624턴) | DooGPU 실행 필요 | demo_runner_v2_long.py 실행 |
| Mitosis/Extinction 실제 발생 | 198턴에서 미발생 | 624턴 데이터로 검증 예정 |
| 대량 데이터 성능 | 프로토타입 단계 | 10K 메모리 벤치마크 |
| 동시 요청 부하 | 단일 요청만 테스트 | locust/k6 부하 테스트 |
