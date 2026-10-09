"""ReasoningService: LOOKUP-only stays deterministic; multi-entity/multi-op uses the LLM."""

from __future__ import annotations

import logging
import re
import time

from app.core import perf
from dataclasses import dataclass, field

from app.contracts.common import AnswerModelTier, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.copy import general_knowledge_unavailable
from app.core.errors import LLMUnavailableError
from app.llm.factory import get_llm_client
from app.llm.models import LLMStructuredOutput
from app.llm.registry import answer_timeout_for_tier, fallback_tiers, uses_answer_llm
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


DEEP_UNAVAILABLE_MESSAGE = (
    "I couldn't work through this one properly just now, and I'd rather not give you a partial answer "
    "to a question that connects several of your results. Please try again in a minute."
)


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
    answer_tier: AnswerModelTier | None = None  # tier that actually wrote the answer


def _is_different_model(current: AnswerModelTier, target: AnswerModelTier) -> bool:
    """Escalating only helps when the target tier is a different model; otherwise it repeats the call."""
    from app.llm.registry import model_id_for_tier

    try:
        return model_id_for_tier(target) != model_id_for_tier(current)
    except Exception:  # noqa: BLE001 - unknown configuration: do not repeat the call
        return False


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
        explain_bio = bool(re.search(r"\b(explain|interpret|what does|what do|mean|understand|how should i read)\b", message or "", re.I))
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
        interpret_turn = "INTERPRET" in {str(op).upper() for op in plan.operations or []}
        if response_plan.kind == "report_overview" and context.markers and not interpret_turn:
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
        if (plan.task_contract or {}).get("response_type") == "ABNORMAL_LIST" and context.markers:
            from app.pipeline.evidence_inventory import assemble_evidence

            abnormal = assemble_evidence(plan, context)
            if abnormal.measurements:
                lines = [
                    f"{row.get('name')}: {row.get('value')} {row.get('unit') or ''} ({row.get('flag')})".replace("  ", " ")
                    for row in abnormal.measurements
                ]
                return ReasoningResult(
                    answer="These results are outside the range on the report: " + "; ".join(lines) + ".",
                    llm_called=False,
                    llm_mode="verified_abnormal_list",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

        if (
            lookup
            and not explain_bio
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
            with perf.stage("prompt_build"):
                messages = self.prompts.build(
                    context, conversation_summary, message, response_lang, routing_note=routing_note
                )
            perf.count("prompt_chars", sum(len(m.get("content") or "") for m in messages))
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
            from app.pipeline.evidence_inventory import assemble_evidence

            package = assemble_evidence(plan, context)
            if plan.task_contract:
                context.evidence_package = package.prompt_payload()
                if package.blocked_answer:
                    return ReasoningResult(
                        answer=package.blocked_answer,
                        llm_called=False,
                        llm_mode="evidence_unavailable",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                if package.response_type == "MARKER_LOOKUP" and len(package.measurements) == 1:
                    row = package.measurements[0]
                    unit = row.get("unit") or ""
                    answer = (
                        f"{row.get('name')} is {row.get('value')} {unit}. "
                        f"The report marks it {row.get('flag') or 'unknown'}."
                    ).replace("  ", " ")
                    return ReasoningResult(
                        answer=answer.strip(),
                        llm_called=False,
                        llm_mode="verified_marker",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
            with perf.stage("prompt_build"):
                messages = self.prompts.build(
                    context, conversation_summary, message, response_lang, routing_note=routing_note
                )
            perf.count("prompt_chars", sum(len(m.get("content") or "") for m in messages))
            try:
                llm_result, answer_client, used_tier, fallback = completer(messages, plan, budget=budget)
                answer = llm_result.answer
                escalated = False
                escalation_reason = None
                next_tier = {
                    AnswerModelTier.fast_reasoning: AnswerModelTier.standard_medical,
                    AnswerModelTier.standard_medical: AnswerModelTier.deep_medical_reasoning,
                }.get(used_tier)
                if next_tier is not None and not fallback:
                    from app.routing.model_tier import _keep_on_flash, forced_answer_tier

                    gate = review_answer(answer, plan, context)
                    if (
                        forced_answer_tier() is None
                        and not _keep_on_flash(plan)
                        and _is_different_model(used_tier, next_tier)
                        and should_escalate_to_deep(gate.flags, plan.model_copy(update={"answer_model_tier": used_tier}), context, answer, llm_result)
                    ):
                        # Controlled escalation: one more call, one tier up, only when the
                        # answer could not reconcile the evidence or produced no usable output.
                        up_plan = plan.model_copy(update={
                            "answer_model_tier": next_tier,
                            "model_tier": next_tier,
                            "complexity_score": max(plan.complexity_score or 0, 9),  # no downgrade fallback
                        })
                        try:
                            llm_result, answer_client, used_tier, _up_fallback = completer(
                                messages, up_plan, budget=budget
                            )
                            answer = llm_result.answer
                            escalated = True
                            escalation_reason = ", ".join(gate.flags[:4]) or "quality_gate"
                        except LLMUnavailableError:
                            logger.warning("answer_escalation_unavailable tier=%s", next_tier.value)
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
                    answer_tier=used_tier,
                )
            except LLMUnavailableError:
                logger.warning("llm_unavailable tier=%s", plan.answer_model_tier.value if plan.answer_model_tier else None)
                if plan.answer_model_tier == AnswerModelTier.deep_medical_reasoning:
                    # A complex question is not answered by a template that looks equivalent.
                    return ReasoningResult(
                        answer=DEEP_UNAVAILABLE_MESSAGE,
                        llm_called=True,
                        llm_mode="answer_model_unavailable",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
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
        for index, tier in enumerate(fallback_tiers(plan.answer_model_tier, plan.complexity_score)):
            timeout = min(float(settings.llm_timeout_seconds), remaining, answer_timeout_for_tier(tier))
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
