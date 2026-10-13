"""Jev structured router. Jev never retrieves data or generates the final medical answer."""

from __future__ import annotations

import logging
import re
import time

from app.contracts.context_ref import ContextRef
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.pipeline.intent import extract_topics, is_contextual_follow_up, requires_personal_record
from app.pipeline.ontology import requested_metrics_from_message
from app.contracts.conversation_state import ConversationState
from app.pipeline.conversation_state import apply_to_query_plan
from app.pipeline.planner import attach_task_plan
from app.pipeline.query_planner import build_query_plan
from app.pipeline.task_contract import apply_task_contract
from app.routing.jev_client import JevDecisionsClient
from app.routing.mapper import force_general_plan, plan_from_jev
from app.routing.schemas import JevRoutingState, JevTrace
from app.routing.validator import JevDecisionValidationError, validate_jev_decision

_CONTINUING_TURNS = {
    "ANSWER_TO_ASSISTANT",
    "FOLLOW_UP_QUESTION",
    "REFERENCE_RESOLUTION",
    "CONFIRMATION",
    "CLARIFICATION",
    "CORRECTION",
}

logger = logging.getLogger("cura.routing")

JEV_MIN_CONFIDENCE = 0.80

_SUPPORTED_CAPABILITIES = [
    "profile",
    "blood_reports",
    "lab_results",
    "bio_ai_report",
    "bio_ai_trends",
    "health_metrics",
    "uploaded_documents",
    "nutrition_preferences",
    "health_goals",
    "questionnaires",
]


def resolve_plan(
    message: str,
    *,
    conversation_summary: str = "",
    previous_user_message: str | None = None,
    previous_intent: str | None = None,
    follow_up_topic: str | None = None,
    follow_up_name: str | None = None,
    prior_personal: bool = False,
    document_ids: list[str] | None = None,
    uploaded_document_count: int = 0,
    prior_source_mode: str | None = None,
    context_ref: ContextRef | None = None,
    conversation_state: ConversationState | None = None,
) -> tuple[QueryPlan, JevTrace]:
    deterministic = build_query_plan(
        message,
        follow_up_topic,
        follow_up_name,
        prior_personal=prior_personal,
        document_ids=document_ids,
        uploaded_document_count=uploaded_document_count,
        prior_source_mode=prior_source_mode,
        context_ref=context_ref,
        conversation_state=conversation_state,
    )
    if conversation_state and conversation_state.turn_type.value in _CONTINUING_TURNS:
        prior_personal = True
    deterministic = _maybe_demote_personal(
        deterministic,
        message,
        prior_personal=prior_personal,
        follow_up_topic=follow_up_topic,
        context_ref=context_ref,
        document_ids=document_ids or [],
        conversation_state=conversation_state,
    )
    if not settings.jev_enabled:
        return deterministic, JevTrace(called=False, fallback=False)
    if settings.jev_fast_path and _obvious_request(deterministic, message, conversation_state, document_ids or []):
        # "What is my HbA1c?" / "What is HbA1c?": the deterministic planner is certain and a
        # router round trip would only add latency. Anything ambiguous still goes to Jev.
        logger.info("jev_skipped reason=fast_path intent=%s", deterministic.intent.value)
        return deterministic, JevTrace(called=False, fallback=False, fallback_reason="fast_path")

    state = JevRoutingState(
        current_message=message,
        previous_user_message=previous_user_message,
        previous_intent=previous_intent,
        previous_personal_data_used=prior_personal,
        current_topic=follow_up_topic,
        prior_source_mode=prior_source_mode,
        selected_document_count=len(document_ids or []),
        uploaded_document_available=uploaded_document_count > 0,
        supported_capabilities=_SUPPORTED_CAPABILITIES,
        turn_type=conversation_state.turn_type.value if conversation_state else None,
        active_entities=list(conversation_state.active_entities) if conversation_state else [],
        expected_reply_type=conversation_state.expected_reply_type.value if conversation_state else None,
        previous_assistant_follow_up=conversation_state.previous_assistant_follow_up if conversation_state else None,
        resolved_references=dict(conversation_state.resolved_references) if conversation_state else {},
        new_context=list(conversation_state.new_context) if conversation_state else [],
        operations_hint=list(conversation_state.operations_hint) if conversation_state else [],
    )
    started = time.perf_counter()
    try:
        decision, response = JevDecisionsClient().decide(state)
        decision = _bind_metrics(
            decision,
            deterministic.topic,
            follow_up_topic,
            message,
            conversation_state=conversation_state,
        )
        decision = validate_jev_decision(
            decision,
            state,
            deterministic_requires_personal=requires_personal_record(
                message,
                prior_personal=prior_personal,
                follow_up_topic=follow_up_topic,
            ),
        )
    except (LLMUnavailableError, JevDecisionValidationError, ValueError) as exc:
        reason = exc.__class__.__name__
        logger.warning("jev_fallback reason=%s detail=%s", reason, exc)
        fallback_plan = deterministic.model_copy(update={"fallback_reason": reason})
        return fallback_plan, JevTrace(
            called=True,
            fallback=True,
            fallback_reason=reason,
            validation_error=str(exc) if isinstance(exc, JevDecisionValidationError) else None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            model=settings.jev_model,
        )
    latency = int((time.perf_counter() - started) * 1000)
    if decision.intent.value == "clarification" or decision.requires_clarification:
        plan = _bind_conversation_plan(
            plan_from_jev(
                decision,
                message,
                follow_up_topic=follow_up_topic,
                follow_up_name=follow_up_name,
                document_ids=document_ids,
                uploaded_document_count=uploaded_document_count,
                prior_source_mode=prior_source_mode,
                context_ref=context_ref,
            ),
            message,
            conversation_state,
            decision=decision,
        )
        logger.info(
            "jev_decision status=clarification confidence=%s latency_ms=%s",
            decision.confidence,
            latency,
        )
        return plan, JevTrace(
            called=True,
            fallback=False,
            latency_ms=latency,
            model=response.model or settings.jev_model,
            provider=response.provider,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            decision=decision,
            validated=True,
            overridden=False,
        )
    if decision.confidence is None:
        logger.warning("jev_fallback reason=confidence_unavailable")
        fallback_plan = deterministic.model_copy(update={"fallback_reason": "confidence_unavailable"})
        return fallback_plan, JevTrace(
            called=True,
            fallback=True,
            fallback_reason="confidence_unavailable",
            latency_ms=latency,
            model=response.model or settings.jev_model,
            provider=response.provider,
            decision=decision,
            validated=True,
        )
    if decision.confidence < JEV_MIN_CONFIDENCE:
        logger.warning("jev_fallback reason=low_confidence confidence=%s", decision.confidence)
        fallback_plan = deterministic.model_copy(update={"fallback_reason": "low_confidence"})
        return fallback_plan, JevTrace(
            called=True,
            fallback=True,
            fallback_reason="low_confidence",
            latency_ms=latency,
            model=response.model or settings.jev_model,
            provider=response.provider,
            decision=decision,
            validated=True,
        )
    plan = _bind_conversation_plan(
        plan_from_jev(
            decision,
            message,
            follow_up_topic=follow_up_topic,
            follow_up_name=follow_up_name,
            document_ids=document_ids,
            uploaded_document_count=uploaded_document_count,
            prior_source_mode=prior_source_mode,
            context_ref=context_ref,
        ),
        message,
        conversation_state,
        decision=decision,
    )
    plan = _maybe_demote_personal(
        plan,
        message,
        prior_personal=prior_personal,
        follow_up_topic=follow_up_topic,
        context_ref=context_ref,
        document_ids=document_ids or [],
        conversation_state=conversation_state,
    )
    logger.info(
        "jev_decision status=accepted intent=%s operation=%s source=%s personal=%s "
        "historical=%s document=%s clarification=%s confidence=%s latency_ms=%s overridden=False",
        decision.intent.value,
        decision.operation.value,
        decision.source.value,
        decision.requires_personal_data,
        decision.requires_historical_data,
        decision.requires_document_search,
        decision.requires_clarification,
        decision.confidence,
        latency,
    )
    return plan, JevTrace(
        called=True,
        fallback=False,
        latency_ms=latency,
        model=response.model or settings.jev_model,
        provider=response.provider,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        decision=decision,
        validated=True,
        overridden=False,
    )


def _bind_conversation_plan(plan: QueryPlan, message: str, conversation_state: ConversationState | None, *, decision=None) -> QueryPlan:
    plan = apply_to_query_plan(plan, conversation_state)
    plan = attach_task_plan(plan, message, decision=decision)
    return apply_task_contract(plan, message)


def _bind_metrics(
    decision,
    deterministic_topic: str | None,
    follow_up_topic: str | None,
    message: str,
    conversation_state: ConversationState | None = None,
):
    """Fill empty Jev metrics. Current-turn ontology always beats stale follow-up memory."""
    current = requested_metrics_from_message(message)
    if current:
        return decision.model_copy(update={"requested_metrics": current})
    if decision.requested_metrics or decision.requested_entities:
        return decision
    inherit = None
    if conversation_state and conversation_state.turn_type.value in _CONTINUING_TURNS and conversation_state.active_entities:
        return decision.model_copy(update={"requested_metrics": list(conversation_state.active_entities)})
    if is_contextual_follow_up(message) and not extract_topics(message)[0] and not extract_topics(message)[1]:
        inherit = follow_up_topic
    topic = inherit or deterministic_topic
    if topic:
        return decision.model_copy(update={"requested_metrics": [topic]})
    return decision


def _maybe_demote_personal(
    plan: QueryPlan,
    message: str,
    *,
    prior_personal: bool,
    follow_up_topic: str | None,
    context_ref: ContextRef | None,
    document_ids: list[str],
    conversation_state: ConversationState | None = None,
) -> QueryPlan:
    if conversation_state and conversation_state.turn_type.value in _CONTINUING_TURNS:
        return plan
    if context_ref or document_ids:
        return plan
    if requires_personal_record(message, prior_personal=prior_personal, follow_up_topic=follow_up_topic):
        return plan
    selectors = {str(item).upper() for item in (plan.selectors or [])}
    if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and re.search(
        r"\b(markers?|values?|results?|report|labs?)\b", message or "", re.I
    ):
        if not re.search(r"\b(typically|in general|what causes|generally)\b", message or "", re.I):
            return plan
    if not plan.needs_personal_data:
        return plan
    if plan.general_personalization:
        # This is still a general-education task. The personal read is an optional,
        # topic-scoped supplement and must survive the anti-misrouting guard.
        return plan
    logger.info("routing_guard demoted_personal_to_general intent=%s topic=%s", plan.intent.value, plan.topic)
    return force_general_plan(plan)


_FAST_LOOKUP = re.compile(
    r"^\s*(?:what(?:'s| is| was)|show(?: me)?|tell me)\s+(?:my\s+)?(?:latest\s+|current\s+|last\s+)?"
    r"[a-z0-9 \-]{2,40}?\s*(?:value|level|result|score)?\s*\??\s*$",
    re.I,
)


def _obvious_request(plan: QueryPlan, message: str, conversation_state, document_ids: list[str]) -> bool:
    """Short, single-topic questions that deterministic planning already resolves."""
    if document_ids or plan.needs_user_uploaded:
        return False
    if conversation_state is not None and conversation_state.turn_type.value in _CONTINUING_TURNS:
        return False
    text = (message or "").strip()
    if len(text.split()) > 12:
        return False
    from app.pipeline.semantic_plan import ReasoningGoal, build_semantic_plan

    semantic = build_semantic_plan(text)
    if semantic.clarification_needed:
        return False
    named_topics = [*semantic.markers, *semantic.bio_ai]
    interpretation_goals = {
        ReasoningGoal.explain,
        ReasoningGoal.causes,
        ReasoningGoal.assess,
        ReasoningGoal.risk,
    }
    if (
        plan.needs_personal_data
        and len(named_topics) == 1
        and not plan.history
        and not plan.needs_cross_source
        and semantic.primary_goal in interpretation_goals
        and set(semantic.secondary_goals) <= interpretation_goals
    ):
        return True
    if semantic.secondary_goals:
        return False
    if not _FAST_LOOKUP.match(text) or len(text.split()) > 8:
        return False
    if plan.intent.value == "latest_result" and semantic.primary_goal == ReasoningGoal.lookup:
        return len(plan.requested_metrics or ([plan.topic] if plan.topic else [])) == 1
    if plan.intent.value == "general_health_question" and semantic.primary_goal == ReasoningGoal.general_education:
        return bool(semantic.markers or semantic.bio_ai)
    return False
