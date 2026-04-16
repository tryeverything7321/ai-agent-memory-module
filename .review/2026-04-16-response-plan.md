# Adversarial Review 대응 계획 — 2026-04-16
**기반**: `.review/2026-04-16-adversarial-review.md`의 Critical/Major 이슈
**우선순위**: Phase 1 (필수) → Phase 2 (문헌) → Phase 3 (텍스트) → Phase 4 (추가 실험)

---

## Phase 1: 핵심 실험 추가 (Critical 해소)

### 1-1. Forgetting Accuracy 3자 비교 [C1 해소] — 최우선

**문제**: BFS의 피해만 측정하고 이득(forgetting accuracy)을 미측정. "전파 안 하면 되지 않나?"에 답 없음.

**실험 설계**:
- 3-Arm: No-Propagation vs BFS vs Attr-Aware
- 지표 2개 동시 측정:
  - **Forgetting Accuracy**: old_memory_id가 top-5 검색 결과에서 제외된 비율
  - **Collateral Damage**: 무관한 메모리의 weight 감소율
- **Benefit-Damage Ratio**: `Forgetting_Accuracy / (1 + Collateral_Damage_Rate)`

**수정 파일**:
- `experiments/graph_forgetting.py` (lines 426-479): `evaluate_search_results()`에 forgetting_accuracy 추가
- `experiments/benchmark_runner.py`: 3-way comparison 함수 추가

**예상 결과** (논문의 서사를 살리는 방향):
```
No-Propagation:  Forgetting ~45%, Damage 0%   → stale fact 방치
BFS:             Forgetting ~92%, Damage ~18%  → 효과적이나 파괴적  
Attr-Aware:      Forgetting ~95%, Damage ~2%   → 최적 balance
```

**예상 소요**: 2-3일 (코드 수정) + 1-2일 (실험 실행)

---

### 1-2. Scale-free → Heavy-tailed 전환 [C5 해소]

**문제**: 64K에서 KS test가 power-law 기각 ($p=0.009$), log-normal과 구분 불가.

**대응**:
- 본문 전체에서 "scale-free" → "heavy-tailed" 전환
- Finding 4 재작성: power-law는 6K/16K에서만 성립, 64K에서는 기각됨을 솔직하게 인정
- Percolation theory 논증을 heavy-tail 조건으로 재구성 (Molloy-Reed criterion은 heavy-tail에서도 적용 가능)
- Table 4 caption 수정

**수정 파일**: `paper/main.tex` (Finding 4, Abstract, Conclusion 등 5-6곳)

**예상 소요**: 반나절

---

### 1-3. Algorithm 1 의사코드 수정 [C8 해소]

**문제**: fact_registry 참조 누락, "downstream successors of e" 미정의.

**대응**: 실제 코드(`decay.py`)와 일치하도록 의사코드 재작성
- fact_registry lookup 명시
- subject_key 기반 필터링 로직 추가
- 재귀 입력의 fact/memory 혼용 해소

**수정 파일**: `paper/main.tex` (Algorithm 1, lines 470-492)

**예상 소요**: 반나절

---

## Phase 2: 문헌 보강

### 2-1. Kumiho 인용 + 차별화 [C3, C7 해소]

**핵심 차별점** (연구 결과):
| | Kumiho (Park 2026) | 본 논문 |
|---|---|---|
| 그래프 | Typed (6종 edge) | Untyped (co-occurrence) |
| 전파 | **하지 않음** (Relevance 공리) | BFS 분석 + Attr-Aware 제안 |
| 검증 | 49개 시나리오, 논리적 | 6K-64K, 실증적 |
| 적대적 분석 | 없음 | Hub exploitation |
| 토폴로지 | 없음 | Heavy-tailed degree 분석 |

**Kumiho는 전파 자체를 하지 않는다** — 문제를 "회피"한 것이지 "해결"한 것이 아님.
Typed edge 전제도 현실 시스템(Mem0, Zep)에서는 성립하지 않음.

**추가할 텍스트 위치**:
- Related Work: "Formal Belief Revision Approaches" 단락 신설
- Background: AGM 프레임워크 2-3문장 소개

**references.bib 추가**:
```bibtex
@article{park2026kumiho,
  title={Kumiho: Graph-Native Cognitive Memory for {AI} Agents},
  author={Park, ...},
  journal={arXiv preprint arXiv:2603.17244},
  year={2026},
}
```

---

### 2-2. MaRS + Forgetting 문헌 확장 [C6 해소]

**핵심 차별점**: 
- MaRS = **retention-side propagation** (삭제 시 의존 노드 보호)
- 본 논문 = **invalidation-side propagation** (변경 시 오류 전파)
- 두 방향은 **상보적**

**3단계 forgetting 분류 제안**:
1. **Budget-driven forgetting**: MaRS, Mnemosyne, Fofadiya & Tiwari → 메모리 용량 관리
2. **Fact-level invalidation**: Zep/Graphiti, MemMachine → 개별 사실 무효화
3. **Graph-based invalidation propagation** (본 논문) → 연쇄 무효화

**references.bib 추가**:
```bibtex
@article{mars_2025, ...}       % MaRS: Forgetful but Faithful
@article{fofadiya_2026, ...}   % Relevance-guided budgeted forgetting
@article{memmachine_2026, ...} % MemMachine
```

---

### 2-3. 그래프 공격 문헌 추가 [M8 해소]

누락된 논문:
- KEPo (arXiv:2603.11501) — GraphRAG poisoning
- LogicPoison (arXiv:2604.02954) — 논리적 그래프 공격
- KG-RAG Poisoning (arXiv:2507.08862) — 소수 triple 주입

Related Work "Memory-specific adversarial attacks" 단락에 추가.
차별점: 기존은 retrieval 조작, 우리는 maintenance mechanism 자체를 exploit.

---

## Phase 3: 텍스트 수정

### 3-1. "Inevitable" 완화 [M2 해소]
- line 101: "architecturally inevitable" → "architecturally plausible"
- line 558: 동일
- line 650: 동일
- Abstract의 "natural"과 통일

### 3-2. Contribution 프레이밍 전환 [C2 부분 해소]
현재: "novel attack", "first demonstration"
변경: "systematic risk quantification", "empirical characterization"
- "crash testing" 비유를 Contributions 목록에서도 일관되게 사용

### 3-3. 용어 통일 [M10 해소]
- "damage/decay/collateral damage" → 정의 섹션에서 한 번 정리
- "fact/memory/knowledge" → "memory" 또는 "fact"로 통일
- Section 3 시작부에 용어 정의 표 추가

### 3-4. 선정적 표현 완화
- "weaponize" → "exploit"
- "becomes the weapon" → "leverages the system's own maintenance mechanism"

### 3-5. 중복 제거
- Intro/Background 시스템 이중 기술 → Intro에서는 gap만, Background에서 상세
- Transportation 비유 5회 → 3회로 축소 (Intro, Background, Conclusion)
- "co-occurrence ≠ causal" 4회 → 2회 (Intro, Conclusion)

### 3-6. 긴 문장 분리
- Finding 4 (100단어+) → 3-4문장
- Finding 9 (100단어+) → 3-4문장
- Abstract 2번째 데이터 문장 (55단어) → 2문장

---

## Phase 4: 추가 실험 (여력 시)

### 4-1. No-propagation Baseline forgetting accuracy [M1 해소]
- Phase 1-1에서 함께 수행

### 4-2. 2번째 벤치마크 [C4 부분 해소]
- MemoryArena 또는 LongMemEval
- 최소 1개 추가 벤치마크에서 주요 결과 재현

### 4-3. Depth/Decay Sensitivity Analysis 본문 승격
- 현재 adversarial context에서만 depth 1-4 비교 (Table 5)
- Organic damage에서도 depth sensitivity 추가

### 4-4. Subject-key Matching Precision/Recall [M3 해소]
- 100개 샘플에서 수동 검증
- Appendix에 보고

### 4-5. Defense Rate 공식 명시 [M7 해소]
- `1 - (Attr_Damage / BFS_Damage)` 공식 + 한계 논의
- "No-propagation이 100% defense rate" 문제 인정 + 별도 지표 제안

---

## 실행 순서 및 일정 (권장)

| 순서 | 작업 | 예상 소요 | 의존성 |
|------|------|----------|--------|
| 1 | Phase 1-2: scale-free → heavy-tailed | 반나절 | 없음 |
| 2 | Phase 1-3: Algorithm 1 수정 | 반나절 | 없음 |
| 3 | Phase 3 전체: 텍스트 수정 | 1일 | 없음 |
| 4 | Phase 2 전체: 문헌 보강 | 1일 | 없음 |
| 5 | Phase 1-1: Forgetting accuracy 실험 | 3-5일 | 코드 수정 필요 |
| 6 | Phase 4: 추가 실험 | 1-2주 | Phase 1-1 완료 후 |

**순서 1-4는 텍스트 작업으로 즉시 시작 가능.**
**순서 5는 코드 작업으로 별도 세션 권장.**

---

## 리뷰어 예상 반박 대응 매트릭스

| 리뷰어 공격 | 현재 상태 | 대응 후 |
|------------|----------|---------|
| "Straw man — 아무도 안 쓰는 BFS를 공격" | "inevitable" 반복 | "plausible" + forgetting accuracy로 전파 필요성 입증 |
| "Attr-Aware = belief revision 재발명" | Kumiho 미인용 | Kumiho 인용 + typed vs untyped 차별화 |
| "단일 벤치마크" | 인정만 함 | (Phase 4에서) 2번째 벤치마크 추가 |
| "Scale-free 모순" | "consistent with" 완화 | "heavy-tailed"로 전환 + 솔직한 인정 |
| "그냥 전파 안 하면 됨" | 답 없음 | Forgetting accuracy 45% vs 95% 데이터 |
| "Forgetting 문헌 부족" | Mnemosyne만 인용 | MaRS + 3단계 분류 + 6편 추가 |
