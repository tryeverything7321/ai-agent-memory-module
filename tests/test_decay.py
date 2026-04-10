"""Decay Engine 테스트 — Ebbinghaus 망각 곡선, 프루닝, 팩트 갱신, 그래프 전파

D1: 기본 decay 계산
D2: 곱셈형 boost
D3: critical 낮은 감쇠
D4: 프루닝 트리거
D5: 반복 접근 부스트
D6: 팩트 갱신
D7: 배치 프루닝
D8: λ 범위 검증
GP1: 단일 홉 무효화 전파
GP2: 다중 홉 체인 전파 (A→B→C)
GP3: 대안 경로 보존 (in-degree > 1)
GP4: 전파 깊이 제한
GP5: 무효화 대상이 그래프에 없는 경우
"""

import pytest
import math
from datetime import datetime, timedelta

from models import Memory, Importance
from decay import DecayEngine
from storage.graph_store import GraphStore


class TestDecayCalculation:
    """D1-D3: 기본 decay 수식"""

    def test_d1_basic_decay(self):
        """D1: w(t) = e^(-λt) * (1 + boost * access_count), λ=0.3, t=7, access=0"""
        engine = DecayEngine()
        weight = engine.calculate_weight(lambda_val=0.3, days_elapsed=7, access_count=0)
        expected = math.exp(-0.3 * 7) * (1 + 0.05 * 0)  # ≈ 0.122
        assert abs(weight - expected) < 0.001

    def test_d2_multiplicative_boost(self):
        """D2: 곱셈형 boost — λ=0.3, t=8, access=1"""
        engine = DecayEngine()
        weight = engine.calculate_weight(lambda_val=0.3, days_elapsed=8, access_count=1)
        expected = math.exp(-0.3 * 8) * (1 + 0.05 * 1)  # ≈ 0.095
        assert abs(weight - expected) < 0.001

    def test_d3_critical_low_decay(self):
        """D3: critical 메모리 — λ=0.005, t=30"""
        engine = DecayEngine()
        weight = engine.calculate_weight(lambda_val=0.005, days_elapsed=30, access_count=0)
        expected = math.exp(-0.005 * 30)  # ≈ 0.861
        assert weight > 0.85

    def test_d2_boost_never_exceeds_decay(self):
        """곱셈형이므로 boost가 있어도 시간이 충분히 지나면 0에 수렴"""
        engine = DecayEngine()
        # 매우 높은 access_count여도 365일 후엔 거의 0
        weight = engine.calculate_weight(lambda_val=0.3, days_elapsed=365, access_count=100)
        assert weight < 0.01

    def test_d8_lambda_range_validation(self):
        """D8: λ < 0 or λ > 1 → ValueError"""
        engine = DecayEngine()
        with pytest.raises(ValueError):
            engine.calculate_weight(lambda_val=-0.1, days_elapsed=1, access_count=0)
        with pytest.raises(ValueError):
            engine.calculate_weight(lambda_val=1.5, days_elapsed=1, access_count=0)


class TestPruning:
    """D4, D7: 프루닝"""

    async def test_d4_prune_trigger(self, metadata_store):
        """D4: weight < threshold → 삭제"""
        engine = DecayEngine()

        # 살아남을 메모리 (critical, 최근)
        alive = Memory(
            user_id="u", content="중요 메모리",
            importance=Importance.critical, decay_lambda=0.005, decay_weight=0.9,
        )
        # 죽을 메모리 (ephemeral, 오래됨)
        dead = Memory(
            user_id="u", content="오래된 잡담",
            importance=Importance.ephemeral, decay_lambda=0.3, decay_weight=0.05,
        )
        await metadata_store.save_memory(alive)
        await metadata_store.save_memory(dead)

        pruned = await engine.prune(metadata_store, threshold=0.1)
        assert pruned == 1
        assert await metadata_store.get_memory(alive.id) is not None
        assert await metadata_store.get_memory(dead.id) is None

    async def test_d7_batch_prune(self, metadata_store):
        """D7: 100건 중 30건 임계치 미달 → 30건 삭제"""
        engine = DecayEngine()

        for i in range(100):
            weight = 0.05 if i < 30 else 0.5
            mem = Memory(user_id="u", content=f"mem_{i}", decay_weight=weight)
            await metadata_store.save_memory(mem)

        pruned = await engine.prune(metadata_store, threshold=0.1)
        assert pruned == 30

        remaining = await metadata_store.get_memories_by_user("u")
        assert len(remaining) == 70


class TestAccessBoost:
    """D5: 반복 접근 부스트"""

    async def test_d5_access_boost(self, metadata_store):
        """접근할 때마다 access_count 증가 → weight에 반영"""
        engine = DecayEngine()

        mem = Memory(
            user_id="u", content="테스트",
            decay_lambda=0.3,
            created_at=datetime.now() - timedelta(days=5),
        )
        await metadata_store.save_memory(mem)

        # 3회 접근
        for _ in range(3):
            await metadata_store.update_access(mem.id)

        updated = await metadata_store.get_memory(mem.id)
        assert updated.access_count == 3

        # access_count=3일 때 weight가 access_count=0보다 높음
        w_with_access = engine.calculate_weight(0.3, 5, access_count=3)
        w_without = engine.calculate_weight(0.3, 5, access_count=0)
        assert w_with_access > w_without


class TestFactUpdate:
    """D6: 팩트 갱신"""

    async def test_d6_invalidate_and_replace(self, metadata_store):
        """기존 fact 무효화 + 새 fact 생성"""
        engine = DecayEngine()

        old = Memory(
            user_id="u", content="다음 달에 판교로 이사",
            importance=Importance.critical,
        )
        await metadata_store.save_memory(old)

        # 이사 취소 → 기존 무효화 + 새 사실 생성
        await engine.update_fact(
            metadata_store, old.id, "이사 취소됨", "u"
        )

        old_mem = await metadata_store.get_memory(old.id)
        assert old_mem.is_valid is False

        # 새 메모리가 생성되었는지 확인
        all_mems = await metadata_store.get_memories_by_user("u", valid_only=True)
        assert any("이사 취소" in m.content for m in all_mems)


class TestGraphPropagation:
    """GP1-GP5: Graph-aware Selective Forgetting

    교통공학 link failure propagation 적용:
    수식: w_final(m) = w(t,m) * (decay_per_hop ^ hop_distance)
    in-degree > 1인 entity → penalty를 1/in_degree로 축소
    """

    async def _setup_chain(self, metadata_store, graph_store):
        """A→B→C 체인 그래프 + 각 entity에 memory 연결

        메모리 구조:
          mem_a ← entity "프로젝트X" (source)
          mem_b ← entity "김철수" (1홉)
          mem_c ← entity "판교사무실" (2홉)
        그래프: 프로젝트X → 김철수 → 판교사무실
        """
        mem_a = Memory(user_id="u", content="프로젝트X 관련 정보", decay_weight=1.0)
        mem_b = Memory(user_id="u", content="김철수 담당 정보", decay_weight=0.8)
        mem_c = Memory(user_id="u", content="판교사무실 위치 정보", decay_weight=0.9)
        for m in [mem_a, mem_b, mem_c]:
            await metadata_store.save_memory(m)

        graph_store.add_entity("프로젝트X", entity_type="project", memory_id=mem_a.id)
        graph_store.add_entity("김철수", entity_type="person", memory_id=mem_b.id)
        graph_store.add_entity("판교사무실", entity_type="place", memory_id=mem_c.id)
        graph_store.add_relation("프로젝트X", "김철수", "담당")
        graph_store.add_relation("김철수", "판교사무실", "위치")

        return mem_a, mem_b, mem_c

    async def test_gp1_single_hop_propagation(self, metadata_store, graph_store):
        """GP1: 1홉 전파 — 무효화된 memory의 이웃 entity memory에 decay_per_hop 적용"""
        mem_a, mem_b, mem_c = await self._setup_chain(metadata_store, graph_store)
        engine = DecayEngine()

        affected = await engine.propagate_invalidation(
            invalidated_memory_id=mem_a.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
            propagation_depth=1,
            decay_per_hop=0.5,
        )

        # mem_b는 1홉 → weight = 0.8 * 0.5 = 0.4
        updated_b = await metadata_store.get_memory(mem_b.id)
        assert abs(updated_b.decay_weight - 0.4) < 0.001

        # mem_c는 2홉이므로 depth=1에서 미영향
        updated_c = await metadata_store.get_memory(mem_c.id)
        assert abs(updated_c.decay_weight - 0.9) < 0.001

        assert mem_b.id in affected
        assert mem_c.id not in affected

    async def test_gp2_multi_hop_chain(self, metadata_store, graph_store):
        """GP2: 2홉 체인 전파 — A→B→C, depth=2"""
        mem_a, mem_b, mem_c = await self._setup_chain(metadata_store, graph_store)
        engine = DecayEngine()

        affected = await engine.propagate_invalidation(
            invalidated_memory_id=mem_a.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
            propagation_depth=2,
            decay_per_hop=0.5,
        )

        # mem_b: 1홉 → 0.8 * 0.5^1 = 0.4
        updated_b = await metadata_store.get_memory(mem_b.id)
        assert abs(updated_b.decay_weight - 0.4) < 0.001

        # mem_c: 2홉 → 0.9 * 0.5^2 = 0.225
        updated_c = await metadata_store.get_memory(mem_c.id)
        assert abs(updated_c.decay_weight - 0.225) < 0.001

        assert mem_b.id in affected
        assert mem_c.id in affected

    async def test_gp3_alternative_route_resilience(self, metadata_store, graph_store):
        """GP3: 대안 경로 보존 — in-degree > 1이면 penalty를 1/in_degree로 축소

        그래프: 프로젝트X → 김철수 ← 프로젝트Y (김철수 in-degree=2)
        프로젝트X 무효화 시, 김철수는 프로젝트Y에서도 연결되므로 penalty 축소
        """
        mem_a = Memory(user_id="u", content="프로젝트X 정보", decay_weight=1.0)
        mem_b = Memory(user_id="u", content="김철수 정보", decay_weight=0.8)
        mem_y = Memory(user_id="u", content="프로젝트Y 정보", decay_weight=1.0)
        for m in [mem_a, mem_b, mem_y]:
            await metadata_store.save_memory(m)

        graph_store.add_entity("프로젝트X", entity_type="project", memory_id=mem_a.id)
        graph_store.add_entity("김철수", entity_type="person", memory_id=mem_b.id)
        graph_store.add_entity("프로젝트Y", entity_type="project", memory_id=mem_y.id)
        graph_store.add_relation("프로젝트X", "김철수", "담당")
        graph_store.add_relation("프로젝트Y", "김철수", "참여")

        engine = DecayEngine()
        affected = await engine.propagate_invalidation(
            invalidated_memory_id=mem_a.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
            propagation_depth=1,
            decay_per_hop=0.5,
        )

        # 김철수 in-degree=2 → penalty = 0.5 * (1/2) = 0.25
        # w_final = 0.8 * (1 - 0.25) = 0.8 * 0.75 = 0.6
        # 대안: penalty_factor = decay_per_hop^hop / in_degree = 0.5/2 = 0.25
        # w_final = 0.8 * (1 - 0.25) = 0.6
        updated_b = await metadata_store.get_memory(mem_b.id)
        # in-degree=2이므로 단순 1홉(0.4)보다 높아야 함
        assert updated_b.decay_weight > 0.4
        # 하지만 원래(0.8)보다는 낮아야 함
        assert updated_b.decay_weight < 0.8
        assert mem_b.id in affected

    async def test_gp4_depth_limit(self, metadata_store, graph_store):
        """GP4: propagation_depth=0 → 전파 없음"""
        mem_a, mem_b, mem_c = await self._setup_chain(metadata_store, graph_store)
        engine = DecayEngine()

        affected = await engine.propagate_invalidation(
            invalidated_memory_id=mem_a.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
            propagation_depth=0,
            decay_per_hop=0.5,
        )

        # 전파 없음
        assert affected == []
        updated_b = await metadata_store.get_memory(mem_b.id)
        assert abs(updated_b.decay_weight - 0.8) < 0.001

    async def test_gp5_no_graph_connection(self, metadata_store, graph_store):
        """GP5: 무효화 대상 memory가 그래프에 연결되지 않은 경우 → 빈 리스트"""
        orphan = Memory(user_id="u", content="고립된 메모리", decay_weight=1.0)
        await metadata_store.save_memory(orphan)

        engine = DecayEngine()
        affected = await engine.propagate_invalidation(
            invalidated_memory_id=orphan.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
        )
        assert affected == []

    async def test_gp6_update_fact_with_propagation(self, metadata_store, graph_store):
        """GP6: update_fact(propagate=True) → 무효화 + 전파 자동 실행"""
        # 프로젝트X → 김철수 체인
        mem_old = Memory(user_id="u", content="프로젝트X 담당=김철수", decay_weight=1.0)
        mem_related = Memory(user_id="u", content="김철수 연락처", decay_weight=0.8)
        for m in [mem_old, mem_related]:
            await metadata_store.save_memory(m)

        graph_store.add_entity("프로젝트X", entity_type="project", memory_id=mem_old.id)
        graph_store.add_entity("김철수", entity_type="person", memory_id=mem_related.id)
        graph_store.add_relation("프로젝트X", "김철수", "담당")

        engine = DecayEngine()
        new_mem = await engine.update_fact(
            metadata_store, mem_old.id, "프로젝트X 담당=박영희", "u",
            graph_store=graph_store, propagate=True,
        )

        # 기존 메모리 무효화
        old = await metadata_store.get_memory(mem_old.id)
        assert old.is_valid is False

        # 새 메모리 생성
        assert "박영희" in new_mem.content

        # 연결된 메모리에 전파 (0.8 * 0.5 = 0.4)
        related = await metadata_store.get_memory(mem_related.id)
        assert related.decay_weight < 0.8

    async def test_gp8_semantic_filter(self, metadata_store, graph_store):
        """GP8: semantic_filter=True → source 키워드와 관련된 메모리만 전파

        프로젝트X → 김철수 → 판교사무실
        프로젝트X 무효화 시:
          - 김철수 담당 정보 (프로젝트X 언급) → 전파 O
          - 판교사무실 위치 정보 (프로젝트X 미언급) → 전파 X
        """
        mem_a = Memory(user_id="u", content="프로젝트X 관련 정보", decay_weight=1.0)
        mem_b = Memory(user_id="u", content="김철수가 프로젝트X를 담당", decay_weight=0.8)
        mem_c = Memory(user_id="u", content="판교사무실은 3층에 위치", decay_weight=0.9)
        for m in [mem_a, mem_b, mem_c]:
            await metadata_store.save_memory(m)

        graph_store.add_entity("프로젝트X", entity_type="project", memory_id=mem_a.id)
        graph_store.add_entity("김철수", entity_type="person", memory_id=mem_b.id)
        graph_store.add_entity("판교사무실", entity_type="place", memory_id=mem_c.id)
        graph_store.add_relation("프로젝트X", "김철수", "담당")
        graph_store.add_relation("김철수", "판교사무실", "위치")

        engine = DecayEngine()
        # 프로젝트X가 폐지됨 → new_content에 "프로젝트X" 없음
        affected = await engine.propagate_invalidation(
            invalidated_memory_id=mem_a.id,
            graph_store=graph_store,
            metadata_store=metadata_store,
            propagation_depth=2,
            decay_per_hop=0.5,
            semantic_filter=True,
            new_content="프로젝트Y가 새로 시작되었다",  # 프로젝트X 없음 → changed entity
        )

        # mem_b: "프로젝트X" 포함 (changed entity) → 전파 O
        updated_b = await metadata_store.get_memory(mem_b.id)
        assert updated_b.decay_weight < 0.8
        assert mem_b.id in affected

        # mem_c: "프로젝트X" 미포함 → 전파 X (collateral damage 방지)
        updated_c = await metadata_store.get_memory(mem_c.id)
        assert abs(updated_c.decay_weight - 0.9) < 0.001
        assert mem_c.id not in affected

    async def test_gp7_update_fact_without_propagation(self, metadata_store, graph_store):
        """GP7: propagate=False → 기존 동작 유지 (전파 없음)"""
        mem_old = Memory(user_id="u", content="프로젝트Y 정보", decay_weight=1.0)
        mem_related = Memory(user_id="u", content="관련 정보", decay_weight=0.8)
        for m in [mem_old, mem_related]:
            await metadata_store.save_memory(m)

        graph_store.add_entity("프로젝트Y", entity_type="project", memory_id=mem_old.id)
        graph_store.add_entity("관련엔티티", entity_type="misc", memory_id=mem_related.id)
        graph_store.add_relation("프로젝트Y", "관련엔티티", "참조")

        engine = DecayEngine()
        await engine.update_fact(
            metadata_store, mem_old.id, "프로젝트Y 변경됨", "u",
            propagate=False,
        )

        # 전파 없음 — weight 유지
        related = await metadata_store.get_memory(mem_related.id)
        assert abs(related.decay_weight - 0.8) < 0.001
