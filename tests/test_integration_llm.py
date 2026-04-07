"""실제 LLM 연동 통합 테스트 — DooGPU Gemma 31B

Mock이 아닌 실제 LLM으로 전체 파이프라인 검증.
pytest -m integration 으로 실행 (일반 테스트와 분리)
"""

import pytest
from datetime import datetime

from models import Importance, IntentCategory
from extraction import Extractor
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.vector_store import VectorStore, MockEmbeddingProvider
from api.routes import MemoryService
from llm_client import DooGPULLMClient

DOOGPU_BASE = "https://doogpu.doosan.com/standard/workspace/ws-94c8469a-43a7-4573-a455-2926fa446865/workload/wl-9ffd545a-87ed-47ce-92d4-8171856ca014/reserved3/v1"
DOOGPU_MODEL = "google/gemma-4-31B-it"


@pytest.fixture
def real_llm():
    return DooGPULLMClient(base_url=DOOGPU_BASE, model=DOOGPU_MODEL, api_key="EMPTY")


@pytest.fixture
async def real_service(metadata_store, graph_store, real_llm):
    """실제 LLM + Mock Embedding 서비스"""
    provider = MockEmbeddingProvider(dim=1024)
    vs = VectorStore(embedding_provider=provider, use_qdrant=False)
    await vs.initialize()
    extractor = Extractor(llm_client=real_llm)
    return MemoryService(
        metadata_store=metadata_store,
        vector_store=vs,
        graph_store=graph_store,
        extractor=extractor,
    )


@pytest.mark.integration
class TestRealLLMExtraction:
    """실제 LLM으로 fact 추출 검증"""

    async def test_schedule_extraction(self, real_llm):
        """일정 정보가 critical로 추출되는지"""
        extractor = Extractor(llm_client=real_llm)
        result = await extractor.extract(
            "다음 주 수요일에 판교 오피스에서 디자인 리뷰 회의가 있어", "user_pm"
        )
        assert len(result.facts) > 0
        # 일정 → critical
        has_critical = any(f.importance == Importance.critical for f in result.facts)
        print(f"\n  추출된 facts: {[(f.content, f.importance.value) for f in result.facts]}")
        assert has_critical, "일정 정보는 critical이어야 함"

    async def test_ephemeral_detection(self, real_llm):
        """짧은 일상 대화가 ephemeral로 분류되는지"""
        extractor = Extractor(llm_client=real_llm)
        result = await extractor.extract("ㅋㅋ 오키", "user_new")
        print(f"\n  추출된 facts: {[(f.content, f.importance.value) for f in result.facts]}")
        has_ephemeral = any(f.importance == Importance.ephemeral for f in result.facts)
        assert has_ephemeral, "일상 대화는 ephemeral이어야 함"

    async def test_entity_extraction(self, real_llm):
        """엔티티(사람, 장소)가 추출되는지"""
        extractor = Extractor(llm_client=real_llm)
        result = await extractor.extract(
            "김팀장이 A프로젝트 결제 모듈을 담당하고 있어", "user_pm"
        )
        all_entities = []
        for f in result.facts:
            all_entities.extend(f.entities)
        entity_names = [e.name for e in all_entities]
        print(f"\n  추출된 entities: {entity_names}")
        assert len(entity_names) > 0, "최소 1개 엔티티 추출되어야 함"


@pytest.mark.integration
class TestRealLLME2E:
    """실제 LLM으로 E2E 시나리오"""

    async def test_full_chat_pipeline(self, real_service):
        """전체 파이프라인: 대화 → 추출 → 저장 → 검색"""
        svc = real_service

        # 1. 메모리 저장
        r1 = await svc.process_chat("우리 팀 다음 주에 대만 출장 가야 해", "user_pm")
        print(f"\n  응답1: {r1.response[:100]}")

        r2 = await svc.process_chat("김팀장이 결제 모듈 버그 수정 담당이야", "user_pm")
        print(f"  응답2: {r2.response[:100]}")

        # 2. 메모리 확인
        memories = await svc.metadata.get_memories_by_user("user_pm")
        print(f"  저장된 메모리: {len(memories)}개")
        for m in memories:
            print(f"    - [{m.importance.value}] {m.content[:50]}")
        assert len(memories) >= 2

        # 3. 검색
        results = await svc.recall("출장 일정", "user_pm")
        print(f"  '출장 일정' 검색 결과: {len(results)}개")
        assert len(results) > 0

    async def test_intent_transition_with_real_llm(self, real_service):
        """실제 LLM으로 intent 전이 패턴 학습"""
        svc = real_service

        # 주간보고 → 이슈 패턴 반복
        for i in range(3):
            await svc.process_chat("주간 보고서 작성해야 해", "user_pm")
            await svc.process_chat("지난주 이슈 정리해줘", "user_pm")

        # transition graph 확인
        weight = svc.graph.get_transition_weight("weekly_report", "issue_tracking")
        print(f"\n  weekly_report → issue_tracking weight: {weight:.2f}")
        assert weight > 0, "전이 기록이 있어야 함"
