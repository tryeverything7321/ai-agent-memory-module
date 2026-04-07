"""Prediction Layer 테스트 — Intent 분류, 전이 그래프, 선제적 주입

P1: 규칙 기반 intent 분류
P2: LLM fallback intent
P3: transition 기록
P4: 예측 (threshold 이상)
P5: 예측 (threshold 미달)
P6: proactive injection
"""

import pytest
from datetime import datetime

from models import Memory, Importance, IntentCategory
from storage.graph_store import GraphStore
from prediction.intent import IntentClassifier
from prediction.proactive import ProactiveInjector


class TestIntentClassifier:
    """P1-P2: Intent 분류"""

    def test_p1_rule_based_weekly_report(self):
        """P1: 규칙 기반 — '주간 보고서 작성' → weekly_report"""
        classifier = IntentClassifier()
        result = classifier.classify("주간 보고서 작성해야 하는데")
        assert result == IntentCategory.weekly_report

    def test_p1_rule_based_code_review(self):
        classifier = IntentClassifier()
        result = classifier.classify("오늘 리뷰할 PR 있어?")
        assert result == IntentCategory.code_review

    def test_p1_rule_based_scheduling(self):
        classifier = IntentClassifier()
        result = classifier.classify("내일 일정 정리해줘")
        assert result == IntentCategory.scheduling

    def test_p1_rule_based_troubleshooting(self):
        classifier = IntentClassifier()
        result = classifier.classify("500 에러가 나는데 원인 찾아줘")
        assert result == IntentCategory.troubleshooting

    def test_p1_rule_based_onboarding(self):
        classifier = IntentClassifier()
        result = classifier.classify("신입사원 온보딩 자료 어디 있어요?")
        assert result == IntentCategory.onboarding

    def test_p2_fallback_default(self):
        """P2: 규칙 매칭 실패 시 기본값 (knowledge_lookup)"""
        classifier = IntentClassifier()
        result = classifier.classify("이건 어떤 규칙에도 안 걸리는 문장")
        assert result == IntentCategory.knowledge_lookup  # 기본 fallback


class TestTransitionGraph:
    """P3-P5: Intent 전이 그래프"""

    async def test_p3_record_transition(self, graph_store):
        """P3: transition 기록 → edge weight 증가"""
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "scheduling")

        weight = graph_store.get_transition_weight("weekly_report", "issue_tracking")
        assert weight > 0.5  # 2/3 ≈ 0.67

    async def test_p4_prediction_above_threshold(self, graph_store):
        """P4: transition_weight > 0.5 → 예측 반환"""
        # 3회 반복 → weight = 1.0
        for _ in range(3):
            graph_store.record_intent_transition("weekly_report", "issue_tracking")

        result = graph_store.get_next_intent("weekly_report")
        assert result is not None
        assert result[0] == "issue_tracking"
        assert result[1] > 0.5

    async def test_p5_prediction_below_threshold(self, graph_store):
        """P5: 첫 전이 기록 → weight가 분산되면 threshold 미달"""
        # 4개 다른 intent로 분산
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "scheduling")
        graph_store.record_intent_transition("weekly_report", "data_analysis")
        graph_store.record_intent_transition("weekly_report", "team_communication")

        result = graph_store.get_next_intent("weekly_report")
        assert result is not None
        # 각각 0.25 → 모두 threshold(0.5) 미달
        assert result[1] <= 0.5


class TestProactiveInjector:
    """P6: Proactive injection"""

    async def test_p6_injection_above_threshold(self, metadata_store, graph_store):
        """예측 + 관련 메모리 있으면 → '예측된 컨텍스트' 레이블로 주입"""
        # 전이 패턴 학습 (강한 패턴)
        for _ in range(5):
            graph_store.record_intent_transition("weekly_report", "issue_tracking")

        # 관련 메모리 저장
        mem = Memory(
            user_id="user_pm",
            content="지난 주 이슈: API 서버 레이턴시 문제",
            importance=Importance.important,
        )
        await metadata_store.save_memory(mem)

        injector = ProactiveInjector(graph_store=graph_store, metadata_store=metadata_store)
        prediction = await injector.predict_and_fetch(
            current_intent=IntentCategory.weekly_report,
            user_id="user_pm",
        )

        assert prediction is not None
        assert prediction.predicted_next == IntentCategory.issue_tracking
        assert prediction.transition_weight > 0.5

    async def test_p6_no_injection_below_threshold(self, metadata_store, graph_store):
        """threshold 미달 → 주입하지 않음"""
        # 분산된 전이 (각 0.25)
        graph_store.record_intent_transition("weekly_report", "issue_tracking")
        graph_store.record_intent_transition("weekly_report", "scheduling")
        graph_store.record_intent_transition("weekly_report", "data_analysis")
        graph_store.record_intent_transition("weekly_report", "team_communication")

        injector = ProactiveInjector(graph_store=graph_store, metadata_store=metadata_store)
        prediction = await injector.predict_and_fetch(
            current_intent=IntentCategory.weekly_report,
            user_id="user_pm",
        )

        assert prediction is None  # threshold 미달 → None

    async def test_p6_injection_label(self, metadata_store, graph_store):
        """주입된 컨텍스트에 '예측된 컨텍스트' 레이블 확인"""
        for _ in range(5):
            graph_store.record_intent_transition("weekly_report", "issue_tracking")

        mem = Memory(user_id="user_pm", content="이슈 데이터")
        await metadata_store.save_memory(mem)

        injector = ProactiveInjector(graph_store=graph_store, metadata_store=metadata_store)
        context = await injector.build_injection_context(
            current_intent=IntentCategory.weekly_report,
            user_id="user_pm",
        )

        if context:
            assert "예측된 컨텍스트" in context
