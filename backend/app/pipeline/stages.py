"""Typed pipeline stages. ChatService remains the orchestrator; these stages are the single entry points."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.context_ref import ContextRef
from app.contracts.conversation_state import ConversationState
from app.contracts.query import QueryPlan
from app.pipeline.safety import PreSafetyDecision, SafetyLayer
from app.routing.jev_router import resolve_plan
from app.routing.schemas import JevTrace


@dataclass(frozen=True)
class RouteResult:
    plan: QueryPlan
    jev_trace: JevTrace


class SafetyStage:
    def __init__(self, layer: SafetyLayer | None = None):
        self.layer = layer or SafetyLayer()

    def run(self, message: str) -> PreSafetyDecision:
        return self.layer.check_input(message)


class RouteStage:
    """Single routing pipeline: Jev primary, deterministic fallback inside resolve_plan."""

    def run(
        self,
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
    ) -> RouteResult:
        plan, trace = resolve_plan(
            message,
            conversation_summary=conversation_summary,
            previous_user_message=previous_user_message,
            previous_intent=previous_intent,
            follow_up_topic=follow_up_topic,
            follow_up_name=follow_up_name,
            prior_personal=prior_personal,
            document_ids=document_ids,
            uploaded_document_count=uploaded_document_count,
            prior_source_mode=prior_source_mode,
            context_ref=context_ref,
            conversation_state=conversation_state,
        )
        return RouteResult(plan=plan, jev_trace=trace)
