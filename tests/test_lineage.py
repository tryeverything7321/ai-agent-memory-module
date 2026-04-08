"""PhylogeneticLineage 테스트 — 택소노미 계통수 이벤트 기록 및 DAG 관리

L1: bootstrap 기록
L2: discovery 기록
L3: split → DAG 엣지 생성
L4: merge → DAG 엣지 생성
L5: extinction 기록
L6: alive 카테고리 필터링
L7: summary 통계
L8: JSON 직렬화 왕복 검증
"""

import pytest

from taxonomy.lineage import PhylogeneticLineage


@pytest.fixture
def lineage() -> PhylogeneticLineage:
    """빈 계통수 인스턴스"""
    return PhylogeneticLineage()


class TestRecordEvents:
    """L1-L5: 개별 이벤트 기록"""

    def test_l1_record_bootstrap(self, lineage: PhylogeneticLineage):
        """L1: bootstrap 이벤트가 DAG 노드와 이벤트 로그에 기록된다."""
        lineage.record_bootstrap("scheduling", member_count=42)

        events = lineage.get_events()
        assert len(events) == 1
        assert events[0]["type"] == "bootstrap"
        assert events[0]["category"] == "scheduling"
        assert events[0]["metadata"]["member_count"] == 42
        assert "timestamp" in events[0]

        # DAG에 노드 존재
        tree = lineage.get_lineage_tree()
        assert "scheduling" in tree

    def test_l2_record_discovery(self, lineage: PhylogeneticLineage):
        """L2: discovery 이벤트가 기록되고 trigger_message가 메타데이터에 포함된다."""
        lineage.record_discovery(
            "incident_response",
            trigger_message="서버 장애 대응 절차 알려줘",
        )

        events = lineage.get_events()
        assert len(events) == 1
        assert events[0]["type"] == "discovery"
        assert events[0]["category"] == "incident_response"
        assert events[0]["metadata"]["trigger_message"] == "서버 장애 대응 절차 알려줘"

    def test_l3_record_split_creates_edges(self, lineage: PhylogeneticLineage):
        """L3: split 이벤트가 부모→자식 엣지를 DAG에 생성한다."""
        lineage.record_bootstrap("scheduling", member_count=100)
        lineage.record_split(
            parent="scheduling",
            child_a="internal_meeting",
            child_b="client_meeting",
            reason="intra-variance > 0.5",
        )

        tree = lineage.get_lineage_tree()
        # 부모에서 두 자식으로의 엣지 확인
        assert "internal_meeting" in tree["scheduling"]
        assert "client_meeting" in tree["scheduling"]

        # 이벤트 로그 확인
        split_event = lineage.get_events()[1]
        assert split_event["type"] == "split"
        assert split_event["parent"] == "scheduling"
        assert set(split_event["children"]) == {"internal_meeting", "client_meeting"}

        # 부모는 멸종 상태
        assert "scheduling" not in lineage.get_alive_categories()

    def test_l4_record_merge_creates_edges(self, lineage: PhylogeneticLineage):
        """L4: merge 이벤트가 두 부모→자식 엣지를 DAG에 생성한다."""
        lineage.record_bootstrap("code_review", member_count=30)
        lineage.record_bootstrap("debugging", member_count=25)
        lineage.record_merge(
            parent_a="code_review",
            parent_b="debugging",
            child="code_investigation",
            reason="cosine similarity > 0.85",
        )

        tree = lineage.get_lineage_tree()
        # 두 부모에서 자식으로의 엣지 확인
        assert "code_investigation" in tree["code_review"]
        assert "code_investigation" in tree["debugging"]

        # 이벤트 로그 확인
        merge_event = lineage.get_events()[2]
        assert merge_event["type"] == "merge"
        assert set(merge_event["parents"]) == {"code_review", "debugging"}
        assert merge_event["child"] == "code_investigation"

        # 두 부모는 멸종 상태
        alive = lineage.get_alive_categories()
        assert "code_review" not in alive
        assert "debugging" not in alive
        assert "code_investigation" in alive

    def test_l5_record_extinction(self, lineage: PhylogeneticLineage):
        """L5: extinction 이벤트가 카테고리를 멸종 처리한다."""
        lineage.record_bootstrap("onboarding", member_count=5)
        lineage.record_extinction("onboarding", final_weight=0.02)

        events = lineage.get_events()
        assert len(events) == 2
        ext_event = events[1]
        assert ext_event["type"] == "extinction"
        assert ext_event["category"] == "onboarding"
        assert ext_event["metadata"]["final_weight"] == 0.02

        assert "onboarding" not in lineage.get_alive_categories()


class TestQueries:
    """L6-L7: 조회 메서드"""

    def test_l6_get_alive_categories(self, lineage: PhylogeneticLineage):
        """L6: bootstrap 3개 중 1개 멸종 → alive 2개"""
        lineage.record_bootstrap("scheduling", member_count=50)
        lineage.record_bootstrap("code_review", member_count=30)
        lineage.record_bootstrap("onboarding", member_count=10)

        lineage.record_extinction("onboarding", final_weight=0.01)

        alive = lineage.get_alive_categories()
        assert alive == {"scheduling", "code_review"}
        assert len(alive) == 2

    def test_l7_get_summary_counts(self, lineage: PhylogeneticLineage):
        """L7: summary가 이벤트 유형별 카운트를 정확히 집계한다."""
        # 다양한 이벤트 기록
        lineage.record_bootstrap("a", member_count=10)
        lineage.record_bootstrap("b", member_count=20)
        lineage.record_bootstrap("c", member_count=30)
        lineage.record_discovery("d", trigger_message="test")
        lineage.record_split("a", "a1", "a2", reason="variance")
        lineage.record_merge("b", "c", "bc", reason="similar")
        lineage.record_extinction("d", final_weight=0.01)

        summary = lineage.get_summary()
        assert summary["total_events"] == 7
        assert summary["event_counts"]["bootstrap"] == 3
        assert summary["event_counts"]["discovery"] == 1
        assert summary["event_counts"]["split"] == 1
        assert summary["event_counts"]["merge"] == 1
        assert summary["event_counts"]["extinction"] == 1

        # 노드: a, b, c, d, a1, a2, bc = 7
        assert summary["total_nodes"] == 7
        # alive: a1, a2, bc (a→extinct by split, b,c→extinct by merge, d→extinct)
        assert summary["alive_categories"] == 3
        # extinct: a, b, c, d = 4
        assert summary["extinct_categories"] == 4


class TestSerialization:
    """L8: JSON 직렬화 왕복"""

    def test_l8_serialization_roundtrip(self, lineage: PhylogeneticLineage):
        """L8: to_json → from_json 왕복 후 DAG와 상태가 동일하다."""
        # 원본 이벤트 기록
        lineage.record_bootstrap("scheduling", member_count=50)
        lineage.record_bootstrap("code_review", member_count=30)
        lineage.record_discovery("incident", trigger_message="서버 장애")
        lineage.record_split("scheduling", "internal", "client", reason="variance")
        lineage.record_merge("code_review", "incident", "investigation", reason="similar")
        lineage.record_extinction("investigation", final_weight=0.03)

        # 직렬화
        serialized = lineage.to_json()
        assert isinstance(serialized, list)
        assert len(serialized) == 6

        # 새 인스턴스에서 복원
        restored = PhylogeneticLineage()
        restored.from_json(serialized)

        # 이벤트 수 동일
        assert len(restored.get_events()) == len(lineage.get_events())

        # alive 카테고리 동일
        assert restored.get_alive_categories() == lineage.get_alive_categories()

        # summary 동일
        original_summary = lineage.get_summary()
        restored_summary = restored.get_summary()
        assert original_summary["total_events"] == restored_summary["total_events"]
        assert original_summary["total_nodes"] == restored_summary["total_nodes"]
        assert original_summary["alive_categories"] == restored_summary["alive_categories"]
        assert original_summary["extinct_categories"] == restored_summary["extinct_categories"]
        assert original_summary["event_counts"] == restored_summary["event_counts"]

        # DAG 구조 동일
        assert restored.get_lineage_tree() == lineage.get_lineage_tree()
