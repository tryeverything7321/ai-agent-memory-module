# AI Agent Memory Module — 분석 리포트

**생성 시각:** 2026-04-07T17:16:10.988146
**LLM:** google/gemma-4-31B-it
**Embedding:** BAAI/bge-m3
**총 턴:** 60 | **소요:** 75.2s

## 1. Intent 분류 정확도

- **정확도:** 48/59 = **81.4%**

### Intent 혼동 행렬 (상위)

| Ground Truth | Predicted | Count |
|-------------|-----------|-------|
| code_review | code_review | 15 |
| knowledge_lookup | knowledge_lookup | 11 |
| project_status | project_status | 7 |
| issue_tracking | issue_tracking | 4 |
| scheduling | scheduling | 4 |
| troubleshooting | issue_tracking | 4 **miss** |
| data_analysis | data_analysis | 2 |
| document_drafting | document_drafting | 2 |
| meeting_prep | scheduling | 2 **miss** |
| team_communication | issue_tracking | 2 **miss** |
| team_communication | scheduling | 2 **miss** |
| weekly_report | weekly_report | 2 |
| document_drafting | onboarding | 1 **miss** |
| onboarding | onboarding | 1 |

## 2. 선제적 예측 (Prediction Hit Rate)

- **예측 시도:** 27회
- **적중:** 11회
- **Hit Rate:** **40.7%**
- **목표 (30%):** PASS

## 3. 메모리 검색 효과

- **메모리 활용 턴:** 57/60 (95.0%)
- **총 메모리 반환 수:** 231
- **평균 반환 (활용 턴 기준):** 4.1건

### 유저별 저장 메모리

| User | 메모리 수 | Importance 분포 |
|------|----------|----------------|
| user_pm | 11 | critical: 4, important: 7 |
| user_dev | 3 | critical: 1, important: 2 |
| user_new | 10 | critical: 1, ephemeral: 1, important: 8 |

## 4. Latency 분석

- **평균:** 1253ms
- **P50:** 1286ms
- **P95:** 1956ms
- **최소/최대:** 945ms / 2293ms

## 5. Intent 전이 패턴 (Top-10)

| 전이 | Weight |
|------|--------|
| weekly_report -> issue_tracking | 1.000 |
| data_analysis -> document_drafting | 1.000 |
| document_drafting -> weekly_report | 1.000 |
| knowledge_lookup -> code_review | 0.636 |
| onboarding -> knowledge_lookup | 0.500 |
| onboarding -> project_status | 0.500 |
| project_status -> knowledge_lookup | 0.429 |
| code_review -> knowledge_lookup | 0.429 |
| issue_tracking -> scheduling | 0.400 |
| issue_tracking -> code_review | 0.400 |

- **총 전이 패턴:** 23개

## 6. 에러 분석

- **에러 없음** (전체 턴 정상 처리)

## 7. 핵심 인사이트

- Intent 분류 정확도 81.4%로 규칙 기반만으로도 높은 정확도 달성
- 예측 hit rate 40.7%로 목표(30%) 달성 — Anticipatory Memory Chains 유효
- 총 24건 메모리 저장 (60턴 대비 0.4건/턴)
- 턴당 평균 1253ms (LLM 추출 + 임베딩 포함)

## 8. 다음 단계 제안

1. Qdrant Docker 연동으로 벡터 DB 영속성 확보
2. Decay engine 시간 경과 시뮬레이션 (7일/30일 후 메모리 상태)
3. LLM fallback intent 분류 활성화 (규칙 실패 케이스 보강)
4. 대량 데이터 벤치마크 (10K 메모리, 동시 요청 부하)
5. 실제 사용자 파일럿 (소규모 그룹 2주 운영)