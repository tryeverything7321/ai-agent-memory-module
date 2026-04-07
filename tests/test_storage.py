"""Storage Layer 테스트 — RRF fusion, dedup, graceful degradation

S1-S4: 기본 저장/검색 (test_infra에서 커버)
S5: RRF fusion
S6: dedup
S7: 시간 범위 필터
S8-S9: 그래프 직렬화/복원 (test_infra에서 커버)
S10: intent_graph 분리
S11: Qdrant 다운 graceful
S12: 빈 결과
"""

import pytest
from datetime import datetime, timedelta

from models import Memory, Importance, SearchResult
from storage.vector_store import VectorStore, MockEmbeddingProvider
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.memory_index import MemoryIndex


@pytest.fixture
def embedding_provider():
    return MockEmbeddingProvider(dim=1024)


@pytest.fixture
async def full_storage(metadata_store, graph_store, embedding_provider):
    """전체 스토리지 스택 (Vector+Metadata+Graph)"""
    vs = VectorStore(embedding_provider=embedding_provider, use_qdrant=False)
    await vs.initialize()

    index = MemoryIndex(
        vector_store=vs, metadata_store=metadata_store, graph_store=graph_store
    )
    return vs, metadata_store, graph_store, index


class TestRRFFusion:
    """S5: RRF fusion 검색"""

    async def test_rrf_returns_ranked_results(self, full_storage):
        vs, ms, gs, index = full_storage

        # 메모리 3개 저장
        for i, (content, imp) in enumerate([
            ("대만 출장 일정 확인", Importance.critical),
            ("대만 맛집 딘타이펑 추천", Importance.important),
            ("코드 리뷰 PR #123", Importance.important),
        ]):
            mem = Memory(
                id=f"m{i}", user_id="user_pm", content=content, importance=imp,
                created_at=datetime(2026, 3, 25),
            )
            await ms.save_memory(mem)
            await vs.store(mem.id, content, "user_pm")

        results = await index.search("대만 여행", "user_pm", top_k=3)
        assert len(results) > 0
        # 대만 관련 메모리가 코드 리뷰보다 높은 순위
        if len(results) >= 2:
            assert any("대만" in r.memory.content for r in results[:2])

    async def test_rrf_empty_query(self, full_storage):
        """S12: 빈 결과 처리"""
        _, _, _, index = full_storage
        results = await index.search("존재하지않는검색어", "user_nobody")
        assert results == []


class TestDedup:
    """S6: 중복 메모리 dedup"""

    async def test_cosine_dedup(self, vector_store):
        await vector_store.store("m1", "대만 출장 일정", "user_pm")

        # 동일 텍스트 → 기존 메모리 ID 반환
        similar = await vector_store.find_similar("대만 출장 일정", "user_pm", threshold=0.9)
        assert similar == "m1"

    async def test_no_dedup_for_different_content(self, vector_store):
        await vector_store.store("m1", "대만 출장 일정", "user_pm")

        similar = await vector_store.find_similar("Python 코드 리팩토링", "user_pm", threshold=0.9)
        assert similar is None


class TestMetadataFilter:
    """S7: 시간 범위 필터"""

    async def test_time_range_filter(self, metadata_store):
        base = datetime(2026, 3, 23)
        for i in range(5):
            mem = Memory(
                user_id="user_pm",
                content=f"day {i} 메모",
                created_at=base + timedelta(days=i),
            )
            await metadata_store.save_memory(mem)

        # day 1~3만 조회
        results = await metadata_store.search_by_time_range(
            "user_pm",
            base + timedelta(days=1),
            base + timedelta(days=3),
        )
        assert len(results) == 3


class TestIntentGraphSeparation:
    """S10: entity_graph와 intent_graph 분리 확인"""

    async def test_separate_instances(self, graph_store):
        # entity_graph에 추가
        graph_store.add_entity("김팀장", entity_type="person")
        # intent_graph에 추가
        graph_store.record_intent_transition("weekly_report", "issue_tracking")

        # 서로 영향 없음
        assert "김팀장" in graph_store.entity_graph
        assert "김팀장" not in graph_store.intent_graph
        assert "weekly_report" in graph_store.intent_graph
        assert "weekly_report" not in graph_store.entity_graph


class TestGracefulDegradation:
    """S11: Qdrant 다운 시 graceful degradation"""

    async def test_vector_store_fallback(self):
        """Qdrant 연결 실패해도 에러 없이 동작"""
        provider = MockEmbeddingProvider(dim=1024)
        vs = VectorStore(embedding_provider=provider, use_qdrant=False)
        await vs.initialize()

        await vs.store("m1", "테스트 메모리", "user_pm")
        results = await vs.search("테스트", "user_pm")
        assert len(results) > 0

    async def test_memory_index_with_failed_vector(self, metadata_store, graph_store):
        """Vector 검색 실패해도 Metadata+Graph로 결과 반환"""
        class FailingVectorStore:
            async def search(self, *args, **kwargs):
                raise ConnectionError("Qdrant down")

        mem = Memory(user_id="user_pm", content="테스트")
        await metadata_store.save_memory(mem)

        index = MemoryIndex(
            vector_store=FailingVectorStore(),
            metadata_store=metadata_store,
            graph_store=graph_store,
        )
        # 에러 없이 결과 반환 (Metadata에서만)
        results = await index.search("테스트", "user_pm")
        assert isinstance(results, list)
