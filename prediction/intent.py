"""Intent 분류 — 규칙 기반 1차 + LLM fallback 2차

12개 intent taxonomy (동적 확장 가능):
  weekly_report, issue_tracking, scheduling, knowledge_lookup,
  code_review, meeting_prep, data_analysis, team_communication,
  document_drafting, project_status, onboarding, troubleshooting
"""

from __future__ import annotations

import re
from typing import Optional

from models import IntentCategory


# 규칙 기반 분류용 키워드 맵
INTENT_RULES: list[tuple[IntentCategory, list[str]]] = [
    (IntentCategory.weekly_report, ["주간 보고", "주간보고", "weekly report", "주보"]),
    (IntentCategory.issue_tracking, ["이슈", "버그", "장애", "인시던트", "백로그"]),
    (IntentCategory.scheduling, ["일정", "스케줄", "미팅", "회의", "출장", "캘린더"]),
    (IntentCategory.code_review, ["PR", "리뷰", "코드 리뷰", "코드리뷰", "머지", "pull request"]),
    (IntentCategory.meeting_prep, ["미팅 준비", "회의 준비", "발표 자료", "미팅자료"]),
    (IntentCategory.data_analysis, ["데이터", "분석", "지표", "벨로시티", "대시보드", "통계"]),
    (IntentCategory.team_communication, ["공유", "메일", "슬랙", "알림", "공지"]),
    (IntentCategory.document_drafting, ["문서 작성", "문서작성", "초안", "보고서 작성"]),
    (IntentCategory.project_status, ["진행 상황", "스탠드업", "오늘 할 일", "현황"]),
    (IntentCategory.onboarding, ["온보딩", "신입", "첫 출근", "입사"]),
    (IntentCategory.troubleshooting, ["에러", "오류", "500", "디버그", "원인", "해결"]),
]

# 대소문자 무시 패턴으로 컴파일
_COMPILED_RULES: list[tuple[IntentCategory, re.Pattern]] = [
    (intent, re.compile("|".join(re.escape(kw) for kw in keywords), re.IGNORECASE))
    for intent, keywords in INTENT_RULES
]


class IntentClassifier:
    """규칙 기반 1차 분류 + fallback"""

    def classify(self, text: str) -> IntentCategory:
        """텍스트를 intent로 분류. 규칙 우선, 실패 시 knowledge_lookup 기본값"""
        result = self._classify_by_rules(text)
        if result:
            return result
        # LLM fallback은 실제 연동 시 추가
        return IntentCategory.knowledge_lookup

    def _classify_by_rules(self, text: str) -> Optional[IntentCategory]:
        """키워드 매칭 기반 분류"""
        for intent, pattern in _COMPILED_RULES:
            if pattern.search(text):
                return intent
        return None
