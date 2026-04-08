"""TaxonomyGraph 테스트 — 동적 카테고리 그래프 CRUD, decay, split, merge, 직렬화

TG1: 카테고리 추가 및 조회
TG2: 활성화 시 centroid 증분 업데이트
TG3: 최적 매칭 (임계치 이상/이하)
TG4: decay weight 계산
TG5: 프루닝 시 MIN_CATEGORIES 보장
TG6: 카테고리 분열
TG7: 카테고리 융합
TG8: JSON 직렬화/역직렬화 왕복
"""

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from taxonomy.taxonomy_graph import (
    TaxonomyGraph,
    BOOST,
    ACCESS_COUNT_CAP,
    MIN_CATEGORIES,
    MAX_CATEGORIES,
)


# --- 헬퍼 ---

def _random_unit_vector(dim: int = 1024, seed: int = 0) -> list[float]:
    """재현 가능한 단위 벡터를 생성한다."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _make_graph_with_categories(n: int = 5) -> TaxonomyGraph:
    """n개 카테고리가 포함된 그래프를 생성한다."""
    g = TaxonomyGraph()
    for i in range(n):
        g.add_category(
            name=f"cat_{i}",
            centroid=_random_unit_vector(seed=i),
            created_by="bootstrap",
        )
    return g


class TestAddAndGetCategory:
    """TG1: 카테고리 추가 및 조회"""

    def test_add_category_basic(self):
        """기본 카테고리 추가 후 조회"""
        g = TaxonomyGraph()
        centroid = _random_unit_vector(seed=42)
        g.add_category("weekly_report", centroid, created_by="bootstrap")

        cats = g.get_all_categories()
        assert len(cats) == 1
        assert cats[0]["name"] == "weekly_report"
        assert cats[0]["member_count"] == 0
        assert cats[0]["member_ids"] == []
        assert cats[0]["decay_weight"] == 1.0
        assert cats[0]["access_count"] == 0
        assert cats[0]["created_by"] == "bootstrap"

    def test_add_duplicate_raises(self):
        """중복 카테고리 추가 시 ValueError"""
        g = TaxonomyGraph()
        g.add_category("dup", _random_unit_vector())
        with pytest.raises(ValueError, match="이미 존재"):
            g.add_category("dup", _random_unit_vector())

    def test_max_categories_limit(self):
        """MAX_CATEGORIES 초과 시 ValueError"""
        g = TaxonomyGraph()
        for i in range(MAX_CATEGORIES):
            g.add_category(f"cat_{i}", _random_unit_vector(seed=i))

        with pytest.raises(ValueError, match="최대 카테고리"):
            g.add_category("overflow", _random_unit_vector(seed=999))

    def test_add_member(self):
        """멤버 추가 시 member_ids와 member_count 갱신"""
        g = TaxonomyGraph()
        g.add_category("test_cat", _random_unit_vector())

        g.add_member("test_cat", "mem_001")
        g.add_member("test_cat", "mem_002")
        # 중복 추가 무시
        g.add_member("test_cat", "mem_001")

        cats = g.get_all_categories()
        assert cats[0]["member_count"] == 2
        assert set(cats[0]["member_ids"]) == {"mem_001", "mem_002"}

    def test_contains_and_len(self):
        """__contains__와 __len__ 동작 확인"""
        g = _make_graph_with_categories(3)
        assert len(g) == 3
        assert "cat_0" in g
        assert "nonexistent" not in g


class TestActivateUpdatesCentroid:
    """TG2: 활성화 시 centroid 증분 업데이트 검증"""

    def test_incremental_centroid_formula(self):
        """new_centroid = (old * n + new) / (n + 1) 공식 검증"""
        g = TaxonomyGraph()
        old_centroid = [1.0, 0.0, 0.0]
        g.add_category("test", old_centroid)

        # member_count=0인 상태에서 활성화
        # centroid = (old * 0 + new) / 1 = new
        new_emb = [0.0, 1.0, 0.0]
        g.activate_category("test", new_emb)

        node = g._graph.nodes["test"]
        expected = np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(node["centroid"], expected.tolist(), atol=1e-9)
        assert node["access_count"] == 1

    def test_incremental_centroid_with_members(self):
        """멤버가 있을 때 증분 업데이트 공식 확인"""
        g = TaxonomyGraph()
        old_centroid = [1.0, 0.0, 0.0]
        g.add_category("test", old_centroid)

        # 멤버 2개 추가하여 member_count=2로 설정
        g.add_member("test", "m1")
        g.add_member("test", "m2")

        new_emb = [0.0, 3.0, 0.0]
        g.activate_category("test", new_emb)

        # centroid = ([1,0,0] * 2 + [0,3,0]) / 3 = [2/3, 1, 0]
        node = g._graph.nodes["test"]
        expected = [2.0 / 3.0, 1.0, 0.0]
        np.testing.assert_allclose(node["centroid"], expected, atol=1e-9)

    def test_activate_nonexistent_raises(self):
        """존재하지 않는 카테고리 활성화 시 KeyError"""
        g = TaxonomyGraph()
        with pytest.raises(KeyError, match="찾을 수 없습니다"):
            g.activate_category("ghost", [1.0, 0.0])


class TestGetBestMatch:
    """TG3: 최적 매칭 — 임계치 이상/이하"""

    def test_exact_match_above_threshold(self):
        """centroid와 동일한 벡터 → 유사도 1.0 → 매칭 성공"""
        g = TaxonomyGraph()
        centroid = _random_unit_vector(seed=10)
        g.add_category("exact", centroid)

        result = g.get_best_match(centroid, threshold=0.6)
        assert result == "exact"

    def test_orthogonal_below_threshold(self):
        """직교 벡터 → 유사도 ≈ 0 → 매칭 실패"""
        g = TaxonomyGraph()
        # dim=3으로 직교 벡터 생성
        g.add_category("x_axis", [1.0, 0.0, 0.0])

        result = g.get_best_match([0.0, 1.0, 0.0], threshold=0.6)
        assert result is None

    def test_best_among_multiple(self):
        """여러 카테고리 중 가장 유사한 것을 반환"""
        g = TaxonomyGraph()
        g.add_category("a", [1.0, 0.0, 0.0])
        g.add_category("b", [0.0, 1.0, 0.0])
        g.add_category("c", [0.0, 0.0, 1.0])

        # a에 가장 가까운 쿼리
        query = [0.9, 0.1, 0.0]
        result = g.get_best_match(query, threshold=0.5)
        assert result == "a"

    def test_empty_graph_returns_none(self):
        """빈 그래프에서 매칭 시 None"""
        g = TaxonomyGraph()
        result = g.get_best_match([1.0, 0.0, 0.0])
        assert result is None


class TestDecayWeightCalculation:
    """TG4: decay weight 계산"""

    def test_decay_formula(self):
        """w = exp(-λ * hours) * (1 + boost * min(access_count, 20))"""
        g = TaxonomyGraph()
        g.add_category("test", [1.0, 0.0])

        # 24시간 전 활성화, access_count=5
        node = g._graph.nodes["test"]
        node["last_activated"] = datetime.now() - timedelta(hours=24)
        node["access_count"] = 5

        now = datetime.now()
        g.decay_all(now)

        hours = 24.0
        expected = math.exp(-0.1 * hours) * (1 + BOOST * 5)
        assert abs(node["decay_weight"] - expected) < 0.01

    def test_access_count_cap_at_20(self):
        """access_count가 20을 초과해도 20으로 cap"""
        g = TaxonomyGraph()
        g.add_category("capped", [1.0])

        node = g._graph.nodes["capped"]
        node["last_activated"] = datetime.now() - timedelta(hours=10)
        node["access_count"] = 100  # cap 초과

        now = datetime.now()
        g.decay_all(now)

        hours = 10.0
        # access_count=100이지만 min(100, 20)=20 적용
        expected = math.exp(-0.1 * hours) * (1 + BOOST * ACCESS_COUNT_CAP)
        assert abs(node["decay_weight"] - expected) < 0.01

    def test_recently_activated_high_weight(self):
        """방금 활성화된 카테고리는 weight ≈ 1.0"""
        g = TaxonomyGraph()
        g.add_category("fresh", [1.0])

        g.decay_all(datetime.now())

        node = g._graph.nodes["fresh"]
        assert node["decay_weight"] > 0.99

    def test_old_category_low_weight(self):
        """오래된 카테고리는 weight가 낮다"""
        g = TaxonomyGraph()
        g.add_category("old", [1.0])

        node = g._graph.nodes["old"]
        node["last_activated"] = datetime.now() - timedelta(hours=200)

        g.decay_all(datetime.now())
        # exp(-0.1 * 200) = exp(-20) ≈ 2e-9 → 매우 작음
        assert node["decay_weight"] < 0.001


class TestPruneRespectsMinCategories:
    """TG5: 프루닝 시 MIN_CATEGORIES(3) 보장"""

    def test_prune_returns_low_weight_candidates(self):
        """임계치 미달 카테고리를 후보로 반환"""
        g = _make_graph_with_categories(5)

        # cat_0, cat_1을 낮은 weight로 설정
        g._graph.nodes["cat_0"]["decay_weight"] = 0.01
        g._graph.nodes["cat_1"]["decay_weight"] = 0.02
        # 나머지는 높은 weight
        for i in range(2, 5):
            g._graph.nodes[f"cat_{i}"]["decay_weight"] = 0.8

        candidates = g.get_candidates_for_prune(threshold=0.05)
        assert set(candidates) == {"cat_0", "cat_1"}

    def test_prune_respects_min_categories(self):
        """프루닝으로 MIN_CATEGORIES 미만으로 줄어들지 않는다"""
        g = _make_graph_with_categories(4)

        # 모든 카테고리를 낮은 weight로 설정
        for i in range(4):
            g._graph.nodes[f"cat_{i}"]["decay_weight"] = 0.01

        candidates = g.get_candidates_for_prune(threshold=0.05)
        # 4 - MIN_CATEGORIES(3) = 1개만 프루닝 가능
        assert len(candidates) == 1

    def test_prune_empty_when_at_min(self):
        """MIN_CATEGORIES 이하일 때는 프루닝 후보 없음"""
        g = _make_graph_with_categories(MIN_CATEGORIES)

        for i in range(MIN_CATEGORIES):
            g._graph.nodes[f"cat_{i}"]["decay_weight"] = 0.001

        candidates = g.get_candidates_for_prune(threshold=0.05)
        assert candidates == []

    def test_remove_category_returns_orphans(self):
        """카테고리 제거 시 고아 멤버 ID 반환"""
        g = TaxonomyGraph()
        g.add_category("dying", _random_unit_vector())
        g.add_member("dying", "m1")
        g.add_member("dying", "m2")

        orphans = g.remove_category("dying")
        assert set(orphans) == {"m1", "m2"}
        assert "dying" not in g


class TestSplitCategory:
    """TG6: 카테고리 분열"""

    def test_split_replaces_parent(self):
        """분열 후 부모 제거, 자식 2개 생성"""
        g = TaxonomyGraph()
        g.add_category("parent", [1.0, 0.0, 0.0])
        g.add_member("parent", "m1")
        g.add_member("parent", "m2")
        g.add_member("parent", "m3")

        g.split_category(
            parent_name="parent",
            child_a="child_left",
            child_b="child_right",
            members_a=["m1", "m2"],
            members_b=["m3"],
            centroid_a=[1.0, 0.0, 0.0],
            centroid_b=[0.0, 1.0, 0.0],
        )

        assert "parent" not in g
        assert "child_left" in g
        assert "child_right" in g

        left = g._graph.nodes["child_left"]
        right = g._graph.nodes["child_right"]
        assert left["member_count"] == 2
        assert left["member_ids"] == ["m1", "m2"]
        assert left["created_by"] == "split"
        assert right["member_count"] == 1
        assert right["member_ids"] == ["m3"]

    def test_split_nonexistent_raises(self):
        """존재하지 않는 카테고리 분열 시 KeyError"""
        g = TaxonomyGraph()
        with pytest.raises(KeyError):
            g.split_category("ghost", "a", "b", [], [], [0], [0])

    def test_get_candidates_for_split_without_embeddings(self):
        """임베딩 없이 멤버 수 기준만으로 후보 선정"""
        g = TaxonomyGraph()
        g.add_category("big", _random_unit_vector(seed=1))
        g.add_category("small", _random_unit_vector(seed=2))

        for i in range(10):
            g.add_member("big", f"m_{i}")
        g.add_member("small", "m_only")

        candidates = g.get_candidates_for_split(min_size=5)
        assert "big" in candidates
        assert "small" not in candidates

    def test_get_candidates_for_split_with_embeddings(self):
        """임베딩 제공 시 분산 기반 후보 선정"""
        g = TaxonomyGraph()
        # centroid는 x축 방향
        g.add_category("spread", [1.0, 0.0, 0.0])

        member_ids = [f"m_{i}" for i in range(6)]
        for mid in member_ids:
            g.add_member("spread", mid)

        # 멤버 임베딩을 centroid에서 멀리 분산시킴 (높은 variance)
        embeddings = {}
        for i, mid in enumerate(member_ids):
            if i % 2 == 0:
                embeddings[mid] = [1.0, 0.0, 0.0]
            else:
                embeddings[mid] = [0.0, 1.0, 0.0]  # 직교 → distance ≈ 1.0

        candidates = g.get_candidates_for_split(
            split_threshold=0.3, min_size=5, embeddings=embeddings
        )
        assert "spread" in candidates


class TestMergeCategories:
    """TG7: 카테고리 융합"""

    def test_merge_combines_members(self):
        """융합 시 멤버와 접근 횟수가 합산된다"""
        g = TaxonomyGraph()
        g.add_category("a", [1.0, 0.0])
        g.add_category("b", [0.0, 1.0])

        g.add_member("a", "m1")
        g.add_member("a", "m2")
        g.add_member("b", "m3")

        g._graph.nodes["a"]["access_count"] = 5
        g._graph.nodes["b"]["access_count"] = 3

        g.merge_categories("a", "b", "merged_ab", [0.5, 0.5])

        assert "a" not in g
        assert "b" not in g
        assert "merged_ab" in g

        merged = g._graph.nodes["merged_ab"]
        assert merged["member_count"] == 3
        assert set(merged["member_ids"]) == {"m1", "m2", "m3"}
        assert merged["access_count"] == 8
        assert merged["created_by"] == "merge"
        np.testing.assert_allclose(merged["centroid"], [0.5, 0.5])

    def test_merge_nonexistent_raises(self):
        """존재하지 않는 카테고리 융합 시 KeyError"""
        g = TaxonomyGraph()
        g.add_category("exists", [1.0])
        with pytest.raises(KeyError):
            g.merge_categories("exists", "ghost", "new", [1.0])

    def test_get_candidates_for_fusion(self):
        """유사한 centroid 쌍을 융합 후보로 반환"""
        g = TaxonomyGraph()
        # 거의 동일한 두 카테고리
        g.add_category("twin_a", [1.0, 0.0, 0.0])
        g.add_category("twin_b", [0.99, 0.01, 0.0])
        # 완전히 다른 카테고리
        g.add_category("different", [0.0, 0.0, 1.0])

        pairs = g.get_candidates_for_fusion(merge_threshold=0.85)
        assert len(pairs) == 1
        pair = pairs[0]
        assert set(pair) == {"twin_a", "twin_b"}


class TestSerialization:
    """TG8: JSON 직렬화/역직렬화 왕복"""

    def test_round_trip(self):
        """to_json → from_json 왕복 후 데이터 동일성 확인"""
        g = TaxonomyGraph()
        centroid_a = _random_unit_vector(seed=100)
        centroid_b = _random_unit_vector(seed=200)

        g.add_category("cat_a", centroid_a, created_by="bootstrap")
        g.add_category("cat_b", centroid_b, created_by="discovery")

        g.add_member("cat_a", "m1")
        g.add_member("cat_a", "m2")
        g.add_member("cat_b", "m3")

        g._graph.nodes["cat_a"]["access_count"] = 10
        g._graph.nodes["cat_b"]["decay_weight"] = 0.5

        # 직렬화 → 역직렬화
        json_data = g.to_json()
        restored = TaxonomyGraph.from_json(json_data)

        # 카테고리 수 동일
        assert len(restored) == 2

        # 노드 데이터 동일성 확인
        for name in ["cat_a", "cat_b"]:
            orig = g._graph.nodes[name]
            rest = restored._graph.nodes[name]

            assert rest["name"] == orig["name"]
            np.testing.assert_allclose(rest["centroid"], orig["centroid"])
            assert rest["member_count"] == orig["member_count"]
            assert rest["member_ids"] == orig["member_ids"]
            assert rest["access_count"] == orig["access_count"]
            assert rest["decay_weight"] == orig["decay_weight"]
            assert rest["created_by"] == orig["created_by"]
            # datetime 왕복 정밀도 확인 (마이크로초 이내)
            assert abs(
                (rest["created_at"] - orig["created_at"]).total_seconds()
            ) < 0.001
            assert abs(
                (rest["last_activated"] - orig["last_activated"]).total_seconds()
            ) < 0.001

    def test_empty_graph_round_trip(self):
        """빈 그래프의 직렬화/역직렬화"""
        g = TaxonomyGraph()
        json_data = g.to_json()
        restored = TaxonomyGraph.from_json(json_data)
        assert len(restored) == 0

    def test_serialized_format(self):
        """직렬화된 데이터 형식 확인"""
        g = TaxonomyGraph()
        g.add_category("test", [1.0, 0.0])

        data = g.to_json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1

        node = data["nodes"][0]
        # datetime은 ISO 문자열로 변환되어야 함
        assert isinstance(node["last_activated"], str)
        assert isinstance(node["created_at"], str)
