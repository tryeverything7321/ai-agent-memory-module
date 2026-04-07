"""Decay Engine 테스트 — Ebbinghaus 망각 곡선, 프루닝, 팩트 갱신

D1: 기본 decay 계산
D2: 곱셈형 boost
D3: critical 낮은 감쇠
D4: 프루닝 트리거
D5: 반복 접근 부스트
D6: 팩트 갱신
D7: 배치 프루닝
D8: λ 범위 검증
"""

import pytest
import math
from datetime import datetime, timedelta

from models import Memory, Importance
from decay import DecayEngine


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
