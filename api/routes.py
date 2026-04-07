"""전체 API 엔드포인트 — 통합 모듈

POST /chat       - 메인 대화 (메모리 검색 + 응답 + 비동기 추출)
GET  /recall     - 메모리 검색
GET  /memory/{id} - 메모리 상세
DELETE /memory/{id} - 메모리 삭제
GET  /debug/memories - 전체 메모리 상태
GET  /debug/graph    - 그래프 상태
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
    """API에서 사용하는 통합 서비스 — 모든 레이어 조율"""

    def __init__(
        self,
        metadata_store: MetadataStore,
        vector_store: VectorStore,
        graph_store: GraphStore,
        extractor: Extractor,
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

    async def process_chat(
        self, message: str, user_id: str, session_id: Optional[str] = None
    ) -> ChatResponse:
        """
        메인 대화 파이프라인:
          1. Intent 분류
          2. 메모리 검색 (RRF fusion)
          3. 선제적 예측
          4. 비동기 추출 (백그라운드)
        """
        # --- 1. Intent 분류 ---
        intent = self.intent_classifier.classify(message)

        # Intent 전이 기록
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
