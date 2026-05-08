"""Graph-aware Selective Forgetting A/B 실험

Baseline(independent forgetting) vs Experiment(graph propagation forgetting) 비교.

실험 프로토콜:
  1. 시뮬레이션 데이터로 메모리 + 엔티티 그래프 구축
  2. 10건의 fact 변경 이벤트 삽입
  3. 변경 후 검색: top-5 결과에서 stale/valid 판별
  4. 지표: Stale Retrieval Rate, Valid Precision, F1

핵심: 동일한 메모리 상태에서 propagate=True/False만 다르게 실행하여 공정 비교.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Memory, Importance, Entity, Relation, Fact
from decay import DecayEngine
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.vector_store import VectorStore, MockEmbeddingProvider
from storage.memory_index import MemoryIndex


class KeywordEmbeddingProvider:
    """실험용 결정론적 임베딩 — 한국어 키워드 기반 bag-of-words 벡터

    동일 키워드를 포함하는 텍스트는 높은 cosine similarity를 가진다.
    MockEmbeddingProvider의 랜덤 벡터 대신 사용하여 검색 결과를 제어 가능하게 만든다.
    """

    def __init__(self, dim: int = 128):
        self._dim = dim
        self._vocab: dict[str, int] = {}  # keyword → dimension index
        self._next_idx = 0

    def _get_idx(self, word: str) -> int:
        if word not in self._vocab:
            self._vocab[word] = self._next_idx % self._dim
            self._next_idx += 1
        return self._vocab[word]

    def _tokenize(self, text: str) -> list[str]:
        """간단한 한국어 토크나이저 — 2-gram + 공백 분리"""
        tokens = text.split()
        # 2-gram 추가 (한국어 형태소 근사)
        for word in text.split():
            for i in range(len(word) - 1):
                tokens.append(word[i:i+2])
        return tokens

    async def embed(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import math
        vectors = []
        for text in texts:
            vec = [0.0] * self._dim
            tokens = self._tokenize(text)
            for token in tokens:
                idx = self._get_idx(token)
                vec[idx] += 1.0
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


# --- 실험용 시나리오 정의 ---

FACT_CHANGE_SCENARIOS = [
    {
        "id": "FC1",
        "desc": "프로젝트 담당자 변경",
        "entities": [
            ("프로젝트Alpha", "project"),
            ("김철수", "person"),
            ("이영희", "person"),
            ("판교사무실", "place"),
        ],
        "relations": [
            ("프로젝트Alpha", "김철수", "담당"),
            ("김철수", "판교사무실", "근무지"),
        ],
        "memories": [
            ("프로젝트Alpha의 마감일은 다음 주 금요일이다", "critical", "프로젝트Alpha"),
            ("김철수가 프로젝트Alpha를 담당하고 있다", "critical", "프로젝트Alpha,김철수"),
            ("김철수의 연락처는 010-1234-5678이다", "important", "김철수"),
            ("김철수는 판교사무실에서 근무한다", "important", "김철수,판교사무실"),
            ("이영희는 백엔드 개발자이다", "important", "이영희"),
        ],
        "old_fact_idx": 1,  # "김철수가 프로젝트Alpha를 담당하고 있다"
        "new_content": "이영희가 프로젝트Alpha를 담당하게 되었다",
        "stale_keywords": ["김철수", "담당"],
        "query": "프로젝트Alpha 담당자가 누구인가?",
    },
    {
        "id": "FC2",
        "desc": "미팅 일정 변경",
        "entities": [
            ("주간회의", "event"),
            ("박지훈", "person"),
            ("회의실A", "place"),
            ("회의실B", "place"),
        ],
        "relations": [
            ("주간회의", "박지훈", "참석"),
            ("주간회의", "회의실A", "장소"),
            ("박지훈", "회의실A", "예약"),
        ],
        "memories": [
            ("주간회의는 매주 수요일 10시에 열린다", "critical", "주간회의"),
            ("박지훈이 주간회의에 참석한다", "important", "주간회의,박지훈"),
            ("주간회의 장소는 회의실A이다", "important", "주간회의,회의실A"),
            ("박지훈이 회의실A를 예약했다", "important", "박지훈,회의실A"),
            ("회의실B는 30인 수용 가능하다", "ephemeral", "회의실B"),
        ],
        "old_fact_idx": 2,  # "주간회의 장소는 회의실A"
        "new_content": "주간회의 장소가 회의실B로 변경되었다",
        "stale_keywords": ["회의실A"],
        "query": "주간회의 장소가 어디인가?",
    },
    {
        "id": "FC3",
        "desc": "팀 구조 변경",
        "entities": [
            ("DevOps팀", "team"),
            ("최민수", "person"),
            ("인프라팀", "team"),
            ("AWS", "technology"),
        ],
        "relations": [
            ("최민수", "DevOps팀", "소속"),
            ("DevOps팀", "AWS", "담당"),
            ("최민수", "AWS", "전문"),
        ],
        "memories": [
            ("최민수는 DevOps팀 소속이다", "critical", "최민수,DevOps팀"),
            ("DevOps팀이 AWS 인프라를 담당한다", "important", "DevOps팀,AWS"),
            ("최민수는 AWS 전문가이다", "important", "최민수,AWS"),
            ("인프라팀이 신설될 예정이다", "important", "인프라팀"),
            ("DevOps팀은 5명으로 구성되어 있다", "ephemeral", "DevOps팀"),
        ],
        "old_fact_idx": 0,  # "최민수는 DevOps팀 소속"
        "new_content": "최민수가 인프라팀으로 이동했다",
        "stale_keywords": ["DevOps팀", "소속"],
        "query": "최민수는 어느 팀 소속인가?",
    },
    {
        "id": "FC4",
        "desc": "프로젝트 기술 스택 변경",
        "entities": [
            ("프로젝트Beta", "project"),
            ("React", "technology"),
            ("Vue", "technology"),
            ("정수현", "person"),
        ],
        "relations": [
            ("프로젝트Beta", "React", "사용"),
            ("정수현", "프로젝트Beta", "참여"),
            ("정수현", "React", "전문"),
        ],
        "memories": [
            ("프로젝트Beta는 React로 프론트엔드를 개발한다", "critical", "프로젝트Beta,React"),
            ("정수현이 프로젝트Beta에 참여하고 있다", "important", "정수현,프로젝트Beta"),
            ("정수현은 React 전문 개발자이다", "important", "정수현,React"),
            ("Vue는 대안 프레임워크로 검토 중이다", "ephemeral", "Vue"),
            ("프로젝트Beta 1차 릴리스는 4월 말이다", "critical", "프로젝트Beta"),
        ],
        "old_fact_idx": 0,  # "React로 프론트엔드 개발"
        "new_content": "프로젝트Beta가 Vue로 프론트엔드를 전환했다",
        "stale_keywords": ["React", "프론트엔드"],
        "query": "프로젝트Beta 프론트엔드 기술 스택은?",
    },
    {
        "id": "FC5",
        "desc": "담당 업무 변경",
        "entities": [
            ("한지민", "person"),
            ("데이터분석", "task"),
            ("ML엔지니어링", "task"),
            ("데이터팀", "team"),
        ],
        "relations": [
            ("한지민", "데이터분석", "담당"),
            ("한지민", "데이터팀", "소속"),
            ("데이터팀", "데이터분석", "책임"),
        ],
        "memories": [
            ("한지민은 데이터분석 업무를 담당한다", "critical", "한지민,데이터분석"),
            ("한지민은 데이터팀 소속이다", "important", "한지민,데이터팀"),
            ("데이터팀이 데이터분석 업무를 책임진다", "important", "데이터팀,데이터분석"),
            ("ML엔지니어링 포지션이 신설되었다", "important", "ML엔지니어링"),
            ("한지민은 Python과 SQL을 사용한다", "ephemeral", "한지민"),
        ],
        "old_fact_idx": 0,  # "데이터분석 담당"
        "new_content": "한지민이 ML엔지니어링 업무로 전환했다",
        "stale_keywords": ["데이터분석", "담당"],
        "query": "한지민의 담당 업무는?",
    },
    {
        "id": "FC6",
        "desc": "서버 환경 변경",
        "entities": [
            ("운영서버", "infrastructure"),
            ("AWS-Seoul", "region"),
            ("GCP-Tokyo", "region"),
            ("배포팀", "team"),
        ],
        "relations": [
            ("운영서버", "AWS-Seoul", "호스팅"),
            ("배포팀", "운영서버", "관리"),
            ("배포팀", "AWS-Seoul", "담당"),
        ],
        "memories": [
            ("운영서버는 AWS-Seoul 리전에 호스팅된다", "critical", "운영서버,AWS-Seoul"),
            ("배포팀이 운영서버를 관리한다", "important", "배포팀,운영서버"),
            ("배포팀이 AWS-Seoul 리전을 담당한다", "important", "배포팀,AWS-Seoul"),
            ("GCP-Tokyo는 DR 사이트로 검토 중이다", "ephemeral", "GCP-Tokyo"),
            ("운영서버 SLA는 99.9%이다", "important", "운영서버"),
        ],
        "old_fact_idx": 0,  # "AWS-Seoul 호스팅"
        "new_content": "운영서버가 GCP-Tokyo로 마이그레이션되었다",
        "stale_keywords": ["AWS-Seoul"],
        "query": "운영서버 호스팅 위치는?",
    },
    {
        "id": "FC7",
        "desc": "고객사 담당 변경",
        "entities": [
            ("고객사A", "client"),
            ("영업1팀", "team"),
            ("영업2팀", "team"),
            ("계약서", "document"),
        ],
        "relations": [
            ("영업1팀", "고객사A", "담당"),
            ("영업1팀", "계약서", "작성"),
            ("고객사A", "계약서", "관련"),
        ],
        "memories": [
            ("영업1팀이 고객사A를 담당하고 있다", "critical", "영업1팀,고객사A"),
            ("영업1팀이 고객사A 계약서를 작성했다", "important", "영업1팀,계약서"),
            ("고객사A 계약서는 6월 만료 예정이다", "critical", "고객사A,계약서"),
            ("영업2팀은 신규 고객 개발을 담당한다", "important", "영업2팀"),
            ("고객사A 연매출은 10억이다", "important", "고객사A"),
        ],
        "old_fact_idx": 0,  # "영업1팀이 담당"
        "new_content": "고객사A 담당이 영업2팀으로 이관되었다",
        "stale_keywords": ["영업1팀", "담당"],
        "query": "고객사A 담당팀은?",
    },
    {
        "id": "FC8",
        "desc": "프로젝트 일정 변경",
        "entities": [
            ("프로젝트Gamma", "project"),
            ("QA팀", "team"),
            ("4월릴리스", "milestone"),
            ("5월릴리스", "milestone"),
        ],
        "relations": [
            ("프로젝트Gamma", "4월릴리스", "마일스톤"),
            ("QA팀", "프로젝트Gamma", "테스트"),
            ("QA팀", "4월릴리스", "준비"),
        ],
        "memories": [
            ("프로젝트Gamma 릴리스는 4월 15일이다", "critical", "프로젝트Gamma,4월릴리스"),
            ("QA팀이 프로젝트Gamma를 테스트 중이다", "important", "QA팀,프로젝트Gamma"),
            ("QA팀이 4월릴리스를 준비하고 있다", "important", "QA팀,4월릴리스"),
            ("5월릴리스는 v2.0 예정이다", "ephemeral", "5월릴리스"),
            ("프로젝트Gamma는 모바일 앱이다", "important", "프로젝트Gamma"),
        ],
        "old_fact_idx": 0,  # "4월 15일 릴리스"
        "new_content": "프로젝트Gamma 릴리스가 5월 1일로 연기되었다",
        "stale_keywords": ["4월", "15일"],
        "query": "프로젝트Gamma 릴리스 일정은?",
    },
    {
        "id": "FC9",
        "desc": "보고 라인 변경",
        "entities": [
            ("신입사원A", "person"),
            ("팀장B", "person"),
            ("팀장C", "person"),
            ("기획팀", "team"),
        ],
        "relations": [
            ("신입사원A", "팀장B", "보고"),
            ("신입사원A", "기획팀", "소속"),
            ("팀장B", "기획팀", "리드"),
        ],
        "memories": [
            ("신입사원A는 팀장B에게 보고한다", "critical", "신입사원A,팀장B"),
            ("신입사원A는 기획팀 소속이다", "important", "신입사원A,기획팀"),
            ("팀장B가 기획팀을 리드한다", "important", "팀장B,기획팀"),
            ("팀장C는 개발팀 리더이다", "important", "팀장C"),
            ("신입사원A의 온보딩은 3월에 완료되었다", "ephemeral", "신입사원A"),
        ],
        "old_fact_idx": 0,  # "팀장B에게 보고"
        "new_content": "신입사원A가 팀장C에게 보고하게 되었다",
        "stale_keywords": ["팀장B", "보고"],
        "query": "신입사원A의 보고 라인은?",
    },
    {
        "id": "FC10",
        "desc": "도구/플랫폼 변경",
        "entities": [
            ("개발팀", "team"),
            ("Jira", "tool"),
            ("Linear", "tool"),
            ("PM장윤서", "person"),
        ],
        "relations": [
            ("개발팀", "Jira", "사용"),
            ("PM장윤서", "Jira", "관리"),
            ("PM장윤서", "개발팀", "PM"),
        ],
        "memories": [
            ("개발팀은 Jira로 이슈를 관리한다", "critical", "개발팀,Jira"),
            ("PM장윤서가 Jira를 관리한다", "important", "PM장윤서,Jira"),
            ("PM장윤서가 개발팀의 PM이다", "important", "PM장윤서,개발팀"),
            ("Linear를 도입 검토 중이다", "ephemeral", "Linear"),
            ("개발팀 스프린트는 2주 단위이다", "ephemeral", "개발팀"),
        ],
        "old_fact_idx": 0,  # "Jira로 이슈 관리"
        "new_content": "개발팀이 Linear로 이슈 관리 도구를 변경했다",
        "stale_keywords": ["Jira"],
        "query": "개발팀 이슈 관리 도구는?",
    },
]


async def build_scenario_state(
    scenario: dict,
    metadata_store: MetadataStore,
    graph_store: GraphStore,
    vector_store: VectorStore,
) -> list[Memory]:
    """시나리오에서 메모리 + 엔티티 그래프 구축"""
    memories = []
    importance_map = {
        "critical": Importance.critical,
        "important": Importance.important,
        "ephemeral": Importance.ephemeral,
    }

    base_time = datetime(2026, 3, 23, 9, 0, 0)

    for i, (content, imp_str, entity_names_str) in enumerate(scenario["memories"]):
        mem = Memory(
            user_id="experiment_user",
            content=content,
            importance=importance_map[imp_str],
            decay_lambda={
                "critical": 0.005,
                "important": 0.05,
                "ephemeral": 0.3,
            }[imp_str],
            decay_weight=1.0 - i * 0.05,  # 약간 다른 weight로 차별화
            created_at=base_time + timedelta(hours=i),
        )
        await metadata_store.save_memory(mem)
        await vector_store.store(mem.id, mem.content, mem.user_id)
        memories.append(mem)

        # entity → memory 연결
        for entity_name in entity_names_str.split(","):
            entity_name = entity_name.strip()
            graph_store.add_entity(entity_name, memory_id=mem.id)

    # noise 메모리 추가 — 검색 풀을 충분히 크게 (top-5 경쟁 유도)
    noise_contents = [
        "오늘 점심은 된장찌개를 먹었다",
        "내일 날씨가 맑을 예정이다",
        "회사 엘리베이터가 점검 중이다",
        "커피머신이 고장났다고 한다",
        "주차장 B구역이 공사 중이다",
        "올해 연차를 15일 사용했다",
        "사내 동호회 모집 공고가 올라왔다",
        "새로운 복지 제도가 시행된다",
        "이번 달 회식은 금요일이다",
        "사무실 온도가 너무 낮다는 민원이 있다",
        "인사팀에서 설문조사를 보냈다",
        "기술 블로그 글을 작성해야 한다",
        "보안 교육을 이번 주까지 이수해야 한다",
        "전사 타운홀 미팅이 다음 주에 있다",
        "신규 입사자 환영회를 계획 중이다",
    ]
    for j, content in enumerate(noise_contents):
        noise_mem = Memory(
            user_id="experiment_user",
            content=content,
            importance=Importance.ephemeral,
            decay_lambda=0.3,
            decay_weight=0.7 + j * 0.01,  # 0.7~0.85 범위
            created_at=base_time + timedelta(hours=len(scenario["memories"]) + j),
        )
        await metadata_store.save_memory(noise_mem)
        await vector_store.store(noise_mem.id, noise_mem.content, noise_mem.user_id)

    # relation 추가
    for src, tgt, rel_type in scenario["relations"]:
        if src not in graph_store.entity_graph:
            graph_store.add_entity(src)
        if tgt not in graph_store.entity_graph:
            graph_store.add_entity(tgt)
        graph_store.add_relation(src, tgt, rel_type)

    return memories


def evaluate_search_results(
    results: list,
    old_memory_id: str,
    stale_keywords: list[str],
    new_content: str,
) -> dict:
    """검색 결과 평가

    Returns:
        stale_count: stale 결과 수
        valid_count: valid 결과 수
        total: 전체 결과 수
        stale_rate: stale / total
        valid_precision: valid / total
        forgetting_accuracy: old_memory가 top-5에서 제외되었으면 1.0, 아니면 0.0
    """
    stale_count = 0
    valid_count = 0
    old_fact_found = False

    for result in results:
        mem = result.memory if hasattr(result, "memory") else result
        content = mem.content if hasattr(mem, "content") else str(mem)

        # 무효화된 원본 memory
        mem_id = mem.id if hasattr(mem, "id") else ""
        if mem_id == old_memory_id:
            stale_count += 1
            old_fact_found = True
            continue

        # stale keyword 포함 여부
        is_stale = any(kw in content for kw in stale_keywords)
        if is_stale:
            stale_count += 1
        else:
            valid_count += 1

    total = len(results) if results else 1
    stale_rate = stale_count / total
    valid_precision = valid_count / total

    # Forgetting accuracy (broad): 모든 stale 콘텐츠가 검색에서 제거된 비율
    # = 1 - stale_rate (원본 fact + 관련 stale fact 모두 포함)
    # No-Propagation에서는 관련 stale fact가 남아있어 이 값이 낮음
    forgetting_accuracy = 1.0 - stale_rate

    # F1: harmonic mean of (1-stale_rate) and valid_precision
    freshness = 1 - stale_rate
    if freshness + valid_precision > 0:
        f1 = 2 * freshness * valid_precision / (freshness + valid_precision)
    else:
        f1 = 0.0

    return {
        "stale_count": stale_count,
        "valid_count": valid_count,
        "total": total,
        "stale_rate": stale_rate,
        "valid_precision": valid_precision,
        "forgetting_accuracy": forgetting_accuracy,
        "f1": f1,
    }


async def run_single_scenario(
    scenario: dict,
    propagate: bool,
    embedding_provider=None,
    propagation_depth: int = 2,
    decay_per_hop: float = 0.5,
    prune_threshold: float = 0.3,
    semantic_filter: bool = False,
) -> dict:
    """단일 시나리오 실행 (baseline or experiment)"""
    # 독립 환경 생성
    metadata_store = MetadataStore(":memory:")
    await metadata_store.initialize()
    graph_store = GraphStore(metadata_store)
    provider = embedding_provider or KeywordEmbeddingProvider(dim=128)
    vector_store = VectorStore(
        embedding_provider=provider,
        use_qdrant=False,
    )
    await vector_store.initialize()
    memory_index = MemoryIndex(vector_store, metadata_store, graph_store)

    try:
        # 1. 메모리 + 그래프 구축
        memories = await build_scenario_state(
            scenario, metadata_store, graph_store, vector_store
        )

        # 2. fact 변경 실행
        engine = DecayEngine()
        old_mem = memories[scenario["old_fact_idx"]]

        # fact 무효화 (propagate 없이 — 별도로 파라미터 제어)
        await engine.update_fact(
            metadata_store,
            old_mem.id,
            scenario["new_content"],
            "experiment_user",
            propagate=False,
        )

        # graph propagation (실험군만)
        if propagate:
            await engine.propagate_invalidation(
                invalidated_memory_id=old_mem.id,
                graph_store=graph_store,
                metadata_store=metadata_store,
                propagation_depth=propagation_depth,
                decay_per_hop=decay_per_hop,
                semantic_filter=semantic_filter,
                new_content=scenario["new_content"] if semantic_filter else None,
            )

        # 프루닝
        pruned = await engine.prune(metadata_store, threshold=prune_threshold)

        # 3. 검색 실행
        results = await memory_index.search(
            query=scenario["query"],
            user_id="experiment_user",
            top_k=5,
        )

        # 4. 평가
        metrics = evaluate_search_results(
            results, old_mem.id, scenario["stale_keywords"], scenario["new_content"]
        )
        metrics["scenario_id"] = scenario["id"]
        metrics["scenario_desc"] = scenario["desc"]
        metrics["propagate"] = propagate

        # weight 변화 기록
        weight_changes = {}
        collateral_weight_loss = 0.0
        collateral_count = 0
        total_unrelated = 0

        for idx, mem in enumerate(memories):
            updated = await metadata_store.get_memory(mem.id)
            is_changed_fact = (idx == scenario["old_fact_idx"])

            if updated and abs(updated.decay_weight - mem.decay_weight) > 0.001:
                weight_changes[mem.id] = {
                    "content": mem.content[:40],
                    "before": round(mem.decay_weight, 4),
                    "after": round(updated.decay_weight, 4),
                    "is_target": is_changed_fact,
                }

            # collateral damage: 변경 대상이 아닌 메모리의 weight 손실
            if not is_changed_fact:
                total_unrelated += 1
                if updated:
                    loss = mem.decay_weight - updated.decay_weight
                    if loss > 0.001:
                        collateral_weight_loss += loss
                        collateral_count += 1

        # Collateral Damage Rate: 피해를 입은 무관 메모리 비율
        collateral_damage_rate = collateral_count / max(total_unrelated, 1)

        # Avg weight loss among damaged memories
        avg_collateral_loss = (
            collateral_weight_loss / collateral_count if collateral_count > 0 else 0.0
        )

        # Benefit-Damage Ratio
        forgetting_acc = metrics["forgetting_accuracy"]
        bdr = forgetting_acc / (1 + collateral_damage_rate)

        metrics["weight_changes"] = weight_changes
        metrics["pruned_count"] = pruned
        metrics["collateral_damage_rate"] = round(collateral_damage_rate, 4)
        metrics["collateral_count"] = collateral_count
        metrics["total_unrelated"] = total_unrelated
        metrics["avg_collateral_loss"] = round(avg_collateral_loss, 4)
        metrics["benefit_damage_ratio"] = round(bdr, 4)

        return metrics

    finally:
        await metadata_store.close()


async def run_experiment(
    propagation_depth: int = 2,
    decay_per_hop: float = 0.5,
    prune_threshold: float = 0.3,
    label: str = "",
) -> dict:
    """3-arm 실험: Baseline vs Naive Propagation vs Semantic Propagation"""
    print("=" * 70)
    print(f"Graph-aware Selective Forgetting — 3-Arm 실험 {label}")
    print(f"  depth={propagation_depth}, decay_per_hop={decay_per_hop}, prune={prune_threshold}")
    print("=" * 70)

    baseline_results = []
    naive_results = []
    semantic_results = []

    for scenario in FACT_CHANGE_SCENARIOS:
        # Arm 1: Baseline (propagate=False)
        baseline = await run_single_scenario(
            scenario, propagate=False,
            propagation_depth=propagation_depth,
            decay_per_hop=decay_per_hop,
            prune_threshold=prune_threshold,
        )
        baseline_results.append(baseline)

        # Arm 2: Naive Graph Propagation
        naive = await run_single_scenario(
            scenario, propagate=True, semantic_filter=False,
            propagation_depth=propagation_depth,
            decay_per_hop=decay_per_hop,
            prune_threshold=prune_threshold,
        )
        naive_results.append(naive)

        # Arm 3: Semantic-aware Graph Propagation
        semantic = await run_single_scenario(
            scenario, propagate=True, semantic_filter=True,
            propagation_depth=propagation_depth,
            decay_per_hop=decay_per_hop,
            prune_threshold=prune_threshold,
        )
        semantic_results.append(semantic)

    def aggregate(results):
        n = len(results)
        return {
            "avg_stale_rate": sum(r["stale_rate"] for r in results) / n,
            "avg_valid_precision": sum(r["valid_precision"] for r in results) / n,
            "avg_f1": sum(r["f1"] for r in results) / n,
            "avg_forgetting_accuracy": sum(r["forgetting_accuracy"] for r in results) / n,
            "avg_collateral_damage_rate": sum(r["collateral_damage_rate"] for r in results) / n,
            "avg_collateral_count": sum(r["collateral_count"] for r in results) / n,
            "avg_benefit_damage_ratio": sum(r["benefit_damage_ratio"] for r in results) / n,
        }

    baseline_agg = aggregate(baseline_results)
    naive_agg = aggregate(naive_results)
    semantic_agg = aggregate(semantic_results)

    # --- 핵심 지표 요약 (Phase 1-1 포맷) ---
    print(f"\n{'='*75}")
    print(f"  3-Arm Comparison: No-Propagation vs BFS vs Attr-Aware")
    print(f"{'='*75}")

    metrics_display = [
        ("Forgetting Accuracy", "avg_forgetting_accuracy", True),
        ("Collateral Damage Rate", "avg_collateral_damage_rate", False),
        ("Benefit-Damage Ratio", "avg_benefit_damage_ratio", True),
        ("Stale Rate", "avg_stale_rate", False),
        ("Valid Precision", "avg_valid_precision", True),
        ("F1", "avg_f1", True),
    ]

    print(f"\n{'Metric':<28} {'No-Prop':>10} {'BFS':>10} {'Attr-Aware':>12} {'Δ(A-N)':>10}")
    print("-" * 75)
    for display_name, metric_name, higher_better in metrics_display:
        b = baseline_agg[metric_name]
        n = naive_agg[metric_name]
        s = semantic_agg[metric_name]
        delta = s - n
        if higher_better:
            good = "✓" if delta > 0 else ("=" if abs(delta) < 0.001 else "")
        else:
            good = "✓" if delta < 0 else ("=" if abs(delta) < 0.001 else "")
        print(f"  {display_name:<26} {b:>10.4f} {n:>10.4f} {s:>12.4f} {delta:>+10.4f} {good}")

    # 시나리오별 상세
    print(f"\n{'ID':<6} {'B-Forg':>7} {'N-Forg':>7} {'S-Forg':>7} {'B-CDR':>7} {'N-CDR':>7} {'S-CDR':>7} {'S-BDR':>7}")
    print("-" * 70)
    for b, n, s in zip(baseline_results, naive_results, semantic_results):
        print(
            f"{b['scenario_id']:<6} "
            f"{b['forgetting_accuracy']:>7.1%} "
            f"{n['forgetting_accuracy']:>7.1%} "
            f"{s['forgetting_accuracy']:>7.1%} "
            f"{b['collateral_damage_rate']:>7.1%} "
            f"{n['collateral_damage_rate']:>7.1%} "
            f"{s['collateral_damage_rate']:>7.1%} "
            f"{s['benefit_damage_ratio']:>7.3f}"
        )

    return {
        "config": {
            "propagation_depth": propagation_depth,
            "decay_per_hop": decay_per_hop,
            "prune_threshold": prune_threshold,
        },
        "baseline": {"aggregate": baseline_agg, "scenarios": baseline_results},
        "naive": {"aggregate": naive_agg, "scenarios": naive_results},
        "semantic": {"aggregate": semantic_agg, "scenarios": semantic_results},
    }


async def run_ablation():
    """Ablation study — 파라미터 조합별 성능 비교"""
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  Graph-aware Selective Forgetting — Ablation Study              ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")

    # 설계 문서 ablation 변수
    depths = [1, 2, 3]
    decay_hops = [0.3, 0.5, 0.7]
    prune_threshold = 0.3

    all_results = []
    for depth in depths:
        for dph in decay_hops:
            result = await run_experiment(
                propagation_depth=depth,
                decay_per_hop=dph,
                prune_threshold=prune_threshold,
                label=f"[d={depth}, dph={dph}]",
            )
            all_results.append(result)
            print()

    # --- Ablation 종합 ---
    print("\n" + "=" * 70)
    print("ABLATION SUMMARY (3-Arm: Baseline / Naive / Semantic)")
    print("=" * 70)
    print(f"\n{'depth':>5} {'dph':>5} {'B-Forg':>7} {'N-Forg':>7} {'S-Forg':>7} {'N-CDR':>6} {'S-CDR':>6} {'S-BDR':>7} {'S-F1':>6} {'Best':>5}")
    print("-" * 75)

    best_bdr = -999
    best_config = None

    for r in all_results:
        cfg = r["config"]
        ba = r["baseline"]["aggregate"]
        na = r["naive"]["aggregate"]
        sa = r["semantic"]["aggregate"]
        is_best = ""

        if sa["avg_benefit_damage_ratio"] > best_bdr:
            best_bdr = sa["avg_benefit_damage_ratio"]
            best_config = cfg
            is_best = "★"

        print(
            f"{cfg['propagation_depth']:>5} "
            f"{cfg['decay_per_hop']:>5.1f} "
            f"{ba['avg_forgetting_accuracy']:>7.1%} "
            f"{na['avg_forgetting_accuracy']:>7.1%} "
            f"{sa['avg_forgetting_accuracy']:>7.1%} "
            f"{na['avg_collateral_damage_rate']:>6.1%} "
            f"{sa['avg_collateral_damage_rate']:>6.1%} "
            f"{sa['avg_benefit_damage_ratio']:>7.3f} "
            f"{sa['avg_f1']:>6.4f} "
            f"{is_best:>5}"
        )

    print(f"\n최적 설정: depth={best_config['propagation_depth']}, "
          f"decay_per_hop={best_config['decay_per_hop']}, "
          f"Best BDR={best_bdr:.3f}")

    # 결과 저장
    output = {
        "timestamp": datetime.now().isoformat(),
        "ablation_results": all_results,
        "best_config": best_config,
        "best_bdr": best_bdr,
    }

    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "graph_forgetting_ablation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n결과 저장: {output_path}")
    return output


if __name__ == "__main__":
    import sys
    if "--ablation" in sys.argv:
        asyncio.run(run_ablation())
    else:
        asyncio.run(run_experiment())
