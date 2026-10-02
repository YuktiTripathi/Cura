"""Semantic conversation continuity. Never a source of authoritative personal values."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TurnType(str, Enum):
    new_question = "NEW_QUESTION"
    follow_up_question = "FOLLOW_UP_QUESTION"
    answer_to_assistant = "ANSWER_TO_ASSISTANT"
    clarification = "CLARIFICATION"
    reference_resolution = "REFERENCE_RESOLUTION"
    topic_switch = "TOPIC_SWITCH"
    confirmation = "CONFIRMATION"
    correction = "CORRECTION"


class ExpectedReplyType(str, Enum):
    none = "NONE"
    clinical_context = "CLINICAL_CONTEXT"
    confirmation = "CONFIRMATION"
    report_choice = "REPORT_CHOICE"
    metric_choice = "METRIC_CHOICE"
    yes_no = "YES_NO"


class ConversationState(BaseModel):
    turn_type: TurnType = TurnType.new_question
    active_domain: str | None = None
    active_entities: list[str] = Field(default_factory=list)
    active_source: str | None = None
    active_report_id: str | None = None
    previous_user_question: str | None = None
    previous_assistant_summary: str | None = None
    previous_assistant_follow_up: str | None = None
    previous_intent: str | None = None
    expected_reply_type: ExpectedReplyType = ExpectedReplyType.none
    expected_handling_path: str | None = None
    recently_referenced: list[str] = Field(default_factory=list)
    unresolved_references: list[str] = Field(default_factory=list)
    resolved_references: dict[str, str] = Field(default_factory=dict)
    new_context: list[str] = Field(default_factory=list)
    operations_hint: list[str] = Field(default_factory=list)
    prior_personal: bool = False
    resolved_time_scope: str | None = None
    last_surfaced_catalog_id: str | None = None
    last_surfaced_catalog_name: str | None = None
    communication_style: str | None = None
    recent_context_notes: list[str] = Field(default_factory=list)
    dismissed_insight_keys: list[str] = Field(default_factory=list)
    session_goal_code: str | None = None
    current_concern: str | None = None
    response_depth: str | None = None
    conversation_goal: str | None = None
    topic_turn_count: int = 0
    explained_entities: list[str] = Field(default_factory=list)
    topic_summary: str | None = None
    active_topic: str | None = None
    current_goal: str | None = None
    previous_goal: str | None = None
    user_tone: str = "neutral"
    facts_already_explained: list[str] = Field(default_factory=list)
    biomarkers_already_discussed: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    resolved_query: str | None = None
