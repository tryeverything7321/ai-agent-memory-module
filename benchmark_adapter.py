"""MemoryAgentBench Adapter — 우리 메모리 모듈을 벤치마크에 연결

MemoryAgentBench의 AgentWrapper 인터페이스를 구현하여
FactConsolidation (Selective Forgetting) 태스크에서 평가.

두 가지 모드:
  - Baseline: 단순 메모리 저장 + 검색 (graph propagation OFF)
  - Experiment: graph-aware selective forgetting (propagation ON)
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 프로젝트 임포트
from models import Memory, Importance, Entity, Relation, Fact
from decay import DecayEngine
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.vector_store import VectorStore
from storage.memory_index import MemoryIndex
from config import settings


class DooGPULLMClient:
    """DooGPU 클러스터의 Gemma 31B를 호출하는 간단한 LLM 클라이언트"""

    def __init__(self, base_url: str = None, model: str = None):
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._model = model or settings.llm_model
        self._timeout = 120

    async def generate(self, prompt: str, max_tokens: int = 10, temperature: float = 0.0) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url, json=payload,
                headers={"Authorization": f"Bearer EMPTY"},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    async def extract_entities_and_facts(self, text: str) -> dict:
        """텍스트에서 entity, relation, fact 추출 (LLM 기반)"""
        prompt = f"""Extract entities and facts from the following text.
Return JSON format:
{{"facts": [{{"content": "...", "importance": "critical"}}],
 "entities": [{{"name": "...", "entity_type": "..."}}],
 "relations": [{{"source": "...", "target": "...", "relation_type": "..."}}]}}

Text: {text}

JSON:"""
        try:
            result = await self.generate(prompt, max_tokens=500, temperature=0.0)
            import json
            # JSON 부분 추출
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
        return {"facts": [{"content": text, "importance": "important"}], "entities": [], "relations": []}


class MemoryModuleAdapter:
    """MemoryAgentBench 호환 어댑터

    AgentWrapper의 send_message 인터페이스를 구현.
    graph_propagation=True/False로 Baseline vs Experiment 전환.
    """

    def __init__(
        self,
        graph_propagation: bool = True,
        semantic_filter: bool = True,
        attribute_aware: bool = True,
        propagation_depth: int = 2,
        decay_per_hop: float = 0.5,
        llm_client: DooGPULLMClient = None,
        embedding_provider=None,
        db_path: str = ":memory:",
    ):
        self.graph_propagation = graph_propagation
        self.semantic_filter = semantic_filter
        self.attribute_aware = attribute_aware
        self.propagation_depth = propagation_depth
        self.decay_per_hop = decay_per_hop

        # 내부 컴포넌트
        self._llm = llm_client or DooGPULLMClient()
        self._embedding_provider = embedding_provider
        self._db_path = db_path

        # lazy init (async)
        self._initialized = False
        self._metadata_store: Optional[MetadataStore] = None
        self._graph_store: Optional[GraphStore] = None
        self._vector_store: Optional[VectorStore] = None
        self._memory_index: Optional[MemoryIndex] = None
        self._decay_engine = DecayEngine()

        # fact 충돌 감지용 — serial number → memory_id 매핑
        self._fact_registry: dict[str, str] = {}  # "entity:attribute" → memory_id
        self._serial_registry: dict[int, str] = {}  # serial_number → memory_id

        # 성능 측정
        self._memory_construction_start: float = 0
        self._total_memorize_time: float = 0

    async def _ensure_initialized(self):
        if self._initialized:
            return

        self._metadata_store = MetadataStore(self._db_path)
        await self._metadata_store.initialize()

        self._graph_store = GraphStore(self._metadata_store)

        if self._embedding_provider:
            self._vector_store = VectorStore(
                embedding_provider=self._embedding_provider,
                use_qdrant=False,
            )
        else:
            from storage.vector_store import DooGPUEmbeddingProvider
            self._vector_store = VectorStore(
                embedding_provider=DooGPUEmbeddingProvider(),
                use_qdrant=False,
            )
        await self._vector_store.initialize()

        self._memory_index = MemoryIndex(
            self._vector_store, self._metadata_store, self._graph_store
        )
        self._memory_construction_start = time.time()
        self._initialized = True

    def send_message(self, message: str, memorizing: bool = False,
                     query_id: int = None, context_id: int = None) -> dict | str:
        """MemoryAgentBench 호환 인터페이스 (동기)"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 이미 async 컨텍스트 안이면 nest_asyncio 또는 직접 await 불가
            # → 새 스레드에서 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    self._async_send_message(message, memorizing, query_id, context_id)
                ).result()
        return asyncio.get_event_loop().run_until_complete(
            self._async_send_message(message, memorizing, query_id, context_id)
        )

    async def async_send_message(self, message: str, memorizing: bool = False,
                                  query_id: int = None, context_id: int = None) -> dict | str:
        """async 컨텍스트에서 직접 호출용"""
        return await self._async_send_message(message, memorizing, query_id, context_id)

    async def _async_send_message(self, message: str, memorizing: bool,
                                   query_id: int, context_id: int) -> dict | str:
        await self._ensure_initialized()

        if memorizing:
            return await self._memorize(message)
        else:
            return await self._query(message, query_id, context_id)

    async def _memorize(self, message: str) -> str:
        """청크를 메모리에 저장 — entity 추출 + 충돌 감지 + graph 구축"""
        start = time.time()

        # --- serial number 추출 + fact 파싱 ---
        facts = self._parse_numbered_facts(message)

        for serial_num, fact_text in facts:
            # 1. 메모리 생성 및 저장
            mem = Memory(
                user_id="benchmark",
                content=fact_text,
                importance=Importance.critical,
                decay_lambda=settings.decay_lambda_critical,
            )
            await self._metadata_store.save_memory(mem)
            await self._vector_store.store(mem.id, fact_text, "benchmark")

            # 2. 간단한 entity 추출 (규칙 기반 — LLM 호출 절약)
            entities = self._extract_entities_rule_based(fact_text)
            for entity_name, entity_type in entities:
                self._graph_store.add_entity(
                    entity_name, entity_type=entity_type, memory_id=mem.id
                )

            # 3. entity 간 relation 추가 (co-occurrence 기반)
            entity_names = [e[0] for e in entities]
            for i in range(len(entity_names)):
                for j in range(i + 1, len(entity_names)):
                    self._graph_store.add_relation(
                        entity_names[i], entity_names[j], "co_occurs"
                    )

            # 4. 충돌 감지 — 동일 subject entity에 대한 이전 fact 무효화
            subject_key = self._get_subject_key(fact_text, entities)
            if subject_key and subject_key in self._fact_registry:
                old_memory_id = self._fact_registry[subject_key]
                if old_memory_id != mem.id:
                    # 이전 fact 무효화 (새 메모리는 이미 위에서 생성됨)
                    await self._metadata_store.invalidate_memory(old_memory_id)
                    # graph propagation
                    if self.graph_propagation:
                        await self._decay_engine.propagate_invalidation(
                            invalidated_memory_id=old_memory_id,
                            graph_store=self._graph_store,
                            metadata_store=self._metadata_store,
                            propagation_depth=self.propagation_depth,
                            decay_per_hop=self.decay_per_hop,
                            semantic_filter=self.semantic_filter,
                            new_content=fact_text,
                            # attribute_aware=False → BFS 경로 사용
                            subject_key=subject_key if self.attribute_aware else None,
                            fact_registry=self._fact_registry if self.attribute_aware else None,
                        )
            if subject_key:
                self._fact_registry[subject_key] = mem.id
            if serial_num is not None:
                self._serial_registry[serial_num] = mem.id

        self._total_memorize_time += time.time() - start
        return "Memorized"

    async def _query(self, message: str, query_id: int, context_id: int) -> dict:
        """질문에 답변 — RRF search + LLM 생성"""
        memory_construction_time = self._total_memorize_time
        start = time.time()

        # 1. 하이브리드 검색
        results = await self._memory_index.search(
            query=message, user_id="benchmark", top_k=5
        )

        # 2. 검색 결과로 컨텍스트 구성
        context_parts = []
        for r in results:
            context_parts.append(r.memory.content)
        context = "\n".join(context_parts)

        # 3. LLM으로 답변 생성
        prompt = (
            "You are a knowledge management system. Each fact in the knowledge pool "
            "is provided with a serial number, and the newer fact has a larger serial number. "
            "Resolve conflicts by preferring the newest fact. "
            "Give a very concise answer without extra words.\n\n"
            f"Knowledge Pool:\n{context}\n\n"
            f"Question: {message}\n"
            f"Answer:"
        )

        try:
            answer = await self._llm.generate(prompt, max_tokens=10, temperature=0.0)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            answer = "unknown"

        query_time = time.time() - start

        return {
            "output": answer,
            "input_len": len(message),
            "output_len": len(answer),
            "memory_construction_time": memory_construction_time,
            "query_time_len": query_time,
        }

    # --- 유틸리티 ---

    def _parse_numbered_facts(self, text: str) -> list[tuple[int | None, str]]:
        """번호 매겨진 사실 파싱 (예: '1. 러시아 대통령은 푸틴이다')"""
        facts = []
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # "123. fact text" 패턴
            match = re.match(r'^(\d+)\.\s*(.+)', line)
            if match:
                serial = int(match.group(1))
                content = match.group(2).strip()
                facts.append((serial, content))
            else:
                # 번호 없는 경우 전체를 하나의 fact으로
                facts.append((None, line))

        # 번호가 하나도 없으면 전체 텍스트를 하나의 fact으로
        if not facts:
            facts.append((None, text.strip()))
        return facts

    def _extract_entities_rule_based(self, text: str) -> list[tuple[str, str]]:
        """규칙 기반 entity 추출 — FactConsolidation 데이터에 최적화

        패턴: "X is/was/are Y", "X's Y", "the Y of X" 등에서 고유명사 추출
        """
        entities = []

        # 대문자로 시작하는 단어 시퀀스 (영어 고유명사)
        proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', text)
        seen = set()
        for noun in proper_nouns:
            if noun.lower() not in {"the", "a", "an", "is", "was", "are", "were", "has", "have"}:
                if noun not in seen:
                    entities.append((noun, "entity"))
                    seen.add(noun)

        # "the X of Y" 패턴에서 X, Y 추출
        of_pattern = re.findall(r'the\s+(\w+)\s+of\s+([A-Z]\w+(?:\s+[A-Z]\w+)*)', text)
        for attr, entity in of_pattern:
            if entity not in seen:
                entities.append((entity, "entity"))
                seen.add(entity)

        return entities

    def _get_subject_key(self, text: str, entities: list[tuple[str, str]]) -> str | None:
        """fact의 subject 키 생성 — 충돌 감지용

        "The president of Russia is X" → "Russia:president"
        "X was born in Y" → "X:born_in"
        "X is the president of Y" → "Y:president"
        """
        if not entities:
            return None

        subject = entities[0][0] if entities else ""
        text_lower = text.lower()

        # "The X of Y is Z" 패턴 (FactConsolidation 데이터의 주요 형태)
        the_of_match = re.search(r'the\s+(\w+)\s+of\s+(\w[\w\s]*?)\s+(?:is|was|are|were)\s', text_lower)
        if the_of_match:
            attribute = the_of_match.group(1)
            of_entity = the_of_match.group(2).strip()
            # 대소문자 보정: entities에서 매칭되는 원본 이름 찾기
            for ename, _ in entities:
                if ename.lower() == of_entity.lower():
                    return f"{ename}:{attribute}"
            return f"{of_entity}:{attribute}"

        # "X is the Y of Z" 패턴
        is_the_match = re.search(r'is the (\w+) of', text_lower)
        if is_the_match:
            attribute = is_the_match.group(1)
            target = entities[-1][0] if len(entities) > 1 else subject
            return f"{target}:{attribute}"

        # 기타 관계 패턴
        relation_patterns = [
            (r'was born in', f"{subject}:birthplace"),
            (r'died in', f"{subject}:death_place"),
            (r'lives in', f"{subject}:residence"),
            (r'works at', f"{subject}:workplace"),
            (r'(?:is|was) married to', f"{subject}:spouse"),
            (r'is a (\w+)', f"{subject}:type"),
            (r'plays for', f"{subject}:team"),
            (r'is located in', f"{subject}:location"),
            (r'was founded', f"{subject}:founded"),
            (r'is the capital of', f"{subject}:capital_of"),
        ]

        for pattern, key in relation_patterns:
            if re.search(pattern, text_lower):
                return key

        # fallback: first entity + normalized text hash (동일 구조의 문장은 같은 해시)
        # "The X of Y is Z" 에서 Z를 제거하여 구조만 비교
        structure = re.sub(r'\b(?:' + '|'.join(re.escape(e[0]) for e in entities) + r')\b', '_E_', text)
        return f"{subject}:{hash(structure) % 100000}"

    async def reset(self):
        """벤치마크 context 전환 시 상태 초기화"""
        if self._metadata_store:
            await self._metadata_store.close()
        self._initialized = False
        self._fact_registry.clear()
        self._serial_registry.clear()
        self._total_memorize_time = 0
