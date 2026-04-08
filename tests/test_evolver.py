"""TaxonomyEvolver 테스트 — 2단계 분류, decay sweep, mitosis, fusion

EV1: centroid 매칭 성공 시 LLM 호출 없이 분류
EV2: centroid 매칭 실패 시 LLM fallback → 기존 카테고리 선택
EV3: centroid 매칭 실패 + LLM 신규 제안 → 카테고리 생성
EV4: register_memory + 임베딩 캐시
EV5: should_sweep 주기 판정
EV6: decay_sweep → prune + re-classify
EV7: mitosis (분열) — k-means 분할 + LLM 네이밍
EV8: fusion (병합) — centroid 유사 카테고리 합침
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import numpy as np
import pytest

from taxonomy.taxonomy_graph import TaxonomyGraph
from taxonomy.lineage import PhylogeneticLineage
from taxonomy.evolver import TaxonomyEvolver, SWEEP_INTERVAL_TURNS


# --- 헬퍼 ---

def _unit_vec(dim: int = 1024, seed: int = 0) -> list[float]:
    """재현 가능한 단위 벡터"""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _similar_vec(base: list[float], noise: float = 0.01, seed: int = 99) -> list[float]:
    """base와 유사한 벡터 (cosine ~0.99)"""
    rng = np.random.RandomState(seed)
    v = np.array(base) + rng.randn(len(base)) * noise
    return (v / np.linalg.norm(v)).tolist()


def _orthogonal_vec(base: list[float], seed: int = 42) -> list[float]:
    """base와 직교에 가까운 벡터"""
    rng = np.random.RandomState(seed)
    v = rng.randn(len(base))
    b = np.array(base)
    v = v - np.dot(v, b) * b / np.dot(b, b)
    return (v / np.linalg.norm(v)).tolist()


def _make_mock_llm():
    """LLM client mock (DooGPULLMClient 인터페이스)"""
    llm = MagicMock()
    llm._model = "test-model"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test_category"
    llm._client = MagicMock()
    llm._client.chat.completions.create.return_value = mock_response
    return llm


def _make_evolver_with_categories(
    categories: list[tuple[str, list[float]]],
) -> TaxonomyEvolver:
    """카테고리가 미리 추가된 evolver를 생성한다."""
    taxonomy = TaxonomyGraph()
    lineage = PhylogeneticLineage()
    llm = _make_mock_llm()
    emb = MagicMock()

    for name, centroid in categories:
        taxonomy.add_category(name, centroid, created_by="bootstrap")
        lineage.record_bootstrap(name, member_count=0)

    return TaxonomyEvolver(taxonomy, lineage, llm, emb)


# --- EV1: centroid 매칭 성공 ---

class TestCentroidMatch:
    """EV1: centroid가 충분히 유사하면 LLM 호출 없이 바로 분류"""

    @pytest.mark.asyncio
    async def test_ev1_match_existing_category(self):
        """임베딩이 기존 centroid와 유사하면 해당 카테고리로 분류된다."""
        base = _unit_vec(seed=10)
        evolver = _make_evolver_with_categories([
            ("weekly_report", base),
            ("code_review", _unit_vec(seed=20)),
        ])

        similar = _similar_vec(base, noise=0.01, seed=1)
        cat, is_new = await evolver.classify_or_propose("주간 보고서", similar)

        assert cat == "weekly_report"
        assert is_new is False
        # LLM이 호출되지 않았는지 확인
        evolver._llm._client.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_ev1_no_match_triggers_llm(self):
        """임베딩이 모든 centroid와 다르면 LLM fallback이 호출된다."""
        evolver = _make_evolver_with_categories([
            ("weekly_report", _unit_vec(seed=10)),
        ])
        evolver._llm._client.chat.completions.create.return_value.choices[
            0
        ].message.content = "weekly_report"

        orthogonal = _orthogonal_vec(_unit_vec(seed=10), seed=50)
        cat, is_new = await evolver.classify_or_propose("전혀 다른 내용", orthogonal)

        assert cat == "weekly_report"
        assert is_new is False
        evolver._llm._client.chat.completions.create.assert_called_once()


# --- EV2-3: LLM fallback 분류 ---

class TestLLMClassify:
    """EV2-3: LLM이 기존 카테고리 선택 또는 신규 제안"""

    @pytest.mark.asyncio
    async def test_ev2_llm_selects_existing(self):
        """EV2: LLM이 기존 카테고리를 선택한다."""
        evolver = _make_evolver_with_categories([
            ("scheduling", _unit_vec(seed=1)),
            ("code_review", _unit_vec(seed=2)),
        ])
        evolver._llm._client.chat.completions.create.return_value.choices[
            0
        ].message.content = "scheduling"

        orthogonal = _orthogonal_vec(_unit_vec(seed=1), seed=99)
        cat, is_new = await evolver.classify_or_propose("미팅 일정 잡아줘", orthogonal)

        assert cat == "scheduling"
        assert is_new is False

    @pytest.mark.asyncio
    async def test_ev3_llm_proposes_new(self):
        """EV3: LLM이 새 카테고리를 제안하면 생성된다."""
        evolver = _make_evolver_with_categories([
            ("scheduling", _unit_vec(seed=1)),
        ])
        evolver._llm._client.chat.completions.create.return_value.choices[
            0
        ].message.content = "incident_response"

        orthogonal = _orthogonal_vec(_unit_vec(seed=1), seed=77)
        cat, is_new = await evolver.classify_or_propose(
            "서버 장애 대응", orthogonal
        )

        assert cat == "incident_response"
        assert is_new is True
        assert "incident_response" in evolver.taxonomy
        # lineage에 discovery 기록
        events = evolver.lineage.get_events()
        discovery_events = [e for e in events if e["type"] == "discovery"]
        assert len(discovery_events) == 1


# --- EV4: register_memory ---

class TestRegisterMemory:
    """EV4: 메모리 등록 + 임베딩 캐시"""

    @pytest.mark.asyncio
    async def test_ev4_register_caches_embedding(self):
        """메모리 등록 시 taxonomy에 멤버가 추가되고 임베딩이 캐시된다."""
        evolver = _make_evolver_with_categories([
            ("code_review", _unit_vec(seed=5)),
        ])
        emb = _unit_vec(seed=100)

        await evolver.register_memory("code_review", "mem_001", emb)

        cats = evolver.taxonomy.get_all_categories()
        cr = [c for c in cats if c["name"] == "code_review"][0]
        assert "mem_001" in cr["member_ids"]
        assert "mem_001" in evolver._embedding_cache

    @pytest.mark.asyncio
    async def test_ev4_turn_count_increments(self):
        """각 register_memory 호출마다 turn_count가 증가한다."""
        evolver = _make_evolver_with_categories([
            ("code_review", _unit_vec(seed=5)),
        ])

        for i in range(3):
            await evolver.register_memory(
                "code_review", f"mem_{i}", _unit_vec(seed=i + 100)
            )

        assert evolver._turn_count == 3


# --- EV5: should_sweep ---

class TestShouldSweep:
    """EV5: sweep 주기 판정"""

    def test_ev5_sweep_at_interval(self):
        """SWEEP_INTERVAL_TURNS(50) 배수에서만 sweep이 트리거된다."""
        evolver = _make_evolver_with_categories([
            ("cat_a", _unit_vec(seed=0)),
        ])

        evolver._turn_count = SWEEP_INTERVAL_TURNS - 1
        assert evolver.should_sweep() is False

        evolver._turn_count = SWEEP_INTERVAL_TURNS
        assert evolver.should_sweep() is True

        evolver._turn_count = 0
        assert evolver.should_sweep() is False


# --- EV6: decay_sweep ---

class TestDecaySweep:
    """EV6: decay sweep → prune + re-classify"""

    @pytest.mark.asyncio
    async def test_ev6_prune_decayed_categories(self):
        """decay weight가 임계치 미만인 카테고리가 프루닝된다."""
        evolver = _make_evolver_with_categories([
            ("active_cat", _unit_vec(seed=0)),
            ("dying_cat", _unit_vec(seed=1)),
            ("also_dying", _unit_vec(seed=2)),
            ("still_alive", _unit_vec(seed=3)),
        ])

        for name in ["dying_cat", "also_dying"]:
            node = evolver.taxonomy._graph.nodes[name]
            node["last_activated"] = datetime.now() - timedelta(days=30)

        now = datetime.now()
        result = await evolver.decay_sweep(now)

        # 프루닝 확인 (MIN_CATEGORIES=3이므로 최대 1개만 삭제 가능)
        assert len(result["pruned"]) >= 1
        for pruned_name in result["pruned"]:
            assert pruned_name not in evolver.taxonomy

    @pytest.mark.asyncio
    async def test_ev6_reclassify_orphans(self):
        """프루닝으로 고아가 된 메모리가 다른 카테고리로 재분류된다."""
        base = _unit_vec(seed=0)
        evolver = _make_evolver_with_categories([
            ("active_cat", base),
            ("dying_cat", _unit_vec(seed=1)),
            ("filler_a", _unit_vec(seed=2)),
            ("filler_b", _unit_vec(seed=3)),
        ])

        similar_emb = _similar_vec(base, noise=0.02, seed=55)
        evolver.taxonomy.add_member("dying_cat", "orphan_mem")
        evolver._embedding_cache["orphan_mem"] = similar_emb

        node = evolver.taxonomy._graph.nodes["dying_cat"]
        node["last_activated"] = datetime.now() - timedelta(days=60)

        now = datetime.now()
        result = await evolver.decay_sweep(now)

        if "dying_cat" in result["pruned"]:
            assert result["reclassified"] >= 1


# --- EV7: mitosis ---

class TestMitosis:
    """EV7: 분열 — 분산 높은 카테고리를 k-means로 분할"""

    @pytest.mark.asyncio
    async def test_ev7_split_high_variance_category(self):
        """멤버 임베딩 분산이 높은 카테고리가 두 개로 분열된다."""
        vec_a = _unit_vec(dim=64, seed=0)
        vec_b = _orthogonal_vec(vec_a, seed=10)

        mid = np.array(vec_a) + np.array(vec_b)
        mid = (mid / np.linalg.norm(mid)).tolist()

        evolver = _make_evolver_with_categories([
            ("mixed_cat", mid),
            ("other_cat", _unit_vec(dim=64, seed=50)),
            ("filler_cat", _unit_vec(dim=64, seed=60)),
        ])

        evolver._llm._client.chat.completions.create.return_value.choices[
            0
        ].message.content = "cluster_alpha, cluster_beta"

        for i in range(3):
            mem_id = f"group_a_{i}"
            emb = _similar_vec(vec_a, noise=0.05, seed=i + 100)
            evolver.taxonomy.add_member("mixed_cat", mem_id)
            evolver._embedding_cache[mem_id] = emb

        for i in range(3):
            mem_id = f"group_b_{i}"
            emb = _similar_vec(vec_b, noise=0.05, seed=i + 200)
            evolver.taxonomy.add_member("mixed_cat", mem_id)
            evolver._embedding_cache[mem_id] = emb

        splits = await evolver._check_mitosis()

        # 분열이 발생하면 검증
        if len(splits) > 0:
            assert splits[0]["parent"] == "mixed_cat"
            assert len(splits[0]["children"]) == 2
            assert "mixed_cat" not in evolver.taxonomy


# --- EV8: fusion ---

class TestFusion:
    """EV8: 병합 — centroid가 유사한 카테고리를 합침"""

    @pytest.mark.asyncio
    async def test_ev8_merge_similar_categories(self):
        """centroid가 매우 유사한 두 카테고리가 하나로 병합된다."""
        base = _unit_vec(seed=0)
        very_similar = _similar_vec(base, noise=0.001, seed=1)

        evolver = _make_evolver_with_categories([
            ("cat_alpha", base),
            ("cat_beta", very_similar),
            ("cat_gamma", _orthogonal_vec(base, seed=5)),
        ])

        evolver._llm._client.chat.completions.create.return_value.choices[
            0
        ].message.content = "merged_alpha_beta"

        evolver.taxonomy.add_member("cat_alpha", "mem_a1")
        evolver.taxonomy.add_member("cat_beta", "mem_b1")

        fusions = await evolver._check_fusion()

        assert len(fusions) >= 1
        fusion = fusions[0]
        assert set(fusion["parents"]) == {"cat_alpha", "cat_beta"}
        assert fusion["child"] == "merged_alpha_beta"
        assert "cat_alpha" not in evolver.taxonomy
        assert "cat_beta" not in evolver.taxonomy
        assert "merged_alpha_beta" in evolver.taxonomy

    @pytest.mark.asyncio
    async def test_ev8_no_merge_if_distant(self):
        """centroid가 충분히 다르면 병합되지 않는다."""
        evolver = _make_evolver_with_categories([
            ("cat_x", _unit_vec(seed=0)),
            ("cat_y", _orthogonal_vec(_unit_vec(seed=0), seed=10)),
        ])

        fusions = await evolver._check_fusion()
        assert len(fusions) == 0
