"""ReasoningService: LOOKUP-only stays deterministic; multi-entity/multi-op uses the LLM."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from app.contracts.common import AnswerModelTier, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.copy import general_knowledge_unavailable
from app.core.errors import LLMUnavailableError
from app.llm.factory import get_llm_client
from app.llm.models import LLMStructuredOutput
from app.llm.registry import fallback_tiers, uses_answer_llm
from app.pipeline.planner import plan_needs_reasoning
from app.pipeline.quality_gate import review_answer, should_escalate_to_deep
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.response_planner import build_response_plan
from app.pipeline.renderer import (
    DeterministicRenderer,
    render_bio_ai_ambiguity,
    render_bio_ai_score_list,
    render_diagnosis_restraint,
    render_missing_blood_marker,
    render_provenance,
)
from app.retrieval.medical import is_servable, render_medical_evidence_answer

logger = logging.getLogger("cura.reasoning")


@dataclass
class ReasoningResult:
    answer: str
    llm_result: LLMStructuredOutput | None = None
    llm_called: bool = False
    llm_mode: str = "deterministic"
    answer_client: object | None = None
    model_fallback_used: bool = False
    latency_ms: int | None = None
    flags: list[str] = field(default_factory=list)
    model_escalated: bool = False
    escalation_reason: str | None = None
    first_token_ms: int | None = None


class ReasoningService:
    def __init__(self, prompts: PromptBuilder | None = None, renderer: DeterministicRenderer | None = None):
        self.prompts = prompts or PromptBuilder()
        self.renderer = renderer or DeterministicRenderer()

    def run(
        self,
        *,
        message: str,
        plan: QueryPlan,
        context: HealthContext,
        conversation_summary: str = "",
        response_lang=None,
        routing_note: str | None = None,
        medical_hits: list | None = None,
        general_only: bool = False,
        diagnosis_restraint: bool = False,
        budget=None,
        complete_answer=None,
        on_token=None,
    ) -> ReasoningResult:
        started = time.perf_counter()
        medical_hits = medical_hits or []
        if diagnosis_restraint:
            return ReasoningResult(
                answer=render_diagnosis_restraint(context),
                llm_mode="structured_safety",
            )
        if (plan.operation or "").upper() == "PROVENANCE":
            return ReasoningResult(answer=render_provenance(context), llm_mode="structured_provenance")
        lookup = self._lookup_only(plan, context)
        structured_bio_ai = (
            lookup
            and plan.intent == IntentType.bio_ai_score
            and bool(context.bio_ai_risks)
            and context.status != "ambiguous"
            and not plan.needs_user_uploaded
        )
        explain_bio = bool(re.search(r"\b(explain|interpret|what does|what do|mean|understand)\b", message or "", re.I))
        if explain_bio and context.bio_ai_risks and settings.enable_llm and not uses_answer_llm(plan.answer_model_tier):
            plan = plan.model_copy(update={"answer_model_tier": AnswerModelTier.standard_medical})
        if structured_bio_ai and not (explain_bio and settings.enable_llm):
            return ReasoningResult(
                answer=render_bio_ai_score_list(context.bio_ai_risks),
                llm_mode="structured_bio_ai",
            )
        if (
            lookup
            and plan.intent == IntentType.bio_ai_score
            and context.status == "ambiguous"
            and not plan.needs_user_uploaded
        ):
            return ReasoningResult(answer=render_bio_ai_ambiguity(context), llm_mode="structured_bio_ai")
        if (
            lookup
            and plan.intent == IntentType.bio_ai_score
            and context.status != "ambiguous"
            and not context.bio_ai_risks
            and not plan.needs_user_uploaded
            and any(getattr(item, "reason", None) == "score_not_available" for item in context.missing)
        ):
            return ReasoningResult(answer="Score not available in this report.", llm_mode="structured_bio_ai")
        response_plan = build_response_plan(message, plan, context)
        if response_plan.kind == "report_overview" and context.markers:
            highlights = [
                m for m in context.markers
                if getattr(m.flag, "value", str(m.flag)) in {"low", "high", "critical"}
            ]
            detail = ""
            if highlights:
                names = ", ".join(m.name for m in highlights[:3])
                detail = f" The results worth reviewing first are {names}."
            return ReasoningResult(
                answer=f"{response_plan.direct_answer} {response_plan.summary}{detail}".strip(),
                llm_mode="structured_report_overview",
            )

        if (
            lookup
            and plan.intent in {IntentType.latest_result, IntentType.previous_result}
            and plan.needs_blood
            and context.markers
            and context.status != "ambiguous"
            and not plan.needs_user_uploaded
            and not plan.needs_cross_source
        ):
            return ReasoningResult(
                answer=self.renderer.render(message, context),
                llm_mode="structured_blood",
            )
        if (
            lookup
            and plan.intent in {
                IntentType.latest_result,
                IntentType.previous_result,
                IntentType.blood_marker_explanation,
            }
            and plan.needs_blood
            and not context.markers
            and any(getattr(item, "reason", None) in {"no_reports", "not_in_reports"} for item in context.missing)
        ):
            return ReasoningResult(answer=render_missing_blood_marker(context), llm_mode="structured_blood")

        completer = complete_answer or self._complete_answer
        if general_only:
            corpus_answer = render_medical_evidence_answer(plan.topic, medical_hits)
            if corpus_answer and definition_from_reviewed_passage(message, plan, medical_hits):
                # Cost lever 4: a plain definition is answered from the reviewed passage, no model call.
                return ReasoningResult(
                    answer=corpus_answer,
                    llm_called=False,
                    llm_mode="medical_corpus_definition",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            messages = self.prompts.build(
                context, conversation_summary, message, response_lang, routing_note=routing_note
            )
            streamed = self._stream_low_risk(message, plan, messages, on_token, started)
            if streamed is not None:
                return streamed
            try:
                llm_result, answer_client, _tier, fallback = completer(messages, plan, budget=budget)
                return ReasoningResult(
                    answer=llm_result.answer,
                    llm_result=llm_result,
                    llm_called=True,
                    llm_mode=settings.resolved_llm_provider() if settings.enable_llm else "deterministic_mock",
                    answer_client=answer_client,
                    model_fallback_used=fallback,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            except LLMUnavailableError:
                if corpus_answer:
                    return ReasoningResult(
                        answer=corpus_answer,
                        llm_called=True,
                        llm_mode="medical_corpus",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                return ReasoningResult(
                    answer=general_knowledge_unavailable(response_lang),
                    llm_called=True,
                    llm_mode="unavailable",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        if settings.enable_llm and uses_answer_llm(plan.answer_model_tier) and (
            plan_needs_reasoning(plan) or not lookup or (explain_bio and context.bio_ai_risks)
        ):
            messages = self.prompts.build(
                context, conversation_summary, message, response_lang, routing_note=routing_note
            )
            try:
                llm_result, answer_client, used_tier, fallback = completer(messages, plan, budget=budget)
                answer = llm_result.answer
                escalated = False
                escalation_reason = None
                if used_tier == AnswerModelTier.standard_medical:
                    from app.routing.model_tier import _keep_on_flash

                    gate = review_answer(answer, plan, context)
                    if not _keep_on_flash(plan) and should_escalate_to_deep(gate.flags, plan, context, answer, llm_result):
                        deep_plan = plan.model_copy(update={
                            "answer_model_tier": AnswerModelTier.deep_medical_reasoning,
                            "model_tier": AnswerModelTier.deep_medical_reasoning,
                        })
                        try:
                            llm_result, answer_client, used_tier, _deep_fallback = completer(
                                messages, deep_plan, budget=budget
                            )
                            answer = llm_result.answer
                            escalated = True
                            escalation_reason = ", ".join(gate.flags[:4]) or "quality_gate"
                            fallback = True
                        except LLMUnavailableError:
                            logger.warning("deep_medical_escalation_unavailable")
                if llm_result.parse_error and not answer:
                    answer = self.renderer.render(message, context)
                return ReasoningResult(
                    answer=answer,
                    llm_result=llm_result,
                    llm_called=True,
                    llm_mode=settings.resolved_llm_provider() if settings.enable_llm else "deterministic_mock",
                    answer_client=answer_client,
                    model_fallback_used=fallback,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    model_escalated=escalated,
                    escalation_reason=escalation_reason,
                )
            except LLMUnavailableError:
                logger.warning("llm_unavailable")
                return ReasoningResult(
                    answer=self.renderer.render(message, context),
                    llm_called=True,
                    llm_mode="deterministic_fallback",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        return ReasoningResult(
            answer=self.renderer.render(message, context),
            llm_mode=settings.resolved_llm_provider() if settings.enable_llm else "deterministic_mock",
        )

    def _lookup_only(self, plan: QueryPlan, context: HealthContext) -> bool:
        if plan_needs_reasoning(plan):
            return False
        if context.status == "ambiguous":
            return True
        return True

    def _complete_answer(self, messages, plan, budget=None):
        from app.llm.openrouter_policy import openrouter_policy
        from app.pipeline.dlp import SecurityBlockedError

        openrouter_policy().assert_privacy_for_health(personal_health=bool(plan.needs_personal_data))
        last_error = None
        remaining = budget.remaining() if budget is not None else float(settings.llm_timeout_seconds)
        for index, tier in enumerate(fallback_tiers(plan.answer_model_tier)):
            tier_cap = {
                AnswerModelTier.standard_medical.value: 18.0,
                AnswerModelTier.deep_medical_reasoning.value: 28.0,
                AnswerModelTier.fast_reasoning.value: 12.0,
            }.get(tier.value, 20.0)
            timeout = min(float(settings.llm_timeout_seconds), remaining, tier_cap)
            if budget is not None:
                timeout = budget.timeout_for(timeout)
            if timeout < 0.5:
                break
            client = get_llm_client(
                model_tier=tier.value,
                timeout=timeout,
                personal_health=bool(plan.needs_personal_data),
            )
            started = time.perf_counter()
            try:
                result = client.complete_structured(messages)
                logger.info(
                    "answer_llm tier=%s model=%s fallback=%s latency_ms=%s",
                    tier.value,
                    client.model,
                    index > 0,
                    int((time.perf_counter() - started) * 1000),
                )
                return result, client, tier, index > 0
            except SecurityBlockedError as exc:
                raise LLMUnavailableError("LLM request blocked by privacy policy") from exc
            except LLMUnavailableError as exc:
                last_error = exc
                remaining = budget.remaining() if budget is not None else remaining
        raise last_error or LLMUnavailableError("LLM request failed")



    def _stream_low_risk(self, message, plan, messages, on_token, started) -> ReasoningResult | None:
        """Stream tokens for low-risk general answers only (plan 5.4). None = use the normal path."""
        from app.pipeline.topic_risk import is_high_risk_topic

        if on_token is None or settings.chat_streaming_mode != "tokens_low_risk" or not settings.enable_llm:
            return None
        if is_high_risk_topic(message):
            return None
        first_token: list[int] = []

        def _timed(delta: str) -> None:
            if not first_token:
                first_token.append(int((time.perf_counter() - started) * 1000))
            on_token(delta)

        try:
            client = get_llm_client(
                model_tier=(plan.answer_model_tier or AnswerModelTier.standard_medical).value,
                timeout=float(settings.llm_timeout_seconds),
                personal_health=False,
            )
            text = client.stream_text(
                [*messages, {"role": "user", "content": "Reply in plain text, not JSON."}],
                _timed,
            )
        except Exception:  # noqa: BLE001 - fall back to the normal, non-streamed answer
            logger.warning("answer_stream status=fallback")
            return None
        return ReasoningResult(
            answer=text,
            llm_result=LLMStructuredOutput(answer=text),
            llm_called=True,
            llm_mode=settings.resolved_llm_provider(),
            answer_client=client,
            latency_ms=int((time.perf_counter() - started) * 1000),
            first_token_ms=first_token[0] if first_token else None,
        )


_DEFINITION = re.compile(
    r"^\s*(what\s+(is|are|does)\b.{0,40}?\b(mean|measure|stand for|do)?\??\s*$|"
    r"what\s+is\s+the\s+difference\s+between\b|define\b|meaning\s+of\b)",
    re.I,
)


def definition_from_reviewed_passage(message: str, plan, medical_hits) -> bool:
    """True for a plain definition question that a reviewed passage on the same topic answers."""
    from app.pipeline.topic_risk import is_high_risk_topic

    if not settings.deterministic_definitions_enabled or not medical_hits:
        return False
    if not settings.medical_require_reviewed_enabled():
        return False  # never answer directly from the unreviewed development index
    if is_high_risk_topic(message) or not _DEFINITION.search(message or ""):
        return False
    if len((message or "").split()) > 14:
        return False
    if not all(is_servable(doc) for doc in medical_hits):
        return False
    topic = (plan.topic or "").lower()
    return bool(topic) and any(topic in doc.topics for doc in medical_hits)
