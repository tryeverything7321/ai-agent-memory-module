"""Qdrant 기반 벡터 저장소 — 시맨틱 임베딩 저장/검색, dedup"""

from __future__ import annotations

from typing import Optional, Protocol

import numpy as np

from config import settings
from models import Memory


class EmbeddingProvider(Protocol):
    """임베딩 생성 인터페이스 — 테스트에서 mock 가능"""
    async def embed(self, text: str) -> list[float]: ...


class DooGPUEmbeddingProvider:
    """BAAI/bge-m3 via DooGPU reserved9 — 실제 시맨틱 임베딩"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str = "EMPTY",
    ):
        self._base_url = (base_url or settings.embedding_base_url).rstrip("/")
        self._model = model or settings.embedding_model
        self._api_key = api_key
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        return self._dim or settings.embedding_dim

    async def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩"""
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """배치 임베딩 — demo_runner에서 효율적 처리용"""
        import httpx

        url = f"{self._base_url}/embeddings"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                json={"model": self._model, "input": texts},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        vectors = [d["embedding"] for d in data["data"]]
        if vectors and self._dim is None:
            self._dim = len(vectors[0])
        return vectors


class MockEmbeddingProvider:
    """테스트용 mock 임베딩 (랜덤 벡터, 동일 텍스트는 동일 벡터)"""
    def __init__(self, dim: int = 1024):
        self._dim = dim
        self._cache: dict[str, list[float]] = {}

    async def embed(self, text: str) -> list[float]:
        if text not in self._cache:
            rng = np.random.RandomState(hash(text) % (2**31))
            vec = rng.randn(self._dim).tolist()
            norm = np.linalg.norm(vec)
            self._cache[text] = (np.array(vec) / norm).tolist()
        return self._cache[text]


class VectorStore:
    """
    Qdrant 래퍼.
    - Qdrant 연결 실패 시 graceful degradation (빈 결과 반환)
    - 임베딩 cosine similarity > 0.9 → dedup (기존 메모리 업데이트)
    """

    def __init__(self, embedding_provider: EmbeddingProvider, use_qdrant: bool = True):
        self._embedding = embedding_provider
        self._use_qdrant = use_qdrant
        self._client = None
        self._collection = settings.qdrant_collection

        # Qdrant 없을 때 fallback: in-memory dict
        self._memory_vectors: dict[str, list[float]] = {}
        self._memory_users: dict[str, str] = {}  # memory_id → user_id

    async def initialize(self) -> None:
        if self._use_qdrant:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import VectorParams, Distance

                self._client = QdrantClient(
                    host=settings.qdrant_host, port=settings.qdrant_port
                )
                # 컬렉션 생성 (없으면)
                collections = [c.name for c in self._client.get_collections().collections]
                if self._collection not in collections:
                    self._client.create_collection(
                        collection_name=self._collection,
                        vectors_config=VectorParams(
                            size=settings.embedding_dim, distance=Distance.COSINE
                        ),
                    )
            except Exception:
                self._client = None

    async def store(self, memory_id: str, text: str, user_id: str) -> list[float]:
        """텍스트를 임베딩하고 벡터 저장. 임베딩 벡터 반환."""
        embedding = await self._embedding.embed(text)

        if self._client:
            from qdrant_client.models import PointStruct
            self._client.upsert(
                collection_name=self._collection,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=embedding,
                        payload={"user_id": user_id, "content": text},
                    )
                ],
            )
        else:
            self._memory_vectors[memory_id] = embedding
            self._memory_users[memory_id] = user_id

        return embedding

    async def search(
        self, query: str, user_id: str, top_k: int = 5
    ) -> list[tuple[str, float]]:
        """시맨틱 검색 → (memory_id, score) 리스트"""
        query_vec = await self._embedding.embed(query)

        if self._client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = self._client.search(
                collection_name=self._collection,
                query_vector=query_vec,
                query_filter=Filter(
                    must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                ),
                limit=top_k,
            )
            return [(str(r.id), r.score) for r in results]
        else:
            return self._fallback_search(query_vec, user_id, top_k)

    async def find_similar(self, text: str, user_id: str, threshold: float = 0.9) -> Optional[str]:
        """dedup 용: threshold 이상 유사한 기존 메모리 ID 반환"""
        results = await self.search(text, user_id, top_k=1)
        if results and results[0][1] >= threshold:
            return results[0][0]
        return None

    async def delete(self, memory_id: str) -> None:
        if self._client:
            self._client.delete(
                collection_name=self._collection,
                points_selector=[memory_id],
            )
        else:
            self._memory_vectors.pop(memory_id, None)

    def _fallback_search(
        self, query_vec: list[float], user_id: str, top_k: int
    ) -> list[tuple[str, float]]:
        """Qdrant 없을 때 in-memory cosine search (user_id 필터링 포함)"""
        q = np.array(query_vec)
        scores = []
        for mid, vec in self._memory_vectors.items():
            if self._memory_users.get(mid) != user_id:
                continue
            v = np.array(vec)
            cos_sim = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-10))
            scores.append((mid, cos_sim))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]
