"""Jev structured router. Jev never retrieves data or generates the final medical answer."""

from __future__ import annotations

import logging
import time

from app.contracts.context_ref import ContextRef
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.pipeline.intent import extract_topics, is_contextual_follow_up, requires_personal_record
from app.pipeline.ontology import requested_metrics_from_message
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_client import JevDecisionsClient
from app.routing.mapper import force_general_plan, plan_from_jev
from app.routing.schemas import JevRoutingState, JevTrace
from app.routing.validator import JevDecisionValidationError, validate_jev_decision

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
    )
    deterministic = _maybe_demote_personal(
        deterministic,
        message,
        prior_personal=prior_personal,
        follow_up_topic=follow_up_topic,
        context_ref=context_ref,
        document_ids=document_ids or [],
    )
    if not settings.jev_enabled:
        return deterministic, JevTrace(called=False, fallback=False)

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
    )
    started = time.perf_counter()
    try:
        decision, response = JevDecisionsClient().decide(state)
        decision = _bind_metrics(decision, deterministic.topic, follow_up_topic, message)
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
        plan = plan_from_jev(
            decision,
            message,
            follow_up_topic=follow_up_topic,
            follow_up_name=follow_up_name,
            document_ids=document_ids,
            uploaded_document_count=uploaded_document_count,
            prior_source_mode=prior_source_mode,
            context_ref=context_ref,
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
    plan = plan_from_jev(
        decision,
        message,
        follow_up_topic=follow_up_topic,
        follow_up_name=follow_up_name,
        document_ids=document_ids,
        uploaded_document_count=uploaded_document_count,
        prior_source_mode=prior_source_mode,
        context_ref=context_ref,
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


def _bind_metrics(decision, deterministic_topic: str | None, follow_up_topic: str | None, message: str):
    """Fill empty Jev metrics. Current-turn ontology always beats stale follow-up memory."""
    current = requested_metrics_from_message(message)
    if current:
        return decision.model_copy(update={"requested_metrics": current})
    if decision.requested_metrics or decision.requested_entities:
        return decision
    inherit = follow_up_topic if (is_contextual_follow_up(message) and not extract_topics(message)[0] and not extract_topics(message)[1]) else None
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
) -> QueryPlan:
    if context_ref or document_ids:
        return plan
    if requires_personal_record(message, prior_personal=prior_personal, follow_up_topic=follow_up_topic):
        return plan
    if not plan.needs_personal_data:
        return plan
    logger.info("routing_guard demoted_personal_to_general intent=%s topic=%s", plan.intent.value, plan.topic)
    return force_general_plan(plan)
