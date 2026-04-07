"""Extraction Layer — 대화에서 facts/entities/relations 추출 + 중요도 분류

통합 모듈: extractor + tagger + classifier
LLM 실패 시 raw text fallback → SQLite 임시 저장
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol, Optional

from models import (
    ExtractionResult, Fact, Entity, Relation, Importance
)


class LLMClient(Protocol):
    """LLM 인터페이스 — 실제 구현과 mock 모두 이 프로토콜을 따름"""
    async def extract_facts(self, text: str, user_id: str) -> dict: ...
    async def classify_importance(self, text: str) -> str: ...


class Extractor:
    """대화 텍스트에서 메모리를 추출하는 메인 클래스"""

    # 한국어 ephemeral 판별 기준 (eng review: "5단어 이하" → 글자수 기반으로 수정)
    EPHEMERAL_MAX_CHARS = 15
    EPHEMERAL_PATTERNS = ["ㅋ", "ㅎ", "ㅇㅋ", "오키", "넵", "네네", "ㄴㄴ", "점심", "ㅇㅇ"]

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def extract(
        self, text: str, user_id: str, session_id: Optional[str] = None
    ) -> ExtractionResult:
        """텍스트에서 fact/entity/relation 추출 + 중요도 분류"""

        # --- E10: 빈 입력 처리 ---
        if not text or not text.strip():
            return ExtractionResult(facts=[], raw_text=text or "", user_id=user_id)

        # --- 추출 시도 (LLM or fallback) ---
        try:
            raw_result = await self._llm.extract_facts(text, user_id)
            facts = self._parse_facts(raw_result, text)
        except Exception:
            # E9: LLM 실패 fallback → raw text를 그대로 fact으로 저장
            facts = [Fact(
                content=text,
                fact_type="raw_fallback",
                importance=Importance.important,
            )]

        # --- 중요도 분류 (규칙 우선 + LLM fallback) ---
        for fact in facts:
            importance = self._classify_by_rules(fact.content)
            if importance:
                fact.importance = importance
            else:
                try:
                    level = await self._llm.classify_importance(fact.content)
                    fact.importance = Importance(level)
                except Exception:
                    fact.importance = Importance.important  # safe default

        return ExtractionResult(
            facts=facts,
            raw_text=text,
            user_id=user_id,
            session_id=session_id,
            timestamp=datetime.now(),
        )

    def _parse_facts(self, raw: dict, original_text: str) -> list[Fact]:
        """LLM 출력을 Fact 리스트로 변환"""
        facts = []
        for f in raw.get("facts", []):
            entities = [
                Entity(**e) for e in raw.get("entities", [])
            ]
            relations = [
                Relation(**r) for r in raw.get("relations", [])
            ]
            importance = Importance(f.get("importance", "important"))
            facts.append(Fact(
                content=f.get("content", original_text),
                entities=entities,
                relations=relations,
                importance=importance,
                fact_type=f.get("fact_type", "general"),
            ))
        return facts

    def _classify_by_rules(self, text: str) -> Optional[Importance]:
        """
        규칙 기반 중요도 분류 (1차 필터)
        - ephemeral: 짧은 텍스트 + ephemeral 패턴
        - critical: 날짜/일정/결정 키워드
        - None: 규칙 매칭 실패 → LLM fallback 필요
        """
        stripped = text.strip()

        # --- Ephemeral: 한국어 글자수 기반 (eng review 수정) ---
        if len(stripped) <= self.EPHEMERAL_MAX_CHARS:
            if any(p in stripped for p in self.EPHEMERAL_PATTERNS):
                return Importance.ephemeral
            # 단순 응답 (네, 응, 아니, 좋아 등)
            simple_responses = ["네", "응", "아니", "좋아", "알겠습니다", "네 알겠습니다"]
            if stripped in simple_responses:
                return Importance.ephemeral

        # --- Critical: 일정/결정 키워드 ---
        critical_keywords = [
            "일정", "마감", "이사", "출장", "결정", "계약",
            "연봉", "퇴사", "입사", "승진",
        ]
        date_pattern = re.compile(
            r"\d{1,2}[/\-\.]\d{1,2}|\d{1,2}월\s*\d{1,2}일|내일|모레|다음\s*주|이번\s*주"
        )
        has_critical_keyword = any(kw in stripped for kw in critical_keywords)
        has_date = bool(date_pattern.search(stripped))

        if has_critical_keyword or (has_date and len(stripped) > self.EPHEMERAL_MAX_CHARS):
            return Importance.critical

        return None  # LLM fallback 필요
