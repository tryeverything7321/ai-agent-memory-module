"""Pydantic 데이터 모델 — Memory, Fact, Entity, Intent 등 전체 도메인 모델"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class Importance(str, Enum):
    ephemeral = "ephemeral"
    important = "important"
    critical = "critical"


class IntentCategory(str, Enum):
    """12개 초기 intent taxonomy (동적 확장 가능)"""
    weekly_report = "weekly_report"
    issue_tracking = "issue_tracking"
    scheduling = "scheduling"
    knowledge_lookup = "knowledge_lookup"
    code_review = "code_review"
    meeting_prep = "meeting_prep"
    data_analysis = "data_analysis"
    team_communication = "team_communication"
    document_drafting = "document_drafting"
    project_status = "project_status"
    onboarding = "onboarding"
    troubleshooting = "troubleshooting"


# --- Core Models ---

class Entity(BaseModel):
    """추출된 엔티티"""
    name: str
    entity_type: str = "unknown"  # person, place, project, date, ...


class Relation(BaseModel):
    """두 엔티티 간 관계"""
    source: str
    target: str
    relation_type: str  # 담당, 참석, 위치, ...


class Fact(BaseModel):
    """대화에서 추출된 단일 사실"""
    content: str
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    importance: Importance = Importance.ephemeral
    fact_type: str = "general"  # schedule, preference, decision, ...


class Memory(BaseModel):
    """저장된 메모리 단위"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str
    facts: list[Fact] = Field(default_factory=list)
    importance: Importance = Importance.ephemeral
    decay_lambda: float = 0.3
    decay_weight: float = 1.0
    access_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed_at: datetime = Field(default_factory=datetime.now)
    is_valid: bool = True
    embedding: Optional[list[float]] = None
    session_id: Optional[str] = None


class ExtractionResult(BaseModel):
    """Extraction Layer 출력"""
    facts: list[Fact]
    raw_text: str
    user_id: str
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SearchResult(BaseModel):
    """검색 결과 단위"""
    memory: Memory
    score: float
    source: str = "fusion"  # vector, metadata, graph, fusion


class IntentPrediction(BaseModel):
    """Intent 예측 결과"""
    current_intent: IntentCategory
    predicted_next: Optional[IntentCategory] = None
    transition_weight: float = 0.0
    predicted_memories: list[Memory] = Field(default_factory=list)


# --- API Models ---

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    memories_used: list[SearchResult] = Field(default_factory=list)
    prediction: Optional[IntentPrediction] = None


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None


# --- Conversation (합성 데이터용) ---

class ConversationTurn(BaseModel):
    """대화 한 턴"""
    role: str  # user, assistant
    content: str
    timestamp: datetime
    intent: Optional[IntentCategory] = None


class ConversationSession(BaseModel):
    """대화 세션"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
