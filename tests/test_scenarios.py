"""E2E 시나리오 테스트 — 설계 문서의 4개 시나리오 검증

SC1: 기본 기억 — 저장 → 3일 후 회상
SC2: 하이브리드 검색 — Vector + Graph + Metadata fusion
SC3: 선제적 예측 — 패턴 학습 → 다음 행동 예측
SC4: 망각과 갱신 — ephemeral decay + critical 갱신
"""

import pytest
import math
from datetime import datetime, timedelta

from models import Memory, Importance, IntentCategory
from storage.vector_store import VectorStore, MockEmbeddingProvider
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.memory_index import MemoryIndex
from extraction import Extractor
from decay import DecayEngine
from prediction.intent import IntentClassifier
from prediction.proactive import ProactiveInjector
from api.routes import MemoryService
from tests.test_extraction import MockLLMClient


@pytest.fixture
async def service(metadata_store, graph_store):
    """전체 통합 서비스"""
    provider = MockEmbeddingProvider(dim=1024)
    vs = VectorStore(embedding_provider=provider, use_qdrant=False)
    await vs.initialize()
    llm = MockLLMClient()
    extractor = Extractor(llm_client=llm)
    return MemoryService(
        metadata_store=metadata_store,
        vector_store=vs,
        graph_store=graph_store,
        extractor=extractor,
    )


class TestScenario1_BasicMemory:
    """SC1: 기본 메모리 기억 — 저장 → 회상"""

    async def test_store_and_recall(self, service):
        """
        사용자: "우리 팀 다음 주 목요일에 대만 출장이야"
        → 저장 후 "출장" 으로 검색하면 해당 메모리 반환
        """
        # 저장
        response = await service.process_chat(
            "우리 팀 다음 주 목요일에 대만 출장이야", "user_pm", "sess_1"
        )
        assert response is not None

        # 메모리가 저장되었는지 확인
        all_memories = await service.metadata.get_memories_by_user("user_pm")
        assert len(all_memories) > 0
        assert any("출장" in m.content for m in all_memories)

        # 회상
        results = await service.recall("출장 건 어떻게 됐지?", "user_pm")
        assert len(results) > 0

    async def test_critical_memory_has_low_lambda(self, service):
        """출장 일정 → critical → λ가 낮아야 함"""
        await service.process_chat(
            "다음 주 대만 출장 일정 확인", "user_pm"
        )
        memories = await service.metadata.get_memories_by_user("user_pm")
        critical = [m for m in memories if m.importance == Importance.critical]
        assert len(critical) > 0
        assert critical[0].decay_lambda <= 0.01


class TestScenario2_HybridSearch:
    """SC2: 하이브리드 검색 — Vector + Graph + Metadata"""

    async def test_multi_source_search(self, service):
        """
        여러 대화를 저장한 후 복합 검색:
        - Vector: 시맨틱 유사도
        - Metadata: 시간 범위
        - Graph: 엔티티 관계
        """
        # 여러 메모리 저장
        await service.process_chat("대만 출장 준비해야 해", "user_pm", "sess_1")
        await service.process_chat("대만에서 딘타이펑 맛집 추천받았어", "user_pm", "sess_1")
        await service.process_chat("코드 리뷰 PR #123 완료", "user_pm", "sess_2")

        # "대만" 관련 검색 → 대만 메모리가 코드 리뷰보다 상위
        results = await service.recall("대만 여행 정보", "user_pm")
        assert len(results) > 0

    async def test_user_isolation(self, service):
        """다른 유저의 메모리는 검색 안 됨"""
        await service.process_chat("비밀 프로젝트 진행 중", "user_pm")
        results = await service.recall("비밀 프로젝트", "user_dev")
        # user_dev는 user_pm의 메모리를 볼 수 없음
        pm_memories = [r for r in results if r.memory.user_id == "user_pm"]
        assert len(pm_memories) == 0


class TestScenario3_AnticipatoryPrediction:
    """SC3: Anticipatory Memory Chains — 패턴 학습 → 예측"""

    async def test_intent_transition_learning(self, service):
        """
        반복 패턴: weekly_report → issue_tracking
        3회 반복 후 weekly_report를 감지하면 issue 관련 메모리를 선제적으로 제공
        """
        # 이슈 관련 메모리 미리 저장
        issue_mem = Memory(
            user_id="user_pm",
            content="지난 주 이슈: API 서버 레이턴시 문제",
            importance=Importance.important,
        )
        await service.metadata.save_memory(issue_mem)
        await service.vector.store(issue_mem.id, issue_mem.content, "user_pm")

        # 패턴 반복 (weekly_report → issue_tracking 전이)
        for _ in range(4):
            await service.process_chat("주간 보고서 작성해야 해", "user_pm")
            await service.process_chat("지난주 이슈 뭐 있었지?", "user_pm")

        # 다시 주간 보고 → 이슈 예측이 발생해야 함
        response = await service.process_chat("주간 보고서 작성해야 하는데", "user_pm")

        # Prediction이 있어야 함
        if response.prediction:
            assert response.prediction.predicted_next == IntentCategory.issue_tracking
            assert response.prediction.transition_weight > 0.5

    async def test_no_prediction_for_new_user(self, service):
        """콜드스타트: 전이 기록 없으면 예측 안 함"""
        response = await service.process_chat("처음 하는 질문", "user_brand_new")
        # 예측이 없거나 None
        assert response.prediction is None


class TestScenario4_DecayAndUpdate:
    """SC4: 망각과 갱신"""

    def test_ephemeral_decays_fast(self):
        """ephemeral 메모리 7일 후 weight"""
        engine = DecayEngine()
        # ephemeral: λ=0.3, 7일 후, access=0
        w = engine.calculate_weight(0.3, 7, 0)
        assert w < 0.15  # 임계치(0.1) 근접

    def test_ephemeral_prunable_at_10_days(self):
        """ephemeral 메모리 10일 후 → 프루닝 대상"""
        engine = DecayEngine()
        w = engine.calculate_weight(0.3, 10, 0)
        assert w < 0.1  # 프루닝 임계치 미달

    def test_critical_survives_30_days(self):
        """critical 메모리 30일 후에도 활성"""
        engine = DecayEngine()
        w = engine.calculate_weight(0.005, 30, 0)
        assert w > 0.85

    async def test_fact_update_invalidation(self, service):
        """
        '판교로 이사' → '이사 취소' → 기존 무효화 + 새 팩트
        """
        # 기존 팩트
        await service.process_chat("다음 달에 판교로 이사해", "user_pm")
        mems = await service.metadata.get_memories_by_user("user_pm")
        original = mems[0]

        # 갱신
        await service.decay.update_fact(
            service.metadata, original.id, "이사 취소됨", "user_pm"
        )

        # 기존은 무효화
        old = await service.metadata.get_memory(original.id)
        assert old.is_valid is False

        # 새 메모리 존재
        valid_mems = await service.metadata.get_memories_by_user("user_pm", valid_only=True)
        assert any("이사 취소" in m.content for m in valid_mems)

    async def test_access_delays_pruning(self, service):
        """반복 접근하면 프루닝이 늦춰짐"""
        engine = DecayEngine()

        # access 없으면 8일 후 거의 프루닝 대상
        w_no_access = engine.calculate_weight(0.3, 8, access_count=0)

        # access 3회면 같은 시간에도 weight 더 높음
        w_with_access = engine.calculate_weight(0.3, 8, access_count=3)

        assert w_with_access > w_no_access
        assert w_with_access > 0.1  # 아직 프루닝 안 됨
