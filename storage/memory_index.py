"""통합 검색 레이어 — RRF(Reciprocal Rank Fusion)로 3개 소스 병합

score(d) = Σ 1/(k + rank_i(d))
k=60, 가중치: vector×1.0, metadata×1.2, graph×0.8, top-N=5
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from config import settings
from models import Memory, SearchResult
from storage.vector_store import VectorStore
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore


class MemoryIndex:
    """하이브리드 검색: Vector + Metadata + Graph → RRF fusion"""

    def __init__(
        self,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
        graph_store: GraphStore,
    ):
        self._vector = vector_store
        self._metadata = metadata_store
        self._graph = graph_store

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
        time_start: Optional[datetime] = None,
        time_end: Optional[datetime] = None,
    ) -> list[SearchResult]:
        """3개 소스를 asyncio.gather로 병렬 검색 후 RRF fusion (PERF-1)"""
        top_k = top_k or settings.rrf_top_n
        k = settings.rrf_k

        # --- 3개 소스 병렬 검색 ---
        vector_task = self._search_vector(query, user_id, top_k * 2)
        metadata_task = self._search_metadata(query, user_id, time_start, time_end)
        graph_task = self._search_graph(query, user_id)

        vector_results, metadata_results, graph_results = await asyncio.gather(
            vector_task, metadata_task, graph_task
        )

        # --- RRF 점수 계산 ---
        scores: dict[str, float] = {}

        # Vector source (weight 1.0)
        for rank, (memory_id, _) in enumerate(vector_results):
            scores[memory_id] = scores.get(memory_id, 0) + 1.0 / (k + rank + 1)

        # Metadata source (weight 1.2)
        for rank, memory in enumerate(metadata_results):
            scores[memory.id] = scores.get(memory.id, 0) + 1.2 / (k + rank + 1)

        # Graph source (weight 0.8)
        for rank, (memory_id, _) in enumerate(graph_results):
            scores[memory_id] = scores.get(memory_id, 0) + 0.8 / (k + rank + 1)

        # --- Top-N 추출 + Memory 객체 조회 ---
        # 1차: RRF 점수 기준 후보군 (2x top_k로 여유 확보)
        candidate_ids = sorted(scores.items(), key=lambda x: -x[1])[:top_k * 2]
        if not candidate_ids:
            return []

        memory_ids = [mid for mid, _ in candidate_ids]
        memories = await self._metadata.get_memories_by_ids(memory_ids)
        memory_map = {m.id: m for m in memories}

        # 2차: invalid 메모리 제외 + RRF * decay_weight로 최종 점수
        weighted = []
        for memory_id, rrf_score in candidate_ids:
            if memory_id in memory_map:
                mem = memory_map[memory_id]
                if not mem.is_valid:
                    continue  # 무효화된 메모리 제외
                final_score = rrf_score * mem.decay_weight
                weighted.append((memory_id, final_score, rrf_score))

        weighted.sort(key=lambda x: -x[1])
        results = []
        for memory_id, final_score, rrf_score in weighted[:top_k]:
            results.append(SearchResult(
                memory=memory_map[memory_id],
                score=final_score,
                source="fusion",
            ))
        return results

    async def _search_vector(
        self, query: str, user_id: str, top_k: int
    ) -> list[tuple[str, float]]:
        try:
            return await self._vector.search(query, user_id, top_k)
        except Exception:
            return []

    async def _search_metadata(
        self, query: str, user_id: str,
        time_start: Optional[datetime], time_end: Optional[datetime],
    ) -> list[Memory]:
        try:
            if time_start and time_end:
                return await self._metadata.search_by_time_range(user_id, time_start, time_end)
            return await self._metadata.get_memories_by_user(user_id)
        except Exception:
            return []

    async def _search_graph(
        self, query: str, user_id: str
    ) -> list[tuple[str, float]]:
        """쿼리에서 엔티티를 찾아 그래프 탐색 → 관련 메모리 ID 반환"""
        try:
            # 쿼리 텍스트를 단어 단위로 그래프 노드 매칭
            results = []
            words = query.split()
            for word in words:
                if word in self._graph.entity_graph:
                    neighbors = self._graph.get_neighbors(word, hops=1)
                    for node_id, data in neighbors:
                        memory_id = data.get("memory_id")
                        if memory_id:
                            results.append((memory_id, 1.0))
            return results
        except Exception:
            return []
