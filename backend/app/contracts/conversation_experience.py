"""Conversation experience contracts. Presentation only; not medical truth."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConversationGoal(str, Enum):
    quick_answer = "QUICK_ANSWER"
    understand = "UNDERSTAND"
    reassurance = "REASSURANCE"
    prioritize = "PRIORITIZE"
    action_plan = "ACTION_PLAN"
    deep_dive = "DEEP_DIVE"
    health_review = "HEALTH_REVIEW"
    follow_up = "FOLLOW_UP"


class ResponseDepth(str, Enum):
    short = "SHORT"
    standard = "STANDARD"
    guided = "GUIDED"
    deep = "DEEP"


class NextBestConversationAction(str, Enum):
    none = "NONE"
    explain_pattern = "EXPLAIN_PATTERN"
    show_trend = "SHOW_TREND"
    explore_domain = "EXPLORE_DOMAIN"
    identify_missing_data = "IDENTIFY_MISSING_DATA"
    suggest_actions = "SUGGEST_ACTIONS"
    ask_clarifying_question = "ASK_CLARIFYING_QUESTION"
    offer_testing_option = "OFFER_TESTING_OPTION"


class ResponseBlockKind(str, Enum):
    direct_answer = "DIRECT_ANSWER"
    personal_result = "PERSONAL_RESULT"
    why_it_matters = "WHY_IT_MATTERS"
    related_context = "RELATED_CONTEXT"
    pattern = "PATTERN"
    reassurance = "REASSURANCE"
    uncertainty = "UNCERTAINTY"
    missing_info = "MISSING_INFO"
    next_step = "NEXT_STEP"
    follow_up = "FOLLOW_UP"
    source = "SOURCE"


class RelevantContext(BaseModel):
    requested_keys: list[str] = Field(default_factory=list)
    supporting_keys: list[str] = Field(default_factory=list)
    related_trend_keys: list[str] = Field(default_factory=list)
    relevant_missing_keys: list[str] = Field(default_factory=list)
    pattern_keys: list[str] = Field(default_factory=list)
    pattern_note: str | None = None


class ResponseBlock(BaseModel):
    kind: ResponseBlockKind
    title: str | None = None
    text: str | None = None
    expandable: bool = False


class TopicSummary(BaseModel):
    main_facts: list[str] = Field(default_factory=list)
    user_told_cura: list[str] = Field(default_factory=list)
    remaining_question: str | None = None
    text: str | None = None


class ConversationExperiencePlan(BaseModel):
    goal: ConversationGoal = ConversationGoal.quick_answer
    depth: ResponseDepth = ResponseDepth.standard
    next_action: NextBestConversationAction = NextBestConversationAction.none
    blocks: list[ResponseBlockKind] = Field(default_factory=list)
    relevant: RelevantContext = Field(default_factory=RelevantContext)
    topic_summary: TopicSummary | None = None
    ask_follow_up: bool = False
    current_concern: str | None = None
