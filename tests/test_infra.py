"""Phase 1 인프라 테스트 — MetadataStore, GraphStore, VectorStore 기본 동작 확인"""

import pytest
from datetime import datetime

from models import Memory, Importance
from storage.graph_store import GraphStore


class TestMetadataStore:
    async def test_save_and_get_memory(self, metadata_store):
        mem = Memory(
            user_id="user_pm",
            content="다음 주 대만 출장",
            importance=Importance.critical,
            decay_lambda=0.005,
        )
        await metadata_store.save_memory(mem)
        result = await metadata_store.get_memory(mem.id)
        assert result is not None
        assert result.content == "다음 주 대만 출장"
        assert result.importance == Importance.critical

    async def test_get_memories_by_user(self, metadata_store):
        for i in range(3):
            await metadata_store.save_memory(
                Memory(user_id="user_pm", content=f"메모 {i}")
            )
        await metadata_store.save_memory(
            Memory(user_id="user_dev", content="다른 유저 메모")
        )
        results = await metadata_store.get_memories_by_user("user_pm")
        assert len(results) == 3

    async def test_batch_get_by_ids(self, metadata_store):
        mems = []
        for i in range(5):
            m = Memory(user_id="user_pm", content=f"메모 {i}")
            await metadata_store.save_memory(m)
            mems.append(m)
        ids = [m.id for m in mems[:3]]
        results = await metadata_store.get_memories_by_ids(ids)
        assert len(results) == 3

    async def test_update_access(self, metadata_store):
        mem = Memory(user_id="user_pm", content="테스트")
        await metadata_store.save_memory(mem)
        await metadata_store.update_access(mem.id)
        result = await metadata_store.get_memory(mem.id)
        assert result.access_count == 1

    async def test_prune_below_threshold(self, metadata_store):
        m1 = Memory(user_id="u", content="살아남을 메모리", decay_weight=0.5)
        m2 = Memory(user_id="u", content="삭제될 메모리", decay_weight=0.05)
        await metadata_store.save_memory(m1)
        await metadata_store.save_memory(m2)
        deleted = await metadata_store.delete_memories_below_threshold(0.1)
        assert deleted == 1
        assert await metadata_store.get_memory(m1.id) is not None
        assert await metadata_store.get_memory(m2.id) is None


class TestGraphStore:
    async def test_add_entity_and_relation(self, graph_store):
        graph_store.add_entity("김팀장", entity_type="person")
        graph_store.add_entity("A 프로젝트", entity_type="project")
        graph_store.add_relation("김팀장", "A 프로젝트", "담당")
        assert graph_store.entity_graph.has_edge("김팀장", "A 프로젝트")

    async def test_get_neighbors(self, graph_store):
        graph_store.add_relation("대만", "맛집", "관련")
        graph_store.add_relation("대만", "야시장", "관련")
        neighbors = graph_store.get_neighbors("대만", hops=1)
        names = [n[0] for n in neighbors]
        assert "맛집" in names
        assert "야시장" in names

    async def test_intent_transition(self, graph_store):
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "scheduling")

        result = graph_store.get_next_intent("weekly_report")
        assert result is not None
        assert result[0] == "issue_tracking"
        assert result[1] > 0.5  # 2/3 ≈ 0.67

    async def test_persist_and_restore(self, graph_store, metadata_store):
        graph_store.add_relation("A", "B", "관계")
        graph_store.record_intent_transition("a", "b")
        await graph_store.persist()

        # 새 인스턴스에서 복원
        new_store = GraphStore(metadata_store)
        await new_store.load_from_db()
        assert new_store.entity_graph.has_edge("A", "B")
        assert new_store.intent_graph.has_edge("a", "b")


class TestVectorStore:
    async def test_store_and_search(self, vector_store):
        await vector_store.store("m1", "대만 출장 일정", "user_pm")
        await vector_store.store("m2", "대만 맛집 추천", "user_pm")
        await vector_store.store("m3", "코드 리뷰 요청", "user_dev")

        results = await vector_store.search("대만 여행", "user_pm", top_k=2)
        assert len(results) > 0

    async def test_find_similar_dedup(self, vector_store):
        await vector_store.store("m1", "대만 출장 일정", "user_pm")
        # 동일 텍스트 → dedup
        similar = await vector_store.find_similar("대만 출장 일정", "user_pm", threshold=0.9)
        assert similar == "m1"

    async def test_find_similar_no_match(self, vector_store):
        await vector_store.store("m1", "대만 출장 일정", "user_pm")
        similar = await vector_store.find_similar("코드 리뷰 피드백", "user_pm", threshold=0.9)
        assert similar is None
