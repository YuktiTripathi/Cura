"""Narrow optional personal context for an otherwise general educational turn."""

from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.health_topics import (
    evidence_bio_ai_for,
    evidence_markers_for,
    extract_topics,
    questionnaire_keys_for,
)


def attach_general_personalization(plan: QueryPlan, message: str) -> QueryPlan:
    """Keep the general objective while requesting only topic-relevant sources."""
    if plan.intent != IntentType.general_health_question or plan.knowledge_scope != KnowledgeScope.general:
        return plan
    topics = extract_topics(message, conversation_entities=plan.conversation_entities)
    markers = evidence_markers_for(topics)[:6]
    bio_ai = evidence_bio_ai_for(topics)[:4]
    questionnaire = questionnaire_keys_for(topics, limit=6)
    if not (markers or bio_ai or questionnaire):
        return plan
    plan.general_personalization = True
    plan.semantic_scoped = True
    plan.needs_blood = bool(markers)
    plan.needs_bio_ai = bool(bio_ai)
    plan.needs_questionnaire = bool(questionnaire)
    plan.needs_lifestyle = bool(questionnaire)
    plan.needs_supershyft = True
    plan.needs_general = True
    plan.source = QuerySource.mixed
    plan.requested_metrics = list(dict.fromkeys([*plan.requested_metrics, *markers, *bio_ai]))
    plan.reasoning_context = list(dict.fromkeys([*plan.reasoning_context, *questionnaire]))
    return plan
