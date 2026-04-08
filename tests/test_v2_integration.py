"""v2 통합 테스트 — MemoryService v2 통합, Persistence, JSON 파싱

INT1: MemoryService(use_taxonomy=False)은 v1 동작 유지
INT2: MemoryService(use_taxonomy=True) bootstrap phase (buffering)
INT3: MemoryService(use_taxonomy=True) bootstrap 완료 → evolution phase
INT4: load_taxonomy_state로 기존 상태 복원
INT5: Persistence save/load round-trip
INT6: Persistence exists/delete
INT7: _extract_json_array — 정상 JSON
INT8: _extract_json_array — 설명 텍스트 포함 JSON 추출
INT9: _extract_json_array — prefix continuation 모드
INT10: _extract_json_array — 파싱 불가 시 None
INT11: Semantic mapping 정확도 계산
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from taxonomy.bootstrap import _extract_json_array, TaxonomyBootstrap, BUFFER_SIZE
from taxonomy.taxonomy_graph import TaxonomyGraph
from taxonomy.lineage import PhylogeneticLineage
from taxonomy.persistence import TaxonomyPersistence


# --- 헬퍼 ---

def _unit_vec(dim: int = 128, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return (v / np.linalg.norm(v)).tolist()


def _make_taxonomy_with_categories() -> tuple[TaxonomyGraph, PhylogeneticLineage]:
    """테스트용 taxonomy + lineage 생성"""
    taxonomy = TaxonomyGraph()
    lineage = PhylogeneticLineage()

    for i, name in enumerate(["scheduling", "code_review", "data_analysis"]):
        centroid = _unit_vec(128, seed=i * 10)
        taxonomy.add_category(name, centroid, created_by="bootstrap")
        lineage.record_bootstrap(name, member_count=5)

    return taxonomy, lineage


def _make_mock_llm():
    """Mock LLM client"""
    llm = MagicMock()
    llm._model = "test-model"
    llm._client = MagicMock()
    return llm


def _make_mock_embedding():
    """Mock embedding provider"""
    provider = MagicMock()

    async def mock_embed(text):
        return _unit_vec(128, seed=hash(text) % 1000)

    provider.embed = mock_embed
    return provider


# =============================================================
# INT7~10: _extract_json_array 테스트
# =============================================================


class TestExtractJsonArray:
    """_extract_json_array 함수 테스트"""

    def test_normal_json(self):
        """INT7: 정상 JSON 배열 파싱"""
        raw = '["hello", "world", "test"]'
        result = _extract_json_array(raw)
        assert result == ["hello", "world", "test"]

    def test_json_with_surrounding_text(self):
        """INT8: 설명 텍스트가 포함된 경우 JSON 배열 추출"""
        raw = '여기 패턴입니다:\n["ㅋㅋ", "ㅎㅎ", "넵"]\n이상입니다.'
        result = _extract_json_array(raw)
        assert result == ["ㅋㅋ", "ㅎㅎ", "넵"]

    def test_prefix_continuation(self):
        """INT9: prefix items + LLM continuation 합치기"""
        prefix = ["a", "b", "c"]
        # LLM이 prefix 이후 continuation만 출력한 경우
        raw = '"d", "e", "f"]'
        result = _extract_json_array(raw, prefix_items=prefix)
        assert result is not None
        assert "a" in result
        assert "f" in result
        assert len(result) == 6

    def test_unparseable_returns_none(self):
        """INT10: 파싱 불가 시 None 반환"""
        raw = "이것은 JSON이 아닙니다 전혀"
        result = _extract_json_array(raw)
        assert result is None

    def test_empty_returns_none(self):
        result = _extract_json_array("")
        assert result is None

    def test_none_returns_none(self):
        result = _extract_json_array(None)
        assert result is None


# =============================================================
# INT5~6: Persistence 테스트
# =============================================================


class TestPersistence:
    """TaxonomyPersistence 테스트"""

    def test_save_load_roundtrip(self):
        """INT5: save → load round-trip"""
        taxonomy, lineage = _make_taxonomy_with_categories()
        patterns = ["ㅋㅋ", "ㅎㅎ", "넵"]

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = TaxonomyPersistence(base_dir=tmpdir)
            persistence.save(taxonomy, lineage, patterns, turn_count=42)

            loaded_tax, loaded_lin, loaded_pat, loaded_tc = persistence.load()

            # 카테고리 복원 검증
            assert len(loaded_tax) == 3
            assert "scheduling" in loaded_tax
            assert "code_review" in loaded_tax
            assert "data_analysis" in loaded_tax

            # Lineage 복원 검증
            summary = loaded_lin.get_summary()
            assert summary["total_events"] == 3

            # 메타 검증
            assert loaded_pat == patterns
            assert loaded_tc == 42

    def test_exists_and_delete(self):
        """INT6: exists/delete 동작"""
        taxonomy, lineage = _make_taxonomy_with_categories()

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = TaxonomyPersistence(base_dir=tmpdir)
            assert not persistence.exists()

            persistence.save(taxonomy, lineage)
            assert persistence.exists()

            persistence.delete()
            assert not persistence.exists()

    def test_load_nonexistent_raises(self):
        """존재하지 않는 파일 로드 시 FileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = TaxonomyPersistence(base_dir=tmpdir)
            with pytest.raises(FileNotFoundError):
                persistence.load()


# =============================================================
# INT1~4: MemoryService v2 통합 테스트
# =============================================================


class TestMemoryServiceV2:
    """MemoryService v2 통합 테스트"""

    @pytest.fixture
    def stores(self):
        """Mock stores 생성"""
        metadata = AsyncMock()
        metadata.get_memories_by_user = AsyncMock(return_value=[])
        metadata.save_memory = AsyncMock()
        metadata.update_access = AsyncMock()

        vector = AsyncMock()
        vector.store = AsyncMock(return_value=_unit_vec(128))
        vector.find_similar = AsyncMock(return_value=None)

        graph = MagicMock()
        graph.intent_graph = MagicMock()
        graph.record_intent_transition = MagicMock()
        graph.get_next_intent = MagicMock(return_value=None)
        graph.get_neighbors = MagicMock(return_value=[])

        extractor = AsyncMock()
        extractor.extract = AsyncMock()
        extract_result = MagicMock()
        extract_result.facts = []
        extractor.extract.return_value = extract_result

        return metadata, vector, graph, extractor

    @pytest.mark.asyncio
    async def test_v1_mode_unchanged(self, stores):
        """INT1: use_taxonomy=False는 v1 동작 유지"""
        from api.routes import MemoryService

        metadata, vector, graph, extractor = stores

        # MemoryIndex mock
        with patch("api.routes.MemoryIndex") as MockIndex:
            mock_index = AsyncMock()
            mock_index.search = AsyncMock(return_value=[])
            MockIndex.return_value = mock_index

            svc = MemoryService(metadata, vector, graph, extractor, use_taxonomy=False)
            assert not svc._use_taxonomy
            assert svc._bootstrap is None
            assert svc._evolver is None

            result = await svc.process_chat("주간 보고서 작성", "user1")
            assert result.response is not None

    @pytest.mark.asyncio
    async def test_v2_bootstrap_phase(self, stores):
        """INT2: use_taxonomy=True bootstrap phase → buffering 반환"""
        from api.routes import MemoryService

        metadata, vector, graph, extractor = stores
        llm = _make_mock_llm()
        embedding = _make_mock_embedding()

        with patch("api.routes.MemoryIndex") as MockIndex:
            mock_index = AsyncMock()
            mock_index.search = AsyncMock(return_value=[])
            MockIndex.return_value = mock_index

            svc = MemoryService(
                metadata, vector, graph, extractor,
                use_taxonomy=True, llm_client=llm, embedding_provider=embedding,
            )
            assert svc._bootstrap is not None
            assert not svc.taxonomy_ready

            # 첫 번째 메시지: buffering 상태
            result = await svc.process_chat("안녕하세요", "user1")
            assert result.response is not None
            assert svc._bootstrap.buffer_size == 1

    @pytest.mark.asyncio
    async def test_load_taxonomy_state(self, stores):
        """INT4: 기존 taxonomy 상태 복원"""
        from api.routes import MemoryService

        metadata, vector, graph, extractor = stores
        llm = _make_mock_llm()
        embedding = _make_mock_embedding()

        with patch("api.routes.MemoryIndex") as MockIndex:
            mock_index = AsyncMock()
            mock_index.search = AsyncMock(return_value=[])
            MockIndex.return_value = mock_index

            svc = MemoryService(
                metadata, vector, graph, extractor,
                use_taxonomy=True, llm_client=llm, embedding_provider=embedding,
            )

            # 저장된 상태 복원
            taxonomy, lineage = _make_taxonomy_with_categories()
            svc.load_taxonomy_state(taxonomy, lineage, ["ㅋㅋ", "ㅎㅎ"], turn_count=50)

            assert svc.taxonomy_ready
            assert svc._bootstrap is None  # bootstrap 건너뜀
            assert svc._taxonomy_turn_count == 50


# =============================================================
# INT11: Semantic Mapping 테스트
# =============================================================


class TestSemanticMapping:
    """analyze_results_v2의 semantic mapping 테스트"""

    def test_exact_match(self):
        from analyze_results_v2 import _semantic_match
        assert _semantic_match("data_analysis", "data_analysis")

    def test_semantic_match(self):
        from analyze_results_v2 import _semantic_match
        assert _semantic_match("scheduling", "schedule_management")
        assert _semantic_match("scheduling", "team_meeting_prep")
        assert _semantic_match("issue_tracking", "bug_resolution")
        assert _semantic_match("knowledge_lookup", "technical_discussion")

    def test_no_match(self):
        from analyze_results_v2 import _semantic_match
        assert not _semantic_match("scheduling", "data_analysis")
        assert not _semantic_match("code_review", "data_analysis")

    def test_unknown_ground_truth(self):
        from analyze_results_v2 import _semantic_match
        # 매핑에 없는 ground truth는 exact match만
        assert not _semantic_match("unknown_category", "something_else")
        assert _semantic_match("unknown_category", "unknown_category")
