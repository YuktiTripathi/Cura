"""Conversational intelligence: continuity, goal, tone, and response shape.

This package does not store medical values. Health facts still come from retrieval.
"""

from app.pipeline.conversation.followup_planner import plan_conversational_followup
from app.pipeline.conversation.reference_resolver import ResolvedConversationQuery, resolve_reference
from app.pipeline.conversation.response_planner import (
    ResponsePlan,
    apply_conversational_retrieval,
    build_response_plan,
)
from app.pipeline.conversation.state import (
    ConversationalGoal,
    UserTone,
    enrich_conversation_intelligence,
    facts_explained_for_turn,
    infer_conversational_goal,
    infer_user_tone,
)

__all__ = [
    "ConversationalGoal",
    "ResolvedConversationQuery",
    "ResponsePlan",
    "UserTone",
    "apply_conversational_retrieval",
    "build_response_plan",
    "enrich_conversation_intelligence",
    "facts_explained_for_turn",
    "infer_conversational_goal",
    "infer_user_tone",
    "plan_conversational_followup",
    "resolve_reference",
]
