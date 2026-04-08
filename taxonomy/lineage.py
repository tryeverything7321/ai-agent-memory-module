"""계통수(Phylogenetic Lineage) — 택소노미 진화 이벤트를 DAG로 기록

택소노미 카테고리의 탄생(bootstrap/discovery), 분열(split), 융합(merge),
멸종(extinction) 이벤트를 시간순으로 기록하여 "화석 기록"을 생성한다.
NetworkX DiGraph로 부모→자식 관계를 유지하며, 직렬화/역직렬화를 지원한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import networkx as nx


class PhylogeneticLineage:
    """택소노미 진화 이벤트의 DAG 기반 계통수

    노드: 카테고리 (alive 또는 extinct)
    엣지: 부모→자식 (split, merge 시 생성)
    이벤트 로그: 시간순 기록, JSON 직렬화 가능
    """

    def __init__(self) -> None:
        self._dag: nx.DiGraph = nx.DiGraph()
        self._events: list[dict[str, Any]] = []
        self._extinct: set[str] = set()

    # --- 이벤트 기록 ---

    def record_bootstrap(self, category_name: str, member_count: int) -> None:
        """초기 k-means 클러스터링으로 생성된 카테고리를 기록한다."""
        self._dag.add_node(category_name, origin="bootstrap")
        event: dict[str, Any] = {
            "type": "bootstrap",
            "timestamp": _now_iso(),
            "category": category_name,
            "metadata": {"member_count": member_count},
        }
        self._events.append(event)

    def record_discovery(self, category_name: str, trigger_message: str) -> None:
        """LLM이 기존 센트로이드에 매칭하지 못해 새로 생성한 카테고리를 기록한다."""
        self._dag.add_node(category_name, origin="discovery")
        event: dict[str, Any] = {
            "type": "discovery",
            "timestamp": _now_iso(),
            "category": category_name,
            "metadata": {"trigger_message": trigger_message},
        }
        self._events.append(event)

    def record_split(
        self, parent: str, child_a: str, child_b: str, reason: str
    ) -> None:
        """카테고리 분열(Mitosis) — 부모 1개 → 자식 2개로 분리된다."""
        self._dag.add_node(child_a, origin="split")
        self._dag.add_node(child_b, origin="split")
        self._dag.add_edge(parent, child_a)
        self._dag.add_edge(parent, child_b)
        # 부모는 분열 후 멸종 처리
        self._extinct.add(parent)
        event: dict[str, Any] = {
            "type": "split",
            "timestamp": _now_iso(),
            "parent": parent,
            "children": [child_a, child_b],
            "reason": reason,
            "metadata": {},
        }
        self._events.append(event)

    def record_merge(
        self, parent_a: str, parent_b: str, child: str, reason: str
    ) -> None:
        """카테고리 융합(Fusion) — 부모 2개 → 자식 1개로 합쳐진다."""
        self._dag.add_node(child, origin="merge")
        self._dag.add_edge(parent_a, child)
        self._dag.add_edge(parent_b, child)
        # 두 부모는 융합 후 멸종 처리
        self._extinct.add(parent_a)
        self._extinct.add(parent_b)
        event: dict[str, Any] = {
            "type": "merge",
            "timestamp": _now_iso(),
            "parents": [parent_a, parent_b],
            "child": child,
            "reason": reason,
            "metadata": {},
        }
        self._events.append(event)

    def record_extinction(self, category: str, final_weight: float) -> None:
        """decay weight 부족으로 프루닝된 카테고리를 멸종 기록한다."""
        self._extinct.add(category)
        event: dict[str, Any] = {
            "type": "extinction",
            "timestamp": _now_iso(),
            "category": category,
            "metadata": {"final_weight": final_weight},
        }
        self._events.append(event)

    # --- 조회 ---

    def get_events(self) -> list[dict[str, Any]]:
        """시간순 이벤트 로그를 반환한다."""
        return list(self._events)

    def get_lineage_tree(self) -> dict[str, list[str]]:
        """DAG를 인접 리스트(adjacency dict)로 반환한다. 시각화용."""
        return {
            node: list(successors)
            for node, successors in self._dag.adjacency()
        }

    def get_alive_categories(self) -> set[str]:
        """멸종되지 않은 현재 활성 카테고리 집합을 반환한다."""
        return set(self._dag.nodes) - self._extinct

    def get_summary(self) -> dict[str, Any]:
        """이벤트 통계 요약을 반환한다."""
        counts: dict[str, int] = {}
        for event in self._events:
            event_type = event["type"]
            counts[event_type] = counts.get(event_type, 0) + 1
        return {
            "total_events": len(self._events),
            "total_nodes": self._dag.number_of_nodes(),
            "alive_categories": len(self.get_alive_categories()),
            "extinct_categories": len(self._extinct),
            "event_counts": counts,
        }

    # --- 직렬화 ---

    def to_json(self) -> list[dict[str, Any]]:
        """이벤트 로그를 JSON 직렬화 가능한 리스트로 반환한다."""
        return list(self._events)

    def from_json(self, events: list[dict[str, Any]]) -> None:
        """저장된 이벤트 로그로부터 DAG와 상태를 복원한다."""
        self._dag = nx.DiGraph()
        self._events = []
        self._extinct = set()

        for event in events:
            event_type = event["type"]
            if event_type == "bootstrap":
                self._dag.add_node(event["category"], origin="bootstrap")
            elif event_type == "discovery":
                self._dag.add_node(event["category"], origin="discovery")
            elif event_type == "split":
                parent = event["parent"]
                children = event["children"]
                for child in children:
                    self._dag.add_node(child, origin="split")
                    self._dag.add_edge(parent, child)
                self._extinct.add(parent)
            elif event_type == "merge":
                parents = event["parents"]
                child = event["child"]
                self._dag.add_node(child, origin="merge")
                for p in parents:
                    self._dag.add_edge(p, child)
                    self._extinct.add(p)
            elif event_type == "extinction":
                self._extinct.add(event["category"])

            self._events.append(event)


# --- 유틸리티 ---

def _now_iso() -> str:
    """현재 시각을 ISO 8601 문자열로 반환한다."""
    return datetime.now(timezone.utc).isoformat()
