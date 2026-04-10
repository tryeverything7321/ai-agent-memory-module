"""Decay Engine — Mnemosyne 스타일 Ebbinghaus 망각 곡선

수식: w(t) = e^(-λt) * (1 + boost * access_count)
  - 곱셈형: boost가 있어도 시간이 지나면 모든 메모리는 결국 감쇠
  - λ: 감쇠율 (ephemeral=0.3, important=0.05, critical=0.005)
  - boost: 반복 접근 시 가중치 부스트 (기본 0.05)

통합 모듈: calculator + booster + pruner + updater
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from collections import deque
from typing import TYPE_CHECKING

from config import settings
from models import Memory, Importance

if TYPE_CHECKING:
    from storage.graph_store import GraphStore
    from storage.metadata_store import MetadataStore


class DecayEngine:
    """메모리 감쇠 계산, 프루닝, 팩트 갱신"""

    def __init__(self, boost_factor: float = None):
        self._boost = boost_factor or settings.decay_boost_factor

    def calculate_weight(
        self,
        lambda_val: float,
        days_elapsed: float,
        access_count: int = 0,
        boost_factor: float = None,
    ) -> float:
        """
        w(t) = e^(-λt) * (1 + boost * access_count)

        Args:
            lambda_val: 감쇠율 (0 < λ ≤ 1)
            days_elapsed: 생성 이후 경과 일수
            access_count: 접근 횟수
            boost_factor: 커스텀 boost (기본: config.decay_boost_factor)
        """
        if lambda_val < 0 or lambda_val > 1:
            raise ValueError(f"λ must be in [0, 1], got {lambda_val}")

        boost = boost_factor or self._boost
        base_decay = math.exp(-lambda_val * days_elapsed)
        boosted = base_decay * (1 + boost * access_count)
        return boosted

    def get_lambda_for_importance(self, importance: Importance) -> float:
        """중요도별 λ 값 반환"""
        return {
            Importance.ephemeral: settings.decay_lambda_ephemeral,
            Importance.important: settings.decay_lambda_important,
            Importance.critical: settings.decay_lambda_critical,
        }[importance]

    def compute_memory_weight(self, memory: Memory) -> float:
        """Memory 객체의 현재 decay weight 계산"""
        now = datetime.now()
        days_elapsed = (now - memory.created_at).total_seconds() / 86400
        return self.calculate_weight(
            lambda_val=memory.decay_lambda,
            days_elapsed=days_elapsed,
            access_count=memory.access_count,
        )

    # --- 프루닝 ---

    async def prune(
        self, metadata_store, threshold: float = None
    ) -> int:
        """임계치 미달 메모리 일괄 삭제"""
        threshold = threshold or settings.decay_prune_threshold
        return await metadata_store.delete_memories_below_threshold(threshold)

    # --- 팩트 갱신 ---

    async def update_fact(
        self,
        metadata_store,
        old_memory_id: str,
        new_content: str,
        user_id: str,
        graph_store: "GraphStore | None" = None,
        propagate: bool = False,
    ) -> Memory:
        """기존 팩트 무효화 + 새 팩트 생성 + (선택) 그래프 전파"""
        await metadata_store.invalidate_memory(old_memory_id)

        new_memory = Memory(
            user_id=user_id,
            content=new_content,
            importance=Importance.critical,
            decay_lambda=settings.decay_lambda_critical,
        )
        await metadata_store.save_memory(new_memory)

        if propagate and graph_store is not None:
            await self.propagate_invalidation(
                old_memory_id, graph_store, metadata_store
            )

        return new_memory

    # --- Graph-aware Selective Forgetting ---

    async def propagate_invalidation(
        self,
        invalidated_memory_id: str,
        graph_store: "GraphStore",
        metadata_store: "MetadataStore",
        propagation_depth: int = 2,
        decay_per_hop: float = 0.5,
        semantic_filter: bool = False,
        new_content: str | None = None,
        subject_key: str | None = None,
        fact_registry: dict[str, str] | None = None,
        degree_cap: int | None = None,
        propagation_stats: dict | None = None,
    ) -> list[str]:
        """교통 네트워크 link failure propagation 적용.

        수식: w_final(m) = w(t,m) * adjusted_factor
          base_factor = decay_per_hop ^ hop_distance
          adjusted_factor = 1 - (1 - base_factor) / in_degree
          - hop_distance: invalidated_memory에서 m까지의 graph 최단 거리
          - in_degree=1: adjusted = base_factor (full penalty)
          - in_degree>1: 대안 경로가 있으므로 penalty가 1/in_degree로 축소
            (교통 네트워크에서 우회로가 있는 링크는 폐쇄 영향이 작음)

        Attribute-aware propagation:
          subject_key(예: "Russia:president")가 주어지면, 동일 subject entity의
          동일 attribute를 가진 메모리만 전파 대상으로 삼는다.
          교통공학 비유: 서울→부산 구간 폐쇄 시 서울→인천 경로는 영향 없음.

        Returns: 영향 받은 memory_id 리스트
        """
        if propagation_depth <= 0:
            return []

        # --- Attribute-aware 모드: subject_key 기반 직접 타겟팅 ---
        if subject_key and fact_registry is not None:
            return await self._propagate_attribute_aware(
                invalidated_memory_id=invalidated_memory_id,
                graph_store=graph_store,
                metadata_store=metadata_store,
                subject_key=subject_key,
                fact_registry=fact_registry,
                propagation_depth=propagation_depth,
                decay_per_hop=decay_per_hop,
            )

        # --- Legacy 모드: BFS 기반 전파 (자체 실험용 유지) ---
        # --- 1단계: invalidated memory가 연결된 source entity 찾기 ---
        source_entities = set()
        for node_id in graph_store.entity_graph.nodes:
            memory_ids = graph_store.get_memory_ids_for_entity(node_id)
            if invalidated_memory_id in memory_ids:
                source_entities.add(node_id)

        if not source_entities:
            return []

        # --- 1.5단계: semantic filter — 변경된 entity만 추출 ---
        changed_keywords: set[str] = set()
        if semantic_filter:
            source_mem = await metadata_store.get_memory(invalidated_memory_id)
            if source_mem:
                old_entities = set()
                for entity_id in graph_store.entity_graph.nodes:
                    if entity_id in source_mem.content:
                        old_entities.add(entity_id)

                if new_content:
                    new_entities = set()
                    for entity_id in graph_store.entity_graph.nodes:
                        if entity_id in new_content:
                            new_entities.add(entity_id)
                    changed_keywords = old_entities - new_entities
                else:
                    changed_keywords = old_entities

                if not changed_keywords:
                    changed_keywords = old_entities

        # --- 2단계: BFS로 hop별 entity 수집 ---
        hop_map: dict[str, int] = {}
        visited = set(source_entities)
        queue = deque()

        for src in source_entities:
            for neighbor in graph_store.entity_graph.successors(src):
                if neighbor not in visited:
                    queue.append((neighbor, 1))
            for neighbor in graph_store.entity_graph.predecessors(src):
                if neighbor not in visited:
                    queue.append((neighbor, 1))

        while queue:
            entity_id, hop = queue.popleft()
            if entity_id in visited or hop > propagation_depth:
                continue

            # degree_cap: 고차수 노드 전파 차단 (방어 baseline)
            if degree_cap is not None:
                entity_degree = graph_store.entity_graph.degree(entity_id)
                if entity_degree > degree_cap:
                    continue

            visited.add(entity_id)
            hop_map[entity_id] = hop

            if hop < propagation_depth:
                for neighbor in graph_store.entity_graph.successors(entity_id):
                    if neighbor not in visited:
                        queue.append((neighbor, hop + 1))
                for neighbor in graph_store.entity_graph.predecessors(entity_id):
                    if neighbor not in visited:
                        queue.append((neighbor, hop + 1))

        # --- 3단계: 영향받은 memory weight 갱신 ---
        affected_ids: list[str] = []

        # propagation_stats: hop별 damage 통계 수집 (실험 분석용, 선택적)
        if propagation_stats is not None:
            propagation_stats.setdefault("per_hop", {})
            propagation_stats.setdefault("entities_per_hop", {})

        for entity_id, hop in hop_map.items():
            memory_ids = graph_store.get_memory_ids_for_entity(entity_id)
            if not memory_ids:
                continue

            in_degree = graph_store.entity_graph.in_degree(entity_id)
            in_degree = max(in_degree, 1)

            base_factor = decay_per_hop ** hop
            adjusted_factor = 1 - (1 - base_factor) / in_degree

            if propagation_stats is not None:
                hop_key = str(hop)
                propagation_stats["entities_per_hop"].setdefault(hop_key, 0)
                propagation_stats["entities_per_hop"][hop_key] += 1

            memories = await metadata_store.get_memories_by_ids(list(memory_ids))
            for mem in memories:
                if mem.id == invalidated_memory_id:
                    continue

                if semantic_filter and changed_keywords:
                    if not any(kw in mem.content for kw in changed_keywords):
                        continue

                old_weight = mem.decay_weight
                new_weight = mem.decay_weight * adjusted_factor
                new_weight = max(new_weight, 0.0)
                await metadata_store.update_decay_weight(mem.id, new_weight)
                affected_ids.append(mem.id)

                # hop별 damage 통계 기록
                if propagation_stats is not None:
                    hop_key = str(hop)
                    hop_stats = propagation_stats["per_hop"].setdefault(
                        hop_key, {"memories_affected": 0, "total_weight_loss": 0.0,
                                  "killed": 0, "weight_drops": []}
                    )
                    hop_stats["memories_affected"] += 1
                    weight_loss = old_weight - new_weight
                    hop_stats["total_weight_loss"] += weight_loss
                    hop_stats["weight_drops"].append(round(weight_loss, 4))
                    if new_weight < 0.1:
                        hop_stats["killed"] += 1

        return affected_ids

    async def _propagate_attribute_aware(
        self,
        invalidated_memory_id: str,
        graph_store: "GraphStore",
        metadata_store: "MetadataStore",
        subject_key: str,
        fact_registry: dict[str, str],
        propagation_depth: int = 2,
        decay_per_hop: float = 0.5,
    ) -> list[str]:
        """Attribute-aware selective propagation.

        subject_key (예: "Russia:president") 에서 entity 부분("Russia")을 추출하고,
        동일 entity를 subject로 가지면서 다른 attribute인 fact에는 전파하지 않는다.

        대신, invalidated fact의 **값(object)** 을 subject로 가지는 downstream
        fact chain으로만 전파한다.
        예: "The president of Russia is Putin" 무효화 →
            "Putin was born in Leningrad" 도 decay (Putin이 더 이상 현 대통령이 아니므로)
            "The capital of Russia is Moscow" 는 건드리지 않음

        교통공학 비유: 방향성 있는 link failure — 상류 링크 폐쇄가
        하류 트래픽에만 영향을 주는 것과 동일.
        """
        affected_ids: list[str] = []

        # subject_key에서 entity와 attribute 분리
        if ":" not in subject_key:
            return []
        subject_entity, attribute = subject_key.split(":", 1)

        # --- 1단계: invalidated memory에서 object(값) entity 추출 ---
        source_mem = await metadata_store.get_memory(invalidated_memory_id)
        if not source_mem:
            return []

        # source entity 이외의 entity가 object (값)
        # 예: "The president of Russia is Putin" → subject="Russia", object="Putin"
        object_entities: set[str] = set()
        for node_id in graph_store.entity_graph.nodes:
            mem_ids = graph_store.get_memory_ids_for_entity(node_id)
            if invalidated_memory_id in mem_ids and node_id.lower() != subject_entity.lower():
                object_entities.add(node_id)

        if not object_entities:
            return []

        # --- 2단계: object entity를 subject로 가지는 downstream fact chain 탐색 ---
        # fact_registry에서 object entity가 subject인 항목들을 찾는다
        # 예: "Putin:birthplace" → memory_id 찾기
        target_memory_ids: set[str] = set()
        for reg_key, reg_mem_id in fact_registry.items():
            if reg_mem_id == invalidated_memory_id:
                continue
            if ":" not in reg_key:
                continue
            reg_entity, _ = reg_key.split(":", 1)
            # object entity와 대소문자 무관 매칭
            for obj_ent in object_entities:
                if reg_entity.lower() == obj_ent.lower():
                    target_memory_ids.add(reg_mem_id)
                    break

        if not target_memory_ids:
            return []

        # --- 3단계: target memory의 weight 갱신 (hop=1 고정) ---
        # downstream fact는 직접 연결(hop=1)로 취급
        hop = 1
        base_factor = decay_per_hop ** hop

        memories = await metadata_store.get_memories_by_ids(list(target_memory_ids))
        for mem in memories:
            if not mem.is_valid:
                continue
            # in-degree: 이 memory의 subject entity가 가진 incoming edge 수
            in_degree = 1
            for node_id in graph_store.entity_graph.nodes:
                mem_ids = graph_store.get_memory_ids_for_entity(node_id)
                if mem.id in mem_ids:
                    in_deg = graph_store.entity_graph.in_degree(node_id)
                    in_degree = max(in_deg, in_degree)
                    break

            adjusted_factor = 1 - (1 - base_factor) / max(in_degree, 1)
            new_weight = mem.decay_weight * adjusted_factor
            new_weight = max(new_weight, 0.0)
            await metadata_store.update_decay_weight(mem.id, new_weight)
            affected_ids.append(mem.id)

        # --- 4단계: depth > 1이면 재귀적으로 chain 추적 ---
        if propagation_depth > 1:
            for mem_id in list(affected_ids):
                # 이 memory의 subject_key 찾기
                child_key = None
                for reg_key, reg_mem_id in fact_registry.items():
                    if reg_mem_id == mem_id:
                        child_key = reg_key
                        break
                if child_key:
                    deeper = await self._propagate_attribute_aware(
                        invalidated_memory_id=mem_id,
                        graph_store=graph_store,
                        metadata_store=metadata_store,
                        subject_key=child_key,
                        fact_registry=fact_registry,
                        propagation_depth=propagation_depth - 1,
                        decay_per_hop=decay_per_hop,
                    )
                    affected_ids.extend(deeper)

        return affected_ids
