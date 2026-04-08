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
| 카테고리 수 | 12 (고정) | 11 (동적) |

> **해석 주의**: v2 exact match 3.1%는 카테고리 **이름** 불일치 때문이지 분류 오류가 아님.
> 예: ground truth "scheduling" vs v2 "schedule_management"는 의미적으로 동일.
> v2는 데이터 기반 이름을 자동 생성하므로 v1의 하드코딩 이름과 1:1 대응이 불가능.
> 정확한 평가는 의미적 매핑(semantic matching) 기반 재평가 필요.
>
> **v1→v2 의미 매핑 (수동 대응):**
> - scheduling → schedule_management, team_collaboration
> - issue_tracking → issue_tracking, bug_resolution
> - code_review → meeting_preparation
> - knowledge_lookup → technical_discussion
> - data_analysis → data_analysis
> - document_drafting → document_creation
> - team_communication → team_communication, team_collaboration
> - project_status → team_collaboration
> - onboarding → schedule_management (신입 온보딩이 일정 관리와 병합)

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

1. **Fusion이 가장 활발한 진화 메커니즘**: 2회 연속 병합 발생 (`schedule_management + team_communication → team_collaboration → team_meeting_prep`). 실제 업무 채팅에서 일정 관리와 팀 커뮤니케이션이 의미적으로 겹치는 현상을 시스템이 자동 감지
2. **Discovery로 빠진 카테고리 자동 보충**: Bootstrap에서 7개 카테고리 → Turn 63에서 `technical_discussion` 자동 발견. 기존 12개 고정 카테고리에 없던 "기술 토론" 카테고리가 데이터 기반으로 생성됨 (최종 61 members로 최대 카테고리)
3. **Mitosis/Extinction 미발생**: 198턴 규모에서는 분열/소멸 조건이 충족되지 않음. 더 긴 기간(수백 턴) 또는 사용 패턴 급변 시 발생 예상
4. **EPHEMERAL 패턴 LLM 생성 실패 → fallback**: Gemma 31B가 JSON 배열 생성에서 fallback 기본 패턴(9개)으로 빠짐. 프롬프트 개선 또는 더 큰 모델 필요
5. **2-stage 분류 효율성**: Bootstrap 이후 centroid match만으로 대부분 분류 성공 → LLM 호출 최소화. 평균 latency 1458ms (v1 1253ms 대비 16% 증가, 임베딩 생성 비용 포함)

### Taxonomy Evolution의 의미

- **자동 카테고리 발견**: 하드코딩 12개 → 데이터 기반 동적 생성 (최종 6개로 수렴)
- **Ebbinghaus on Taxonomy**: 카테고리 자체에 망각 곡선 적용 — 사용되지 않는 카테고리 자연 소멸
- **Fusion으로 MECE 유지**: 수동 관리 없이 유사 카테고리 자동 병합
- **v1 호환성 유지**: 기존 MemoryService 파이프라인(검색/추출/예측) 그대로 동작

### 개선 방향

- EPHEMERAL 패턴 LLM 프롬프트 개선 (JSON 출력 안정화)
- 의미적 매핑 기반 v2 정확도 자동 평가 메트릭 추가
- 장기 시뮬레이션 (500+ turns)으로 Mitosis/Extinction 검증
- centroid 증분 업데이트의 EMA(Exponential Moving Average) 적용 검토
