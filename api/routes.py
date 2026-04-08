"""전체 API 엔드포인트 — 통합 모듈

POST /chat       - 메인 대화 (메모리 검색 + 응답 + 비동기 추출)
GET  /recall     - 메모리 검색
GET  /memory/{id} - 메모리 상세
DELETE /memory/{id} - 메모리 삭제
GET  /debug/memories - 전체 메모리 상태
GET  /debug/graph    - 그래프 상태

v2: TaxonomyEvolver 통합
  - use_taxonomy=True 시 v2 동적 분류 활성화
  - Bootstrap phase → Evolution phase 자동 전환
  - v1 IntentClassifier는 prediction용으로 유지
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from models import (
    ChatRequest, ChatResponse, RecallRequest,
    Memory, SearchResult, IntentPrediction,
)
from storage.metadata_store import MetadataStore
from storage.vector_store import VectorStore
from storage.graph_store import GraphStore
from storage.memory_index import MemoryIndex
from extraction import Extractor
from decay import DecayEngine
from prediction.intent import IntentClassifier
from prediction.proactive import ProactiveInjector


router = APIRouter()


class MemoryService:
    """API에서 사용하는 통합 서비스 — 모든 레이어 조율

    v2: use_taxonomy=True 시 TaxonomyEvolver 기반 동적 분류 활성화.
    Bootstrap(30턴) → Evolution(이후) 자동 전환.
    """

    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        graph_store: GraphStore,
        extractor: Extractor,
        use_taxonomy: bool = False,
        llm_client=None,
        embedding_provider=None,
    ):
        self.metadata = metadata_store
        self.vector = vector_store
        self.graph = graph_store
        self.index = MemoryIndex(vector_store, metadata_store, graph_store)
        self.extractor = extractor
        self.decay = DecayEngine()
        self.intent_classifier = IntentClassifier()
        self.injector = ProactiveInjector(graph_store, metadata_store)
        self._last_intent: dict[str, str] = {}  # user_id → last intent

        # --- v2: Taxonomy Evolution ---
        self._use_taxonomy = use_taxonomy
        self._llm = llm_client
        self._embedding_provider = embedding_provider
        self._bootstrap = None  # TaxonomyBootstrap (bootstrap phase)
        self._evolver = None    # TaxonomyEvolver (evolution phase)
        self._lineage = None    # PhylogeneticLineage
        self._ephemeral_patterns = None
        self._taxonomy_turn_count = 0
        self._last_v2_category: dict[str, str] = {}  # user_id → last v2 category

        if use_taxonomy and llm_client:
            from taxonomy.bootstrap import TaxonomyBootstrap
            self._bootstrap = TaxonomyBootstrap(llm_client)

    @property
    def taxonomy_ready(self) -> bool:
        """Bootstrap 완료 후 evolver가 활성화되었는지 확인"""
        return self._evolver is not None

    @property
    def evolver(self):
        return self._evolver

    def load_taxonomy_state(self, taxonomy, lineage, ephemeral_patterns, turn_count=0):
        """저장된 taxonomy 상태를 복원하여 bootstrap 건너뛰기"""
        from taxonomy.evolver import TaxonomyEvolver
        self._evolver = TaxonomyEvolver(
            taxonomy, lineage, self._llm, self._embedding_provider,
        )
        self._lineage = lineage
        self._ephemeral_patterns = ephemeral_patterns
        self._taxonomy_turn_count = turn_count
        self._bootstrap = None  # bootstrap 완료 상태

    async def process_chat(
        self, message: str, user_id: str, session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        메인 대화 파이프라인:
          1. Intent 분류 (v1 rule-based 또는 v2 taxonomy)
          2. 메모리 검색 (RRF fusion)
          3. 선제적 예측
          4. 비동기 추출 (백그라운드)
          5. (v2) Taxonomy evolution: bootstrap → classify → sweep
        """
        # --- 1. Intent 분류 ---
        intent = self.intent_classifier.classify(message)

        # v2: Taxonomy 기반 분류 (v1과 병행)
        v2_category = None
        if self._use_taxonomy:
            v2_category = await self._taxonomy_classify(message)
            self._last_v2_category[user_id] = v2_category

        # Intent 전이 기록 (v1 기반 — prediction은 v1 intent graph 사용)
        last = self._last_intent.get(user_id)
        if last:
            self.graph.record_intent_transition(last, intent.value)
        self._last_intent[user_id] = intent.value

        # --- 2. 메모리 검색 ---
        search_results = await self.index.search(message, user_id)

        # 접근한 메모리 access_count 갱신
        for sr in search_results:
            await self.metadata.update_access(sr.memory.id)

        # --- 3. 선제적 예측 ---
        prediction = await self.injector.predict_and_fetch(intent, user_id)

        # --- 4. 비동기 추출 (여기서는 동기로 처리, 실제 운영에선 asyncio.create_task) ---
        extraction = await self.extractor.extract(message, user_id, session_id)

        # 추출된 fact를 메모리로 저장
        for fact in extraction.facts:
            # dedup 확인
            existing_id = await self.vector.find_similar(fact.content, user_id, threshold=0.9)
            if existing_id:
                await self.metadata.update_access(existing_id)
                continue

            # 새 메모리 생성
            memory = Memory(
                user_id=user_id,
                content=fact.content,
                facts=[fact],
                importance=fact.importance,
                decay_lambda=self.decay.get_lambda_for_importance(fact.importance),
                session_id=session_id,
            )
            embedding = await self.vector.store(memory.id, memory.content, user_id)
            memory.embedding = embedding
            await self.metadata.save_memory(memory)

            # 엔티티/관계를 그래프에 추가
            for entity in fact.entities:
                self.graph.add_entity(entity.name, entity_type=entity.entity_type, memory_id=memory.id)
            for rel in fact.relations:
                self.graph.add_relation(rel.source, rel.target, rel.relation_type)

        # 응답 생성 (실제로는 LLM 호출, 여기서는 메모리 기반 간이 응답)
        response_text = self._build_response(message, search_results, prediction)

        return ChatResponse(
            response=response_text,
            memories_used=search_results,
            prediction=prediction,
        )

    # --- v2: Taxonomy 분류 ---

    async def _taxonomy_classify(self, message: str) -> Optional[str]:
        """v2 taxonomy 기반 분류: bootstrap → evolution 자동 전환"""
        if not self._embedding_provider:
            return None

        embedding = await self._embedding_provider.embed(message)

        # Phase 1: Bootstrap (첫 30턴)
        if self._bootstrap and not self._bootstrap.is_executed:
            self._bootstrap.add_message(message, embedding)
            if self._bootstrap.is_ready():
                taxonomy, lineage, patterns = await self._bootstrap.execute()
                from taxonomy.evolver import TaxonomyEvolver
                self._evolver = TaxonomyEvolver(
                    taxonomy, lineage, self._llm, self._embedding_provider,
                )
                self._lineage = lineage
                self._ephemeral_patterns = patterns
                # bootstrap 완료 시점의 분류
                best = taxonomy.get_best_match(embedding)
                return best or "unknown"
            return "buffering"

        # Phase 2: Evolution
        if self._evolver:
            category, is_new = await self._evolver.classify_or_propose(message, embedding)

            # 멤버 등록
            mem_id = f"tax_{self._taxonomy_turn_count}"
            await self._evolver.register_memory(category, mem_id, embedding)
            self._taxonomy_turn_count += 1

            # Decay sweep 체크
            if self._evolver.should_sweep():
                await self._evolver.decay_sweep(datetime.now())

            return category

        return None

    async def recall(
        self, query: str, user_id: str, top_k: int = 5,
        time_start: Optional[datetime] = None, time_end: Optional[datetime] = None,
    ) -> list[SearchResult]:
        """메모리 검색"""
        return await self.index.search(query, user_id, top_k, time_start, time_end)

    def _build_response(
        self, message: str, memories: list[SearchResult],
        prediction: Optional[IntentPrediction],
    ) -> str:
        """메모리 기반 간이 응답 생성 (실제로는 LLM 호출)"""
        parts = []
        if memories:
            parts.append("관련 기억:")
            for sr in memories[:3]:
                parts.append(f"  - {sr.memory.content}")
        if prediction and prediction.predicted_memories:
            parts.append(f"\n[예측된 컨텍스트] ({prediction.predicted_next.value}, "
                         f"{prediction.transition_weight:.0%}):")
            for mem in prediction.predicted_memories[:3]:
                parts.append(f"  - {mem.content}")
        if not parts:
            parts.append(f"메시지를 받았습니다: {message}")
        return "\n".join(parts)
