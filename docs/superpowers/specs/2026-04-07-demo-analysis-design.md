# Demo & Analysis 설계서

## 개요

AI Agent Memory Module의 68개 Mock 테스트 + 5개 실제 LLM 통합 테스트가 완료된 상태에서,
**합성 대화 데이터 120턴 전체를 Real LLM + Real Embedding으로 실행**하고 정량적 분석을 수행한다.

## 목표

1. Mock → Real 전환 시 품질 차이 정량화
2. Anticipatory Memory Chains (선제적 예측)의 실제 hit rate 측정
3. Ebbinghaus 망각 곡선의 시간 경과별 분포 확인
4. dedup 정확도 비교 (hash 기반 vs 시맨틱 임베딩)

## 인프라

| 항목 | 값 |
|------|-----|
| LLM | google/gemma-4-31B-it (DooGPU reserved3) |
| Embedding | BAAI/bge-m3, 1024-dim (DooGPU reserved9) |
| Vector DB | in-memory fallback (Qdrant Docker 미사용) |
| Metadata | SQLite :memory: |
| Graph | NetworkX in-memory |

## 구현 범위

### 1. DooGPUEmbeddingProvider (`vector_store.py`)

기존 `EmbeddingProvider` Protocol을 구현하는 실제 임베딩 클라이언트.

```python
class DooGPUEmbeddingProvider:
    dim = 1024
    async def embed(self, text: str) -> list[float]
    async def embed_batch(self, texts: list[str]) -> list[list[float]]
```

- OpenAI SDK 호환 `/v1/embeddings` 엔드포인트 사용
- `embed_batch`는 demo_runner에서 효율적 배치 처리용

### 2. demo_runner.py

합성 데이터 120턴을 순차 실행하는 스크립트.

**흐름:**
1. `data/synthetic_conversations.json` 로드
2. Real LLM + Real Embedding으로 MemoryService 초기화
3. 유저별/세션별 순차 `process_chat()` 호출
4. 턴마다 기록: intent, memories_found, prediction, latency
5. 결과 저장: `data/demo_results.json`

**출력 스키마:**
```json
{
  "meta": {"total_turns": 120, "duration_sec": ..., "llm_model": "..."},
  "turns": [
    {
      "turn_id": 0,
      "user_id": "user_pm",
      "message": "...",
      "intent": "weekly_report",
      "memories_found": 3,
      "prediction": {"next_intent": "issue_tracking", "weight": 0.85},
      "facts_extracted": 2,
      "dedup_hit": false,
      "latency_ms": 1200
    }
  ]
}
```

### 3. analyze_results.py

demo_results.json을 읽어 분석 리포트 생성.

**분석 항목:**

| 지표 | 계산 방법 |
|------|-----------|
| Prediction hit rate | 예측 intent == 다음 실제 intent / 전체 예측 횟수 |
| 검색 정밀도 | memories_found > 0인 턴 비율 |
| 평균 추출 fact 수 | facts_extracted 평균 |
| Dedup 비율 | dedup_hit / 전체 턴 |
| Intent 전이 top-10 | 가장 빈번한 (from→to) 쌍 |
| 턴당 latency | 평균/p50/p95 (ms) |
| 유저별 메모리 분포 | importance별 메모리 수 |

**산출:** `docs/analysis_report.md`

## 성공 기준

- 120턴 전체 에러 없이 완주
- Prediction hit rate > 30%
- dedup이 최소 1회 이상 동작
- analysis_report.md에 6개 이상 지표 포함
