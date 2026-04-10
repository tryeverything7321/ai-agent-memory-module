# Adversarial Forgetting Workshop Paper — 설계서

## 개요

Graph-based selective forgetting의 collateral damage를 3개 축으로 확장 검증:
1. Scale 트렌드 (6K→32K→64K)
2. Cross-task 영향 (Accurate_Retrieval)
3. Adversarial exploitation (hub entity 공격)

## 논문 Contribution

| # | Contribution | 실험 |
|---|-------------|------|
| C1 | Collateral damage 정량 발견 + scale 트렌드 | FactConsolidation 6K/32K/64K |
| C2 | Cross-task 영향 — forgetting이 retrieval 정확도 오염 | Accurate_Retrieval |
| C3 | Adversarial hub exploitation 공격 시나리오 | 자체 adversarial benchmark |
| C4 | Attribute-aware defense 전체 실험 방어 효과 | C1~C3 통합 |

## 실험 A: 64K Scale 확장

- benchmark_runner.py --sub_dataset factconsolidation_mh_64k
- collateral damage 분석: hub degree 변화, valid memory decay 비율
- 예상: hub degree superlinear 증가, damage > 80%

## 실험 B: Accurate_Retrieval Cross-Task

### 가설
BFS propagation의 collateral damage가 conflict resolution뿐 아니라
retrieval 정확도에도 부정적 영향을 미친다.

### 방법
1. Accurate_Retrieval 데이터 로드 (eventqa 또는 longmemeval)
2. 정상 memorize 후 임의의 fact update → propagation 발동
3. 비교: propagation OFF vs BFS vs Attribute-aware
4. 측정: retrieval QA의 EM/F1 변화

### 구현
- experiments/benchmark_accurate_retrieval.py (신규)
- benchmark_adapter.py에 Accurate_Retrieval 모드 추가

## 실험 C: Adversarial Hub Exploitation

### 공격 시나리오
1. 정상 fact N개 memorize
2. hub entity 식별 (entity_graph degree top-K)
3. 공격자가 hub entity 관련 fake fact 주입
4. 시스템이 conflict 감지 → forgetting 발동
5. 측정:
   - Damage ratio: decay된 valid memory / 전체 valid memory
   - Kill ratio: weight < 0.1인 memory / 전체
   - QA accuracy drop: 공격 전후 EM 차이

### 변수
- 공격 대상: degree top-1 / top-3 / top-5 hub entity
- 공격 수: 1 / 3 / 5 fake facts
- Context: 6K, 32K
- 방어: BFS vs Attribute-aware

### 구현
- experiments/adversarial_attack.py (신규)
- 기존 benchmark_adapter.py의 memorize/query 파이프라인 재활용

## 분석 및 산출물

### experiments/analyze_all.py
- 전체 결과 통합 분석
- Scale 트렌드 표 (6K/32K/64K hub degree, damage ratio)
- Cross-task 비교 표
- Adversarial attack 결과 표
- Defense 효과 요약

### docs/paper_draft_v2.md
- Workshop format (4-6쪽)
- 기존 paper_draft_v1.md 기반 확장

## 인프라

| 항목 | 값 |
|------|-----|
| LLM | google/gemma-4-31B-it (DooGPU reserved3) |
| Embedding | BAAI/bge-m3, 1024-dim (DooGPU reserved9) |
| Vector DB | in-memory fallback |
| Metadata | SQLite :memory: |
| Graph | NetworkX in-memory |
| Benchmark | ai-hyz/MemoryAgentBench (HuggingFace) |

## 성공 기준

- 64K collateral damage 측정 완료
- Accurate_Retrieval에서 BFS의 부정적 영향 확인
- Adversarial attack이 BFS에서 damage ratio > 50% 달성
- Attribute-aware가 전 실험에서 damage 감소 입증
- 전체 결과를 paper_draft_v2.md로 정리

## 실행 우선순위

1. 64K FactConsolidation (기존 인프라 즉시 실행 가능)
2. Adversarial attack 실험 (신규, 핵심 contribution)
3. Accurate_Retrieval cross-task (adapter 확장 필요)
4. 통합 분석 + 논문 v2
