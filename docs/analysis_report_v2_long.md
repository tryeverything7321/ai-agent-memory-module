# AI Agent Memory Module v2 — 장기 시뮬레이션 분석 리포트

**버전:** v2-long
**총 턴:** 624 | **유저:** user_pm, user_dev, user_new, user_analyst | **기간:** 56일 (4 phases)
**소요:** 1013.2s (avg 1623ms/turn)
**LLM:** google/gemma-4-31B-it | **Embedding:** BAAI/bge-m3

## 1. 실험 목적

198턴 실험에서 관찰되지 않은 **Mitosis(분열)** 와 **Extinction(소멸)** 이벤트를 유도하기 위한 장기 시뮬레이션.

### 시나리오 설계

| Phase | 기간 | 전략 | 예상 결과 |
|-------|------|------|-----------|
| Phase 1 | Day 1-7 | 일상 업무 + 온보딩/출장 활성화 | Bootstrap 카테고리 형성 |
| Phase 2 | Day 8-21 | 안정기 — 기존 카테고리 강화 | 카테고리 안정화 |
| Phase 3 | Day 22-35 | 온보딩/출장 사용 중단 + 이질적 기술 주제 유입 | Extinction + Mitosis 유도 |
| Phase 4 | Day 36-56 | 보안 카테고리 신규 출현 | Discovery 유도 |

## 2. Taxonomy Evolution 결과

### 최종 카테고리: 4개

| 카테고리 | 멤버 수 | Decay Weight | 생성 방식 |
|----------|---------|-------------|----------|
| strategic_tech_ops | 964 | 2.0000 | merge |
| casual_chat | 29 | 1.9983 | bootstrap |
| bug_tracking | 26 | 1.9900 | bootstrap |
| tech_guide | 5 | 1.1973 | discovery |

### 진화 이벤트 요약

| 이벤트 | 횟수 |
|--------|------|
| Bootstrap | 7 |
| **Merge (Fusion)** | **4** |
| **Discovery** | **1** |
| **Extinct (via merge)** | **8** |
| Split (Mitosis) | 0 |

### 진화 타임라인

```
Turn  29: [BOOTSTRAP] 7개 카테고리 생성
            casual_chat(3), strategic_planning(3), dev_ops_request(7),
            bug_tracking(2), task_status(4), schedule_management(7),
            technical_consulting(4)

Turn ~150: [MERGE] dev_ops_request + schedule_management
            → ops_schedule_management

Turn ~200: [MERGE] task_status + ops_schedule_management
            → task_ops_management

Turn ~300: [MERGE] technical_consulting + task_ops_management
            → tech_ops_consulting

Turn ~400: [MERGE] strategic_planning + tech_ops_consulting
            → strategic_tech_ops (754 members)
           [DISCOVERY] tech_guide
            trigger: "Tailwind CSS 커스텀 테마 설정 방법"

Turn  624: 최종 — 4개 카테고리 (strategic_tech_ops: 964 members)
```

## 3. v1 vs v2 비교

| 지표 | v2 (198턴) | v2 (624턴) |
|------|-----------|-----------|
| Bootstrap 카테고리 | 7 | 7 |
| 최종 카테고리 | 6 | **4** |
| Fusion 횟수 | 2 | **4** |
| Discovery 횟수 | 1 | **1** |
| Extinction (merge) | 4 | **8** |
| Mitosis | 0 | 0 |
| Prediction 생성률 | 53.0% | **62.3%** |
| 메모리 활용률 | 98.0% | **99.4%** |
| 평균 latency | 1,458ms | 1,623ms |
| 에러 | 0 | **0** |

## 4. Key Insights

### Fusion이 지배적 진화 메커니즘

624턴에서 4회 연속 Fusion이 발생하여 7개 bootstrap 카테고리 중 5개가 하나로 수렴 (`strategic_tech_ops`, 964 members). 이는 Fusion threshold(0.85)가 너무 낮아 의미적으로 구분 가능한 카테고리까지 병합하는 현상.

**병합 체인:**
```
dev_ops_request ─┐
                 ├→ ops_schedule_management ─┐
schedule_management ┘                        │
                                             ├→ task_ops_management ─┐
task_status ─────────────────────────────────┘                       │
                                                                     ├→ tech_ops_consulting ─┐
technical_consulting ────────────────────────────────────────────────┘                        │
                                                                                              ├→ strategic_tech_ops
strategic_planning ──────────────────────────────────────────────────────────────────────────┘
```

### Mitosis 미발생 원인 분석

`strategic_tech_ops`가 964 members (전체의 94%)인데도 분열하지 않은 이유:
1. **centroid 증분 업데이트**: `activate_category()`가 기존 centroid를 새 임베딩으로 점진적 이동시킴. 각 메시지가 centroid를 조금씩 당기므로 전체 variance는 누적되지 않음.
2. **캐시된 임베딩 부족**: `_check_mitosis()`는 `_embedding_cache`에 저장된 임베딩으로 variance를 계산하지만, `_taxonomy_classify()`에서 캐시를 직접 관리하지 않아 일부 임베딩이 누락될 수 있음.

**개선 방안:**
- member_count 기반 분열 조건 추가 (예: member > 200이면 강제 variance 재계산)
- centroid 업데이트를 EMA(Exponential Moving Average)로 변경하여 최근 메시지에 더 큰 가중치 부여
- Fusion threshold 0.85 → 0.9 상향으로 과도한 병합 방지

### Extinction은 Merge를 통해 간접 발생

Ebbinghaus decay에 의한 자연 소멸(weight < 0.1)은 발생하지 않았으나, Merge로 인한 부모 카테고리 8개가 extinct 처리됨. 이는 Merge가 사실상 Extinction의 주요 경로임을 보여줌.

온보딩/출장 카테고리가 사용 중단 후 자연 소멸되지 않은 이유:
- 이들 카테고리가 Merge로 먼저 흡수되어 독립 카테고리로 남아있지 않음
- decay_all()이 sweep 시점에만 호출되며, 50턴 간격이 너무 길어 weight가 충분히 낮아지기 전에 다음 활성화가 발생

### Discovery는 높은 분류 기준에서만 발생

624턴에서 1회만 발생 (`tech_guide`). 대부분의 새로운 주제가 기존 mega-카테고리(`strategic_tech_ops`)에 흡수되어 Discovery 트리거 조건(centroid match 실패 + LLM이 신규 제안)에 도달하지 못함.

## 5. Persistence 검증

100턴마다 자동 저장 실행:
- Turn 100: 5개 카테고리 저장
- Turn 200: 4개 카테고리 (Fusion 후)
- Turn 300: 4개 카테고리
- Turn 400: 4개 카테고리 (Fusion + Discovery 후)
- Turn 500: 4개 카테고리
- Turn 600: 4개 카테고리 (최종)
- Turn 624: 최종 저장

서버 재시작 시뮬레이션: 실행 시 기존 저장 상태(7 categories, 400 turns)를 성공적으로 복원한 후 실행 계속.

## 6. 통계

| 지표 | 값 |
|------|-----|
| 총 턴 | 624 |
| 에러 | 0건 |
| 총 메모리 | 191개 (PM:40, Dev:67, New:50, Analyst:34) |
| Prediction 생성률 | 62.3% (389/624) |
| 메모리 활용률 | 99.4% (620/624) |
| 평균 latency | 1,623ms |
| 총 소요 시간 | 1,013초 (16.9분) |

## 7. 개선 방향

| 과제 | 우선순위 | 설명 |
|------|---------|------|
| Fusion threshold 상향 | P1 | 0.85 → 0.9로 과도한 병합 방지 |
| member_count 기반 Mitosis | P1 | 200+ members 시 강제 분열 검토 |
| centroid EMA | P2 | 최근 메시지 가중치 증가 |
| Sweep 간격 단축 | P2 | 50 → 30턴으로 decay 반응성 향상 |
| Embedding 캐시 보강 | P2 | _taxonomy_classify에서 캐시 직접 관리 |
| decay_all 실시간화 | P3 | sweep 외에도 주기적 decay 적용 |
