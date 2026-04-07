"""Extraction Layer 테스트 — TDD red phase

12개 코드 경로:
  E1-E4: 기본 추출 (fact, entity, relation, metadata)
  E5-E7: 중요도 분류 (ephemeral, important, critical)
  E8: 한국어 ephemeral 판별
  E9: LLM 실패 fallback
  E10-E11: 엣지 케이스
  E12: 비동기 추출
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from models import Importance, IntentCategory, ExtractionResult


# --- LLM Mock ---

class MockLLMClient:
    """규칙 기반 mock LLM — 테스트에서 실제 LLM 호출 대체"""

    async def extract_facts(self, text: str, user_id: str) -> dict:
        """텍스트에서 fact/entity/relation을 규칙 기반으로 추출"""
        facts = []
        entities = []
        relations = []

        # 날짜/일정 키워드 → schedule fact
        schedule_keywords = ["출장", "회의", "미팅", "일정", "다음 주", "내일", "오늘"]
        if any(kw in text for kw in schedule_keywords):
            facts.append({"content": text, "fact_type": "schedule", "importance": "critical"})

        # 사람 이름 패턴 (X팀장, X님)
        import re
        name_matches = re.findall(r"(\w+(?:팀장|님|과장|부장|대리))", text)
        for name in name_matches:
            entities.append({"name": name, "entity_type": "person"})

        # 장소 키워드
        place_keywords = ["판교", "대만", "서울", "오피스"]
        for kw in place_keywords:
            if kw in text:
                entities.append({"name": kw, "entity_type": "place"})

        # 관계 추출 (X가 Y 담당/참석)
        relation_matches = re.findall(r"(\w+)(?:이|가)\s+(\w+)\s+(담당|참석|관련)", text)
        for src, tgt, rel in relation_matches:
            relations.append({"source": src, "target": tgt, "relation_type": rel})

        # 일반 fact
        if not facts:
            facts.append({"content": text, "fact_type": "general", "importance": "important"})

        return {"facts": facts, "entities": entities, "relations": relations}

    async def classify_importance(self, text: str) -> str:
        """중요도 분류 — 규칙 기반 mock"""
        critical_keywords = ["일정", "이사", "출장", "결정", "마감", "날짜"]
        if any(kw in text for kw in critical_keywords):
            return "critical"
        ephemeral_patterns = ["ㅋ", "ㅎ", "오키", "ㅇㅋ", "넵", "점심"]
        if any(p in text for p in ephemeral_patterns) and len(text) < 20:
            return "ephemeral"
        return "important"


@pytest.fixture
def mock_llm():
    return MockLLMClient()


class TestExtraction:
    """E1-E4: 기본 추출"""

    async def test_e1_single_fact(self, mock_llm):
        """E1: 단일 fact 추출"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("다음 주 대만 출장이야", "user_pm")

        assert len(result.facts) > 0
        assert any("출장" in f.content for f in result.facts)

    async def test_e2_multiple_entities(self, mock_llm):
        """E2: 복수 entity 추출"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("김팀장이 판교 오피스에서 회의", "user_pm")

        all_entities = []
        for f in result.facts:
            all_entities.extend(f.entities)
        entity_names = [e.name for e in all_entities]
        assert "김팀장" in entity_names
        assert "판교" in entity_names

    async def test_e3_relation_extraction(self, mock_llm):
        """E3: relation 추출"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("A팀이 B프로젝트 담당", "user_pm")

        all_relations = []
        for f in result.facts:
            all_relations.extend(f.relations)
        assert len(all_relations) > 0

    async def test_e4_metadata_tagging(self, mock_llm):
        """E4: 메타데이터 태깅"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("테스트 대화", "user_pm", session_id="sess_1")

        assert result.user_id == "user_pm"
        assert result.session_id == "sess_1"
        assert result.timestamp is not None


class TestClassification:
    """E5-E8: 중요도 분류"""

    async def test_e5_ephemeral(self, mock_llm):
        """E5: ephemeral 분류"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("ㅋㅋ 오키", "user_new")

        assert any(f.importance == Importance.ephemeral for f in result.facts)

    async def test_e6_important(self, mock_llm):
        """E6: important 분류"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("우리 팀 OKR 바꿔야 할 것 같아", "user_pm")

        assert any(f.importance == Importance.important for f in result.facts)

    async def test_e7_critical(self, mock_llm):
        """E7: critical 분류"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("내일 3시 이사회 참석 일정", "user_pm")

        assert any(f.importance == Importance.critical for f in result.facts)

    async def test_e8_korean_ephemeral(self, mock_llm):
        """E8: 한국어 ephemeral — 토큰/글자수 기반 판별"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)

        # 짧지만 의미 있을 수 있는 텍스트
        result = await extractor.extract("네 알겠습니다", "user_new")
        # "네 알겠습니다"는 짧지만 명시적 승인이므로 ephemeral이어야 함
        assert any(f.importance == Importance.ephemeral for f in result.facts)


class TestEdgeCases:
    """E9-E11: 엣지 케이스"""

    async def test_e9_llm_failure_fallback(self):
        """E9: LLM 실패 시 raw text fallback"""
        from extraction import Extractor

        class FailingLLM:
            async def extract_facts(self, text, user_id):
                raise ConnectionError("LLM API timeout")
            async def classify_importance(self, text):
                raise ConnectionError("LLM API timeout")

        extractor = Extractor(llm_client=FailingLLM())
        result = await extractor.extract("중요한 내용인데 LLM이 죽었어", "user_pm")

        # fallback: raw text를 그대로 fact으로 저장
        assert len(result.facts) > 0
        assert result.raw_text == "중요한 내용인데 LLM이 죽었어"

    async def test_e10_empty_input(self, mock_llm):
        """E10: 빈 대화 처리"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)
        result = await extractor.extract("", "user_pm")

        assert len(result.facts) == 0

    async def test_e11_multi_turn(self, mock_llm):
        """E11: 멀티턴 대화 추출"""
        from extraction import Extractor
        extractor = Extractor(llm_client=mock_llm)

        texts = ["출장 일정 잡아야 해", "대만으로 가자", "김팀장도 같이 가"]
        all_facts = []
        for text in texts:
            result = await extractor.extract(text, "user_pm")
            all_facts.extend(result.facts)

        assert len(all_facts) >= 3
