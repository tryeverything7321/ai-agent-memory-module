"""선제적 예측 + 컨텍스트 주입

Anticipatory Memory Chains의 핵심:
  1. 현재 intent에서 다음 intent를 예측 (transition graph)
  2. transition_weight > threshold(0.5)일 때만 주입
  3. 예측된 메모리를 "예측된 컨텍스트" 레이블로 시스템 프롬프트에 추가
"""

from __future__ import annotations

from typing import Optional

from config import settings
from models import IntentCategory, IntentPrediction, Memory
from storage.graph_store import GraphStore
from storage.metadata_store import MetadataStore


class ProactiveInjector:
    """Intent 전이 예측 → 관련 메모리 프리페치 → 컨텍스트 주입"""

    def __init__(
        self,
        graph_store: GraphStore,
        metadata_store: MetadataStore,
        threshold: float = None,
    ):
        self._graph = graph_store
        self._metadata = metadata_store
        self._threshold = threshold or settings.prediction_threshold

    async def predict_and_fetch(
        self, current_intent: IntentCategory, user_id: str
    ) -> Optional[IntentPrediction]:
        """
        예측 수행:
          1. TransitionGraph에서 다음 intent 예측
          2. threshold 미달 → None 반환 (주입하지 않음)
          3. threshold 이상 → 관련 메모리 프리페치
        """
        next_result = self._graph.get_next_intent(current_intent.value)
        if not next_result:
            return None

        predicted_intent, weight = next_result
        if weight <= self._threshold:
            return None

        # 관련 메모리 프리페치
        memories = await self._fetch_relevant_memories(predicted_intent, user_id)

        try:
            predicted_category = IntentCategory(predicted_intent)
        except ValueError:
            predicted_category = IntentCategory.knowledge_lookup

        return IntentPrediction(
            current_intent=current_intent,
            predicted_next=predicted_category,
            transition_weight=weight,
            predicted_memories=memories,
        )

    async def build_injection_context(
        self, current_intent: IntentCategory, user_id: str
    ) -> Optional[str]:
        """
        예측 결과를 '예측된 컨텍스트' 레이블이 붙은 문자열로 변환.
        LLM 시스템 프롬프트에 주입할 형태.
        """
        prediction = await self.predict_and_fetch(current_intent, user_id)
        if not prediction:
            return None

        lines = [
            f"[예측된 컨텍스트] 다음 행동 예측: {prediction.predicted_next.value} "
            f"(확률: {prediction.transition_weight:.0%})",
        ]
        for mem in prediction.predicted_memories:
            lines.append(f"  - {mem.content}")

        return "\n".join(lines)

    async def _fetch_relevant_memories(
        self, predicted_intent: str, user_id: str
    ) -> list[Memory]:
        """예측된 intent와 관련된 메모리 조회 (키워드 기반 간이 매칭)"""
        all_memories = await self._metadata.get_memories_by_user(user_id, valid_only=True)

        # intent 키워드로 간이 필터링
        intent_keywords = self._get_intent_keywords(predicted_intent)
        relevant = []
        for mem in all_memories:
            if any(kw in mem.content for kw in intent_keywords):
                relevant.append(mem)
            if len(relevant) >= 3:  # 최대 3개
                break

        return relevant

    @staticmethod
    def _get_intent_keywords(intent: str) -> list[str]:
        """intent → 관련 키워드 매핑"""
        keyword_map = {
            "weekly_report": ["주간", "보고", "report"],
            "issue_tracking": ["이슈", "버그", "장애", "에러"],
            "scheduling": ["일정", "스케줄", "미팅"],
            "knowledge_lookup": ["문서", "가이드", "방법"],
            "code_review": ["PR", "리뷰", "코드"],
            "meeting_prep": ["미팅", "발표", "자료"],
            "data_analysis": ["데이터", "분석", "지표"],
            "team_communication": ["공유", "메일", "알림"],
            "document_drafting": ["문서", "작성", "초안"],
            "project_status": ["진행", "현황", "스탠드업"],
            "onboarding": ["온보딩", "신입", "가이드"],
            "troubleshooting": ["에러", "디버그", "해결"],
        }
        return keyword_map.get(intent, [intent])
