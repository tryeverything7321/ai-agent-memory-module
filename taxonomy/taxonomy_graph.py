"""Taxonomy Graph — 동적 intent 카테고리 그래프

NetworkX DiGraph 기반으로 intent 카테고리를 노드로 관리한다.
각 카테고리는 centroid 임베딩, decay weight, 접근 통계를 갖고
데이터 기반으로 생성(bootstrap/discovery), 분열(split), 융합(merge),
소멸(prune)된다.

수식: w(t) = e^(-λ * hours) * (1 + boost * min(access_count, 20))
  - boost cap: access_count 최대 20까지만 반영 (max weight multiplier = 2.0)
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import networkx as nx
import numpy as np

from config import settings

# --- 상수 ---
CLASSIFY_THRESHOLD = 0.6
SPLIT_THRESHOLD = 0.5
MERGE_THRESHOLD = 0.85
PRUNE_THRESHOLD = 0.05
BOOST = 0.05
MIN_SPLIT_SIZE = 5
MAX_CATEGORIES = 50
MIN_CATEGORIES = 3
ACCESS_COUNT_CAP = 20


class TaxonomyGraph:
    """동적 intent 카테고리 그래프

    각 노드는 하나의 intent 카테고리이며, centroid 임베딩과
    decay 기반 가중치를 갖는다.
    """

    def __init__(self):
        self._graph = nx.DiGraph()

    # --- 카테고리 추가 ---

    def add_category(
        self,
        name: str,
        centroid: list[float],
        created_by: str = "bootstrap",
    ) -> None:
        """새 카테고리 노드를 그래프에 추가한다.

        Args:
            name: LLM이 생성한 카테고리 이름
            centroid: 평균 임베딩 벡터 (1024-dim)
            created_by: 생성 경로 ("bootstrap" | "discovery" | "split" | "merge")
        """
        if name in self._graph:
            raise ValueError(f"카테고리 '{name}'이(가) 이미 존재합니다")

        if len(self._graph) >= MAX_CATEGORIES:
            raise ValueError(
                f"최대 카테고리 수({MAX_CATEGORIES})에 도달했습니다"
            )

        now = datetime.now()
        self._graph.add_node(
            name,
            name=name,
            centroid=list(centroid),
            member_count=0,
            member_ids=[],
            decay_lambda=0.1,
            decay_weight=1.0,
            last_activated=now,
            access_count=0,
            created_by=created_by,
            created_at=now,
        )

    # --- 카테고리 활성화 ---

    def activate_category(self, name: str, new_embedding: list[float]) -> None:
        """카테고리에 접근하여 centroid를 증분 업데이트한다.

        증분 공식: new_centroid = (old * n + new) / (n + 1)

        Args:
            name: 카테고리 이름
            new_embedding: 새 임베딩 벡터
        """
        if name not in self._graph:
            raise KeyError(f"카테고리 '{name}'을(를) 찾을 수 없습니다")

        node = self._graph.nodes[name]
        n = node["member_count"]

        old_centroid = np.array(node["centroid"])
        new_emb = np.array(new_embedding)
        updated_centroid = (old_centroid * n + new_emb) / (n + 1)

        node["centroid"] = updated_centroid.tolist()
        node["access_count"] += 1
        node["last_activated"] = datetime.now()

    # --- 멤버 관리 ---

    def add_member(self, category_name: str, memory_id: str) -> None:
        """카테고리에 메모리 ID를 추가한다.

        Args:
            category_name: 대상 카테고리 이름
            memory_id: 추가할 메모리 ID
        """
        if category_name not in self._graph:
            raise KeyError(f"카테고리 '{category_name}'을(를) 찾을 수 없습니다")

        node = self._graph.nodes[category_name]
        if memory_id not in node["member_ids"]:
            node["member_ids"].append(memory_id)
            node["member_count"] = len(node["member_ids"])

    # --- 최적 카테고리 매칭 ---

    def get_best_match(
        self,
        embedding: list[float],
        threshold: float = CLASSIFY_THRESHOLD,
    ) -> Optional[str]:
        """모든 카테고리 centroid와 코사인 유사도를 비교하여 최적 매칭을 반환한다.

        Args:
            embedding: 비교할 임베딩 벡터
            threshold: 최소 유사도 임계치 (기본 0.6)

        Returns:
            최적 카테고리 이름 또는 None (임계치 미달 시)
        """
        if len(self._graph) == 0:
            return None

        query = np.array(embedding)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return None

        best_name = None
        best_sim = -1.0

        for name in self._graph.nodes:
            centroid = np.array(self._graph.nodes[name]["centroid"])
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm == 0:
                continue

            sim = float(np.dot(query, centroid) / (query_norm * centroid_norm))
            if sim > best_sim:
                best_sim = sim
                best_name = name

        if best_sim >= threshold:
            return best_name
        return None

    # --- Decay 계산 ---

    def decay_all(self, now: datetime) -> None:
        """모든 카테고리의 decay weight를 재계산한다.

        수식: w = exp(-lambda * hours) * (1 + boost * min(access_count, 20))
        boost cap: access_count=20일 때 최대 가중치 승수 = 2.0

        Args:
            now: 현재 시각
        """
        for name in self._graph.nodes:
            node = self._graph.nodes[name]
            hours = (now - node["last_activated"]).total_seconds() / 3600
            lam = node["decay_lambda"]
            access = min(node["access_count"], ACCESS_COUNT_CAP)

            base_decay = math.exp(-lam * hours)
            weight = base_decay * (1 + BOOST * access)
            node["decay_weight"] = weight

    # --- 프루닝 후보 ---

    def get_candidates_for_prune(
        self, threshold: float = PRUNE_THRESHOLD
    ) -> list[str]:
        """decay_weight가 임계치 미만인 카테고리를 반환한다.

        MIN_CATEGORIES(3)개 이하로는 줄이지 않는다.

        Args:
            threshold: 프루닝 임계치 (기본 0.05)

        Returns:
            프루닝 대상 카테고리 이름 목록
        """
        total = len(self._graph)
        if total <= MIN_CATEGORIES:
            return []

        # weight 기준 오름차순 정렬하여 임계치 미달 후보 추출
        candidates = []
        for name in self._graph.nodes:
            node = self._graph.nodes[name]
            if node["decay_weight"] < threshold:
                candidates.append((name, node["decay_weight"]))

        # weight 낮은 순으로 정렬
        candidates.sort(key=lambda x: x[1])

        # MIN_CATEGORIES 보장: 최대 삭제 가능 수 제한
        max_removable = total - MIN_CATEGORIES
        return [name for name, _ in candidates[:max_removable]]

    # --- 카테고리 제거 ---

    def remove_category(self, name: str) -> list[str]:
        """카테고리를 제거하고 고아 멤버 ID 목록을 반환한다.

        Args:
            name: 제거할 카테고리 이름

        Returns:
            고아가 된 메모리 ID 목록
        """
        if name not in self._graph:
            raise KeyError(f"카테고리 '{name}'을(를) 찾을 수 없습니다")

        orphan_ids = list(self._graph.nodes[name]["member_ids"])
        self._graph.remove_node(name)
        return orphan_ids

    # --- 분열 후보 ---

    def get_candidates_for_split(
        self,
        split_threshold: float = SPLIT_THRESHOLD,
        min_size: int = MIN_SPLIT_SIZE,
        embeddings: Optional[dict[str, list[float]]] = None,
    ) -> list[str]:
        """분열 후보 카테고리를 반환한다.

        임베딩이 제공되면 intra-cluster variance를 계산하여 split_threshold 초과 시 후보로 선정.
        임베딩이 없으면 member_count >= min_size인 카테고리만 반환.

        Args:
            split_threshold: 분산 임계치 (기본 0.5)
            min_size: 최소 멤버 수 (기본 5)
            embeddings: memory_id → embedding 매핑 (선택)

        Returns:
            분열 후보 카테고리 이름 목록
        """
        candidates = []

        for name in self._graph.nodes:
            node = self._graph.nodes[name]
            if node["member_count"] < min_size:
                continue

            if embeddings is None:
                # 임베딩 없으면 크기 기준만 적용
                candidates.append(name)
                continue

            # intra-cluster variance 계산
            member_embeddings = []
            for mid in node["member_ids"]:
                if mid in embeddings:
                    member_embeddings.append(np.array(embeddings[mid]))

            if len(member_embeddings) < min_size:
                continue

            centroid = np.array(node["centroid"])
            # 평균 코사인 거리 (1 - similarity)를 variance proxy로 사용
            distances = []
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm == 0:
                continue

            for emb in member_embeddings:
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    continue
                sim = float(np.dot(emb, centroid) / (emb_norm * centroid_norm))
                distances.append(1.0 - sim)

            if distances:
                variance = float(np.mean(distances))
                if variance > split_threshold:
                    candidates.append(name)

        return candidates

    # --- 융합 후보 ---

    def get_candidates_for_fusion(
        self, merge_threshold: float = MERGE_THRESHOLD
    ) -> list[tuple[str, str]]:
        """centroid 간 코사인 유사도가 너무 높은 카테고리 쌍을 반환한다.

        Args:
            merge_threshold: 융합 임계치 (기본 0.85)

        Returns:
            융합 후보 (카테고리A, 카테고리B) 튜플 목록
        """
        nodes = list(self._graph.nodes)
        pairs = []

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                c_a = np.array(self._graph.nodes[nodes[i]]["centroid"])
                c_b = np.array(self._graph.nodes[nodes[j]]["centroid"])

                norm_a = np.linalg.norm(c_a)
                norm_b = np.linalg.norm(c_b)
                if norm_a == 0 or norm_b == 0:
                    continue

                sim = float(np.dot(c_a, c_b) / (norm_a * norm_b))
                if sim >= merge_threshold:
                    pairs.append((nodes[i], nodes[j]))

        return pairs

    # --- 분열 실행 ---

    def split_category(
        self,
        parent_name: str,
        child_a: str,
        child_b: str,
        members_a: list[str],
        members_b: list[str],
        centroid_a: list[float],
        centroid_b: list[float],
    ) -> None:
        """부모 카테고리를 두 자식으로 분열한다.

        부모 노드를 제거하고 두 개의 새 카테고리를 생성한다.

        Args:
            parent_name: 분열 대상 부모 카테고리 이름
            child_a: 첫 번째 자식 이름
            child_b: 두 번째 자식 이름
            members_a: 첫 번째 자식의 멤버 ID 목록
            members_b: 두 번째 자식의 멤버 ID 목록
            centroid_a: 첫 번째 자식의 centroid
            centroid_b: 두 번째 자식의 centroid
        """
        if parent_name not in self._graph:
            raise KeyError(f"카테고리 '{parent_name}'을(를) 찾을 수 없습니다")

        # 부모 제거
        self._graph.remove_node(parent_name)

        # 자식 A 생성
        now = datetime.now()
        self._graph.add_node(
            child_a,
            name=child_a,
            centroid=list(centroid_a),
            member_count=len(members_a),
            member_ids=list(members_a),
            decay_lambda=0.1,
            decay_weight=1.0,
            last_activated=now,
            access_count=0,
            created_by="split",
            created_at=now,
        )

        # 자식 B 생성
        self._graph.add_node(
            child_b,
            name=child_b,
            centroid=list(centroid_b),
            member_count=len(members_b),
            member_ids=list(members_b),
            decay_lambda=0.1,
            decay_weight=1.0,
            last_activated=now,
            access_count=0,
            created_by="split",
            created_at=now,
        )

    # --- 융합 실행 ---

    def merge_categories(
        self,
        cat_a: str,
        cat_b: str,
        new_name: str,
        new_centroid: list[float],
    ) -> None:
        """두 카테고리를 하나로 융합한다.

        두 노드를 제거하고 멤버를 합친 새 카테고리를 생성한다.

        Args:
            cat_a: 첫 번째 카테고리 이름
            cat_b: 두 번째 카테고리 이름
            new_name: 융합 결과 카테고리 이름
            new_centroid: 융합 결과 centroid
        """
        if cat_a not in self._graph:
            raise KeyError(f"카테고리 '{cat_a}'을(를) 찾을 수 없습니다")
        if cat_b not in self._graph:
            raise KeyError(f"카테고리 '{cat_b}'을(를) 찾을 수 없습니다")

        # 멤버 합치기
        members_a = list(self._graph.nodes[cat_a]["member_ids"])
        members_b = list(self._graph.nodes[cat_b]["member_ids"])
        merged_members = members_a + members_b

        # 접근 횟수 합산
        total_access = (
            self._graph.nodes[cat_a]["access_count"]
            + self._graph.nodes[cat_b]["access_count"]
        )

        # 기존 노드 제거
        self._graph.remove_node(cat_a)
        self._graph.remove_node(cat_b)

        # 새 노드 생성
        now = datetime.now()
        self._graph.add_node(
            new_name,
            name=new_name,
            centroid=list(new_centroid),
            member_count=len(merged_members),
            member_ids=merged_members,
            decay_lambda=0.1,
            decay_weight=1.0,
            last_activated=now,
            access_count=total_access,
            created_by="merge",
            created_at=now,
        )

    # --- 전체 카테고리 조회 ---

    def get_all_categories(self) -> list[dict]:
        """모든 카테고리 정보를 딕셔너리 목록으로 반환한다."""
        result = []
        for name in self._graph.nodes:
            node = dict(self._graph.nodes[name])
            result.append(node)
        return result

    # --- 직렬화 ---

    def to_json(self) -> dict:
        """그래프를 JSON 직렬화 가능한 dict로 변환한다.

        datetime 객체는 ISO 형식 문자열로 변환한다.
        """
        nodes = []
        for name in self._graph.nodes:
            node = dict(self._graph.nodes[name])
            # datetime → ISO 문자열 변환
            node["last_activated"] = node["last_activated"].isoformat()
            node["created_at"] = node["created_at"].isoformat()
            nodes.append(node)

        edges = []
        for u, v, data in self._graph.edges(data=True):
            edges.append({"source": u, "target": v, "data": data})

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_json(cls, data: dict) -> TaxonomyGraph:
        """JSON dict로부터 TaxonomyGraph를 복원한다.

        Args:
            data: to_json()으로 생성된 dict

        Returns:
            복원된 TaxonomyGraph 인스턴스
        """
        graph = cls()

        for node_data in data.get("nodes", []):
            name = node_data["name"]
            # ISO 문자열 → datetime 복원
            node_data["last_activated"] = datetime.fromisoformat(
                node_data["last_activated"]
            )
            node_data["created_at"] = datetime.fromisoformat(
                node_data["created_at"]
            )
            graph._graph.add_node(name, **node_data)

        for edge_data in data.get("edges", []):
            graph._graph.add_edge(
                edge_data["source"],
                edge_data["target"],
                **edge_data.get("data", {}),
            )

        return graph

    # --- 유틸리티 ---

    def __len__(self) -> int:
        return len(self._graph)

    def __contains__(self, name: str) -> bool:
        return name in self._graph
