"""NetworkX 기반 그래프 저장소 — entity_graph + intent_graph 2개 인스턴스"""

from __future__ import annotations

from typing import Optional

import networkx as nx

from storage.metadata_store import MetadataStore
from config import settings


class GraphStore:
    """
    2개 NetworkX 그래프 인스턴스를 관리:
      - entity_graph: 엔티티 간 관계 (사람→프로젝트, 장소→이벤트 등)
      - intent_graph: 의도 간 전이 확률 (weekly_report→issue_tracking 등)

    영속화: SQLite adjacency list, N건 변경마다 + 서버 종료 시 직렬화
    """

    def __init__(self, metadata_store: MetadataStore):
        self._metadata_store = metadata_store
        self.entity_graph = nx.DiGraph()
        self.intent_graph = nx.DiGraph()
        self._change_count = 0

    # --- Entity Graph ---

    def add_entity(self, entity_id: str, **attrs) -> None:
        """엔티티 추가/갱신 — memory_id는 1:N으로 누적"""
        memory_id = attrs.pop("memory_id", None)
        if entity_id in self.entity_graph:
            # 기존 노드: memory_id만 추가, 나머지 attrs 병합
            existing = self.entity_graph.nodes[entity_id]
            if memory_id:
                memory_ids = existing.get("memory_ids", set())
                if isinstance(memory_ids, list):
                    memory_ids = set(memory_ids)
                memory_ids.add(memory_id)
                existing["memory_ids"] = memory_ids
            existing.update(attrs)
        else:
            # 새 노드: memory_ids set으로 초기화
            memory_ids = {memory_id} if memory_id else set()
            self.entity_graph.add_node(entity_id, memory_ids=memory_ids, **attrs)
        self._on_change()

    def get_memory_ids_for_entity(self, entity_id: str) -> set[str]:
        """엔티티에 연결된 모든 memory_id 반환"""
        if entity_id not in self.entity_graph:
            return set()
        node_data = self.entity_graph.nodes[entity_id]
        memory_ids = node_data.get("memory_ids", set())
        if isinstance(memory_ids, list):
            return set(memory_ids)
        return memory_ids

    def add_relation(self, source: str, target: str, relation_type: str, **attrs) -> None:
        self.entity_graph.add_edge(source, target, relation_type=relation_type, **attrs)
        self._on_change()

    def get_neighbors(self, entity_id: str, hops: int = 1) -> list[tuple[str, dict]]:
        """N-hop 이웃 탐색"""
        if entity_id not in self.entity_graph:
            return []

        visited = set()
        current = {entity_id}
        for _ in range(hops):
            next_nodes = set()
            for node in current:
                for neighbor in self.entity_graph.successors(node):
                    if neighbor not in visited:
                        next_nodes.add(neighbor)
                for neighbor in self.entity_graph.predecessors(node):
                    if neighbor not in visited:
                        next_nodes.add(neighbor)
            visited.update(current)
            current = next_nodes

        results = []
        for node in current - {entity_id}:
            data = dict(self.entity_graph.nodes.get(node, {}))
            results.append((node, data))
        return results

    def get_related_entities(self, entity_id: str) -> list[tuple[str, str, dict]]:
        """특정 엔티티의 모든 관계 반환 (source, target, edge_data)"""
        if entity_id not in self.entity_graph:
            return []
        edges = []
        for _, target, data in self.entity_graph.out_edges(entity_id, data=True):
            edges.append((entity_id, target, dict(data)))
        for source, _, data in self.entity_graph.in_edges(entity_id, data=True):
            edges.append((source, entity_id, dict(data)))
        return edges

    # --- Intent Graph ---

    def record_intent_transition(self, from_intent: str, to_intent: str) -> None:
        """intent 전이 기록 — edge weight 누적"""
        if self.intent_graph.has_edge(from_intent, to_intent):
            self.intent_graph[from_intent][to_intent]["count"] += 1
        else:
            self.intent_graph.add_edge(from_intent, to_intent, count=1)
        self._update_transition_weights(from_intent)
        self._on_change()

    def get_next_intent(self, current_intent: str) -> Optional[tuple[str, float]]:
        """가장 높은 전이 확률의 다음 intent 반환"""
        if current_intent not in self.intent_graph:
            return None
        edges = list(self.intent_graph.out_edges(current_intent, data=True))
        if not edges:
            return None
        best = max(edges, key=lambda e: e[2].get("weight", 0))
        weight = best[2].get("weight", 0)
        return (best[1], weight)

    def get_transition_weight(self, from_intent: str, to_intent: str) -> float:
        if self.intent_graph.has_edge(from_intent, to_intent):
            return self.intent_graph[from_intent][to_intent].get("weight", 0)
        return 0.0

    def _update_transition_weights(self, from_intent: str) -> None:
        """전이 확률 = count / total_count (from_intent에서 나가는 모든 엣지)"""
        total = sum(
            d.get("count", 0)
            for _, _, d in self.intent_graph.out_edges(from_intent, data=True)
        )
        if total == 0:
            return
        for _, target, data in self.intent_graph.out_edges(from_intent, data=True):
            data["weight"] = data.get("count", 0) / total

    # --- 직렬화 ---

    def _on_change(self) -> None:
        self._change_count += 1
        if self._change_count >= settings.graph_serialize_interval:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.persist())
            except RuntimeError:
                pass
            self._change_count = 0

    async def persist(self) -> None:
        """양쪽 그래프를 SQLite에 직렬화"""
        await self._save_graph("entity_graph", self.entity_graph)
        await self._save_graph("intent_graph", self.intent_graph)
        self._change_count = 0

    async def load_from_db(self) -> None:
        """SQLite에서 그래프 복원"""
        await self._load_graph("entity_graph", self.entity_graph)
        await self._load_graph("intent_graph", self.intent_graph)

    async def _save_graph(self, name: str, graph: nx.DiGraph) -> None:
        # set→list 변환 (JSON 직렬화 호환)
        nodes = []
        for n, d in graph.nodes(data=True):
            serialized = dict(d)
            if "memory_ids" in serialized and isinstance(serialized["memory_ids"], set):
                serialized["memory_ids"] = list(serialized["memory_ids"])
            nodes.append((n, serialized))
        edges = [(u, v, dict(d)) for u, v, d in graph.edges(data=True)]
        await self._metadata_store.save_graph_data(name, nodes, edges)

    async def _load_graph(self, name: str, graph: nx.DiGraph) -> None:
        nodes, edges = await self._metadata_store.load_graph_data(name)
        graph.clear()
        for node_id, node_data in nodes:
            # list→set 복원 (JSON 역직렬화 호환)
            if "memory_ids" in node_data and isinstance(node_data["memory_ids"], list):
                node_data["memory_ids"] = set(node_data["memory_ids"])
            graph.add_node(node_id, **node_data)
        for source, target, edge_data in edges:
            graph.add_edge(source, target, **edge_data)
