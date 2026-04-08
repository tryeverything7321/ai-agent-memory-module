"""실제 LLM 클라이언트 — DooGPU LiteLLM Proxy (OpenAI SDK 호환)

Extraction과 Intent Classification에서 사용.
extraction.py의 LLMClient Protocol을 구현.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from openai import OpenAI

from config import settings


class DooGPULLMClient:
    """DooGPU LiteLLM Proxy를 통한 실제 LLM 호출"""

    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        api_key: str = None,
    ):
        self._base_url = base_url or settings.llm_base_url
        self._model = model or settings.llm_model
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=api_key or settings.llm_api_key,
        )

    async def extract_facts(self, text: str, user_id: str) -> dict:
        """LLM으로 대화에서 facts/entities/relations 추출"""
        prompt = f"""다음 대화에서 핵심 정보를 추출하세요.

대화: "{text}"

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "facts": [
    {{"content": "추출된 사실", "fact_type": "general|schedule|preference|decision", "importance": "ephemeral|important|critical"}}
  ],
  "entities": [
    {{"name": "엔티티명", "entity_type": "person|place|project|date|organization"}}
  ],
  "relations": [
    {{"source": "엔티티1", "target": "엔티티2", "relation_type": "관계유형"}}
  ]
}}

규칙:
- 날짜/일정/마감이 포함되면 importance를 "critical"로
- 단순 인사/감탄("ㅋㅋ", "오키", "넵")이면 importance를 "ephemeral"로
- 사람 이름, 장소, 프로젝트명은 entities에 포함
- 관계가 명시적이면 relations에 포함"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "당신은 대화에서 핵심 정보를 추출하는 AI입니다. JSON만 출력하세요."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1024,
        )

        raw = response.choices[0].message.content.strip()
        return self._parse_json_response(raw)

    async def classify_importance(self, text: str) -> str:
        """LLM으로 중요도 분류"""
        prompt = f"""다음 텍스트의 중요도를 분류하세요.

텍스트: "{text}"

아래 중 하나만 답하세요 (다른 텍스트 없이):
- ephemeral: 일상 대화, 인사, 감탄사
- important: 업무 맥락, 선호도, 프로젝트 정보
- critical: 일정, 개인정보 변경, 결정사항"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "중요도를 한 단어로만 답하세요: ephemeral, important, critical"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=20,
        )

        raw = response.choices[0].message.content.strip().lower()
        # "ephemeral", "important", "critical" 중 하나 추출
        for level in ["critical", "important", "ephemeral"]:
            if level in raw:
                return level
        return "important"  # 기본값

    async def classify_intent(self, text: str) -> Optional[str]:
        """LLM으로 intent 분류 (규칙 실패 시 fallback)"""
        categories = (
            "weekly_report, issue_tracking, scheduling, knowledge_lookup, "
            "code_review, meeting_prep, data_analysis, team_communication, "
            "document_drafting, project_status, onboarding, troubleshooting"
        )
        prompt = f"""다음 텍스트의 의도를 분류하세요.

텍스트: "{text}"

카테고리: {categories}

가장 적합한 카테고리 하나만 답하세요 (다른 텍스트 없이):"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": f"카테고리 중 하나만 답하세요: {categories}"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=30,
        )

        raw = response.choices[0].message.content.strip().lower()
        valid = [
            "weekly_report", "issue_tracking", "scheduling", "knowledge_lookup",
            "code_review", "meeting_prep", "data_analysis", "team_communication",
            "document_drafting", "project_status", "onboarding", "troubleshooting",
        ]
        for cat in valid:
            if cat in raw:
                return cat
        return None

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """LLM 응답에서 JSON 파싱 (마크다운 코드블록 처리)"""
        # ```json ... ``` 패턴 제거
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = cleaned.strip().rstrip("`")

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 빈 결과
            return {"facts": [], "entities": [], "relations": []}
