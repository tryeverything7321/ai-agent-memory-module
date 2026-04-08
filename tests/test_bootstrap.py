"""TaxonomyBootstrap 테스트 — 콜드스타트 k-means + LLM 네이밍 + EPHEMERAL 생성

BS1: 버퍼 추가 + is_ready 판정
BS2: 최적 k 결정 (silhouette score)
BS3: execute → TaxonomyGraph + Lineage 초기화
BS4: LLM 네이밍 실패 시 fallback 이름
BS5: EPHEMERAL 패턴 생성 (LLM)
BS6: EPHEMERAL 생성 실패 시 기본 패턴 fallback
BS7: 이중 execute 방지
"""

import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from taxonomy.bootstrap import (
    TaxonomyBootstrap,
    BUFFER_SIZE,
    K_MIN,
    K_MAX,
    DEFAULT_EPHEMERAL_PATTERNS,
)


# --- 헬퍼 ---

def _unit_vec(dim: int = 128, seed: int = 0) -> list[float]:
    """재현 가능한 단위 벡터 (테스트용 128-dim)"""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _cluster_vec(center_seed: int, noise: float = 0.1, seed: int = 0, dim: int = 128) -> list[float]:
    """center_seed 기반 클러스터에 속하는 노이즈 벡터"""
    rng = np.random.RandomState(seed)
    center = np.random.RandomState(center_seed).randn(dim)
    v = center + rng.randn(dim) * noise
    return (v / np.linalg.norm(v)).tolist()


def _make_mock_llm(cluster_names: list[str] = None, ephemeral_patterns: list[str] = None):
    """LLM client mock — 호출 순서에 따라 다른 응답 반환"""
    llm = MagicMock()
    llm._model = "test-model"
    llm._client = MagicMock()

    names_json = json.dumps(cluster_names or ["cat_a", "cat_b", "cat_c"])
    patterns_json = json.dumps(
        ephemeral_patterns or ["ㅋㅋ", "ㅎㅎ", "넵", "오키", "ㅇㅇ"] * 6
    )

    # 첫 번째 호출: 클러스터 이름, 두 번째: EPHEMERAL 패턴
    response_names = MagicMock()
    response_names.choices = [MagicMock()]
    response_names.choices[0].message.content = names_json

    response_patterns = MagicMock()
    response_patterns.choices = [MagicMock()]
    response_patterns.choices[0].message.content = patterns_json

    llm._client.chat.completions.create.side_effect = [
        response_names,
        response_patterns,
    ]
    return llm


def _fill_buffer(
    bootstrap: TaxonomyBootstrap,
    n_clusters: int = 3,
    per_cluster: int = 10,
    dim: int = 128,
) -> None:
    """n_clusters개 클러스터로 구성된 BUFFER_SIZE개 메시지를 버퍼에 추가"""
    idx = 0
    for cluster_id in range(n_clusters):
        for i in range(per_cluster):
            text = f"클러스터{cluster_id} 메시지{i}"
            emb = _cluster_vec(
                center_seed=cluster_id * 100,
                noise=0.05,
                seed=idx,
                dim=dim,
            )
            bootstrap.add_message(text, emb)
            idx += 1
            if idx >= BUFFER_SIZE:
                return


# --- BS1: 버퍼 + is_ready ---

class TestBufferAndReady:
    """BS1: 메시지 버퍼링과 준비 상태 판정"""

    def test_bs1_add_and_count(self):
        """메시지가 버퍼에 추가되고 크기가 증가한다."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)

        assert bs.buffer_size == 0
        bs.add_message("hello", _unit_vec(seed=0))
        assert bs.buffer_size == 1

    def test_bs1_not_ready_before_full(self):
        """BUFFER_SIZE 미만이면 is_ready는 False."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)

        for i in range(BUFFER_SIZE - 1):
            bs.add_message(f"msg_{i}", _unit_vec(seed=i))

        assert bs.is_ready() is False

    def test_bs1_ready_when_full(self):
        """BUFFER_SIZE에 도달하면 is_ready는 True."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs)

        assert bs.is_ready() is True

    def test_bs1_overflow_ignored(self):
        """BUFFER_SIZE 초과 메시지는 무시된다."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs)
        initial_size = bs.buffer_size

        bs.add_message("overflow", _unit_vec(seed=999))
        assert bs.buffer_size == initial_size


# --- BS2: 최적 k 결정 ---

class TestOptimalK:
    """BS2: silhouette score 기반 k 결정"""

    def test_bs2_find_optimal_k_in_range(self):
        """최적 k가 K_MIN~K_MAX 범위 내에 있다."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        embeddings = np.array([m["embedding"] for m in bs._buffer])
        best_k, labels, centroids = bs._find_optimal_k(embeddings)

        assert K_MIN <= best_k <= K_MAX
        assert len(labels) == len(embeddings)
        assert centroids.shape[0] == best_k


# --- BS3: execute ---

class TestExecute:
    """BS3: execute → TaxonomyGraph + Lineage 초기화"""

    @pytest.mark.asyncio
    async def test_bs3_creates_taxonomy_and_lineage(self):
        """execute가 taxonomy, lineage, ephemeral_patterns를 반환한다."""
        llm = _make_mock_llm(
            cluster_names=["reporting", "debugging", "scheduling"]
        )
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        taxonomy, lineage, patterns = await bs.execute()

        # taxonomy에 카테고리가 생성됨
        cats = taxonomy.get_all_categories()
        assert len(cats) >= K_MIN

        # lineage에 bootstrap 이벤트 기록됨
        events = lineage.get_events()
        bootstrap_events = [e for e in events if e["type"] == "bootstrap"]
        assert len(bootstrap_events) >= K_MIN

        # ephemeral 패턴이 반환됨
        assert len(patterns) >= 10

    @pytest.mark.asyncio
    async def test_bs3_members_assigned_to_categories(self):
        """모든 버퍼 메시지가 카테고리에 멤버로 할당된다."""
        llm = _make_mock_llm(
            cluster_names=["cat_a", "cat_b", "cat_c", "cat_d", "cat_e"]
        )
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        taxonomy, _, _ = await bs.execute()

        total_members = sum(
            c["member_count"] for c in taxonomy.get_all_categories()
        )
        assert total_members == BUFFER_SIZE


# --- BS4: LLM 네이밍 실패 fallback ---

class TestNamingFallback:
    """BS4: LLM 네이밍 실패 시 기본 이름"""

    @pytest.mark.asyncio
    async def test_bs4_fallback_names_on_llm_error(self):
        """LLM이 실패해도 category_1, category_2... 이름으로 생성된다."""
        llm = MagicMock()
        llm._model = "test-model"
        llm._client = MagicMock()
        # LLM 호출 시 예외 발생
        llm._client.chat.completions.create.side_effect = Exception("LLM down")

        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        taxonomy, lineage, patterns = await bs.execute()

        cats = taxonomy.get_all_categories()
        # fallback 이름 패턴 확인
        cat_names = [c["name"] for c in cats]
        assert any(name.startswith("category_") for name in cat_names)

        # ephemeral도 기본값으로 fallback
        assert patterns == list(DEFAULT_EPHEMERAL_PATTERNS)


# --- BS5-6: EPHEMERAL 패턴 ---

class TestEphemeralPatterns:
    """BS5-6: EPHEMERAL 패턴 LLM 생성 + fallback"""

    @pytest.mark.asyncio
    async def test_bs5_llm_generated_patterns(self):
        """LLM이 생성한 EPHEMERAL 패턴이 반환된다."""
        custom_patterns = [f"pattern_{i}" for i in range(30)]
        llm = _make_mock_llm(
            cluster_names=["cat_a", "cat_b", "cat_c"],
            ephemeral_patterns=custom_patterns,
        )
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        _, _, patterns = await bs.execute()

        assert len(patterns) == 30
        assert patterns[0] == "pattern_0"

    @pytest.mark.asyncio
    async def test_bs6_fallback_on_bad_json(self):
        """LLM이 잘못된 JSON을 반환하면 기본 패턴으로 fallback된다."""
        llm = MagicMock()
        llm._model = "test-model"
        llm._client = MagicMock()

        # 첫 번째 호출: 정상 클러스터 이름
        response_names = MagicMock()
        response_names.choices = [MagicMock()]
        response_names.choices[0].message.content = json.dumps(["cat_a", "cat_b", "cat_c"])

        # 두 번째 호출: 잘못된 JSON
        bad_response = MagicMock()
        bad_response.choices = [MagicMock()]
        bad_response.choices[0].message.content = "이건 JSON이 아닙니다"

        llm._client.chat.completions.create.side_effect = [
            response_names,
            bad_response,
        ]

        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        _, _, patterns = await bs.execute()
        assert patterns == list(DEFAULT_EPHEMERAL_PATTERNS)


# --- BS7: 이중 execute 방지 ---

class TestDoubleExecute:
    """BS7: 이미 실행된 bootstrap의 재실행 방지"""

    @pytest.mark.asyncio
    async def test_bs7_raises_on_double_execute(self):
        """execute를 두 번 호출하면 RuntimeError가 발생한다."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        await bs.execute()

        with pytest.raises(RuntimeError, match="이미 bootstrap"):
            await bs.execute()

    @pytest.mark.asyncio
    async def test_bs7_add_after_execute_raises(self):
        """execute 후 add_message를 호출하면 RuntimeError가 발생한다."""
        llm = _make_mock_llm()
        bs = TaxonomyBootstrap(llm)
        _fill_buffer(bs, n_clusters=3)

        await bs.execute()

        with pytest.raises(RuntimeError, match="이미 bootstrap"):
            bs.add_message("late msg", _unit_vec(seed=999))
