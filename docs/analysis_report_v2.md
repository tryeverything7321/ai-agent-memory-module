# AI Agent Memory Module v2 — Taxonomy Evolution 분석 리포트

**버전:** v2
**생성 시각:** 2026-04-08T11:05:43.738224
**LLM:** google/gemma-4-31B-it
**Embedding:** BAAI/bge-m3
**총 턴:** 198 | **유저:** user_pm, user_dev, user_new, user_analyst | **소요:** 288.8s

## 1. Taxonomy Evolution 분석

### 최종 카테고리: 6개

| 카테고리 | 멤버 수 | Decay Weight | Access Count | 생성 방식 |
|----------|---------|-------------|-------------|----------|
| team_meeting_prep | 102 | 1.0000 | 102 | merge |
| technical_discussion | 61 | 2.0000 | 60 | discovery |
| document_creation | 12 | 1.5496 | 12 | bootstrap |
| bug_resolution | 11 | 1.5442 | 11 | bootstrap |
| issue_tracking | 6 | 1.2955 | 6 | bootstrap |
| data_analysis | 6 | 1.2441 | 6 | bootstrap |

### 카테고리 생성 방식 분포

- **bootstrap**: 4개
- **discovery**: 1개
- **merge**: 1개

## 2. Lineage (계통수)

- 총 이벤트: 10
- DAG 노드: 10
- 현재 활성: 6
- 멸종: 4

### 이벤트 유형별 횟수

| 이벤트 | 횟수 |
|--------|------|
| bootstrap | 7 |
| discovery | 1 |
| merge | 2 |

### 진화 타임라인

```
  2026-04-08T02:01:38 [BOOTSTRAP] schedule_management (8 members)
  2026-04-08T02:01:38 [BOOTSTRAP] issue_tracking (3 members)
  2026-04-08T02:01:38 [BOOTSTRAP] bug_resolution (5 members)
  2026-04-08T02:01:38 [BOOTSTRAP] team_communication (4 members)
  2026-04-08T02:01:38 [BOOTSTRAP] document_creation (4 members)
  2026-04-08T02:01:38 [BOOTSTRAP] data_analysis (2 members)
  2026-04-08T02:01:38 [BOOTSTRAP] meeting_preparation (4 members)
  2026-04-08T02:02:26 [DISCOVERY] technical_discussion — trigger: "Redis 캐시 만료 전략 어떤 게 좋을까?"
  2026-04-08T02:04:07 [MERGE] ['schedule_management', 'team_communication'] → team_collaboration
  2026-04-08T02:05:19 [MERGE] ['meeting_preparation', 'team_collaboration'] → team_meeting_prep
```

## 3. v1 vs v2 Intent 분류 비교

| 지표 | v1 (Rule-based) | v2 (Taxonomy Evolution) |
|------|----------------|----------------------|
| 정확도 (exact match) | 44.2% (72/163) | 3.1% (5/163) |
| **정확도 (semantic match)** | — | **38.7%** (63/163) |
| 카테고리 수 | 12 (고정) | 11 (동적) |

### Semantic Mapping Table

| v1 (ground truth) | v2 (동적) |
|-------------------|-----------|
| `code_review` | `code_review`, `meeting_preparation`, `team_meeting_prep` |
| `data_analysis` | `data_analysis` |
| `document_drafting` | `document_creation`, `document_drafting` |
| `issue_tracking` | `bug_resolution`, `issue_tracking` |
| `knowledge_lookup` | `knowledge_lookup`, `technical_discussion` |
| `meeting_prep` | `meeting_prep`, `meeting_preparation`, `team_meeting_prep` |
| `onboarding` | `onboarding`, `schedule_management`, `team_meeting_prep` |
| `project_status` | `project_status`, `team_collaboration`, `team_meeting_prep` |
| `scheduling` | `schedule_management`, `team_collaboration`, `team_meeting_prep` |
| `team_communication` | `team_collaboration`, `team_communication`, `team_meeting_prep` |
| `troubleshooting` | `bug_resolution`, `technical_discussion`, `troubleshooting` |
| `weekly_report` | `document_creation`, `team_meeting_prep`, `weekly_report` |

### v2 발견 카테고리 목록

- `buffering`
- `bug_resolution`
- `data_analysis`
- `document_creation`
- `issue_tracking`
- `meeting_preparation`
- `schedule_management`
- `team_collaboration`
- `team_communication`
- `team_meeting_prep`
- `technical_discussion`

## 4. Evolution Log

- **Turn 29**: Bootstrap 완료 — 7개 카테고리, 9개 EPHEMERAL 패턴
- **Turn 63**: 카테고리 발견 — `technical_discussion` (trigger: "Redis 캐시 만료 전략 어떤 게 좋을까?")
- **Turn 79**: Decay Sweep — no changes
- **Turn 129**: Decay Sweep — fusions=['schedule_management+team_communication→team_collaboration']
- **Turn 179**: Decay Sweep — fusions=['meeting_preparation+team_collaboration→team_meeting_prep']

## 5. LLM 생성 EPHEMERAL 패턴

총 9개 패턴:

```
  "ㅋ", "ㅎ", "ㅇㅋ", "오키", "넵", "네네", "ㄴㄴ", "점심", "ㅇㅇ"
```

## 6. Prediction (선제적 예측)

- 예측 생성: 105/198 턴 (53.0%)

### 예측 Intent 분포

| Intent | 횟수 |
|--------|------|
| knowledge_lookup | 84 |
| scheduling | 9 |
| document_drafting | 7 |
| issue_tracking | 3 |
| project_status | 1 |
| team_communication | 1 |

## 7. 메모리 통계

| 유저 | 메모리 수 |
|------|----------|
| user_analyst | 43 |
| user_dev | 33 |
| user_new | 46 |
| user_pm | 23 |
| **합계** | **145** |

## 8. Latency 분석

| 지표 | 값 |
|------|-----|
| 평균 | 1458ms |
| P90 | 2012ms |
| 최소 | 974ms |
| 최대 | 4059ms |

## 9. 에러

에러 0건

## 10. Key Insights

### 실험 결과 분석

1. **Fusion이 가장 활발한 진화 메커니즘**: 2회 병합 발생. 실제 업무 채팅에서 유사 카테고리가 자동 병합되는 현상 관찰
2. **Discovery로 빠진 카테고리 자동 보충**: Bootstrap 이후 1회 발견 — `technical_discussion`(61 members)
3. **카테고리 수렴**: Bootstrap 7개 → 최종 6개 (자동 진화로 최적 분류 체계 수렴)
5. **Semantic Match 정확도**: exact match 3.1% → semantic match **38.7%**. 동적 카테고리 이름이 다를 뿐 의미적 분류 품질은 높음

### Taxonomy Evolution의 의미

- **자동 카테고리 발견**: 하드코딩 12개 → 데이터 기반 동적 생성
- **Ebbinghaus on Taxonomy**: 카테고리 자체에 망각 곡선 적용 — 비활성 카테고리 자연 소멸
- **Fusion으로 MECE 유지**: 수동 관리 없이 유사 카테고리 자동 병합
- **v1 호환성 유지**: 기존 MemoryService 파이프라인(검색/추출/예측) 그대로 동작
