# Experiment Dataset — v2

## 실험 개요

| 항목 | 값 |
|------|-----|
| 버전 | v2 |
| 총 턴 | 198 |
| 유저 | user_pm, user_dev, user_new, user_analyst |
| 기간 | ?일 |
| LLM | google/gemma-4-31B-it |
| Embedding | BAAI/bge-m3 |
| 에러 | 0건 |

## 파일 설명

| 파일 | 행 수 | 설명 |
|------|-------|------|
| `turns.csv` | 198 | Turn별 메시지, 분류 결과, 정확도, latency |
| `evolution_events.csv` | 10 | Taxonomy 진화 이벤트 (bootstrap/discovery/merge/split/extinction) |
| `category_final.csv` | 6 | 최종 카테고리 상태 (member_count, decay_weight) |
| `memory_stats.csv` | 4 | 유저별 메모리 수 |
| `summary.json` | 1 | 전체 정량 지표 요약 |

## 주요 정량 지표

| 지표 | 값 |
|------|-----|
| v1 분류 정확도 | 44.2% |
| v2 exact match | 3.1% |
| v2 semantic match | 38.7% |
| Prediction 생성률 | 53.0% |
| 메모리 활용률 | 98.0% |
| Bootstrap 카테고리 | 7개 |
| 최종 카테고리 | 6개 |
| Fusion 횟수 | 2회 |
| Discovery 횟수 | 1회 |
| Extinction 수 | 4개 |
| 평균 latency | 1458ms |
| P90 latency | 2012ms |

## turns.csv 컬럼 설명

| 컬럼 | 타입 | 설명 |
|------|------|------|
| turn_id | int | 턴 순번 (0-indexed) |
| user_id | str | 유저 식별자 |
| message | str | 사용자 메시지 원문 |
| timestamp | str | ISO 8601 타임스탬프 |
| ground_truth | str | 정답 Intent (v1 카테고리 기준) |
| v1_classified | str | v1 규칙 기반 분류 결과 |
| v2_classified | str | v2 taxonomy 동적 분류 결과 |
| v1_correct | 0/1 | v1 분류 정확도 (ground_truth == v1_classified) |
| v2_exact_correct | 0/1 | v2 exact match (ground_truth == v2_classified) |
| v2_semantic_correct | 0/1 | v2 semantic match (의미적 매핑 기반) |
| memories_found | int | 검색된 관련 메모리 수 |
| has_prediction | 0/1 | 선제적 예측 생성 여부 |
| pred_intent | str | 예측된 다음 Intent |
| pred_weight | float | 예측 전이 확률 |
| latency_ms | int | 처리 시간 (밀리초) |
| has_error | 0/1 | 에러 발생 여부 |
