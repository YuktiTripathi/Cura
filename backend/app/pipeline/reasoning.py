"""ReasoningService: verified facts are deterministic; the approved model writes the reply."""

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


_CLINICAL_CHANGE = re.compile(
    r"\b(improved|improvement|better|worse|worsened|right direction|clinically meaningful)\b",
    re.I,
)


def _false_unit_mismatch(message: str, context: HealthContext, answer: str) -> bool:
    if not re.search(r"units do not match|units differ|incompatible units", answer or "", re.I):
        return False
    from app.pipeline.evidence_inventory import classify_marker_trends

    coverage = classify_marker_trends(message, context.markers, context.comparisons)
    return bool(coverage["supported"]) and not coverage["incompatible_units"]


def _stored_fact_lines(context: HealthContext) -> list[str]:
    lines = []
    for marker in context.markers or []:
        if getattr(marker, "value", None) is None:
            continue
        when = getattr(marker, "measured_at", None)
        day = when.isoformat()[:10] if hasattr(when, "isoformat") else (str(when)[:10] if when else "")
        unit = getattr(marker, "unit", None) or ""
        dated = f" on {day}" if day else ""
        lines.append(f"{marker.name} {marker.value:g} {unit}{dated}".strip())
    for risk in context.bio_ai_risks or []:
        score = getattr(risk, "score", None)
        if score is None:
            continue
        status = getattr(risk, "status", None) or getattr(risk, "band", None) or ""
        lines.append(f"{getattr(risk, 'name', None) or risk.code} {score:g} {status}".strip())
    return lines


def _answer_with_stored_facts(rendered: str, context: HealthContext) -> str:
    text = rendered or ""
    missing = []
    for line in _stored_fact_lines(context):
        token = next((part for part in line.split() if re.fullmatch(r"\d+(?:\.\d+)?", part)), "")
        if token and token not in text:
            missing.append(line)
    if not missing:
        return text
    facts = "Stored records: " + "; ".join(missing) + "."
    if "could not be generated" in text.lower() or not text.strip():
        return facts
    return f"{text.rstrip()}\n\n{facts}"


CROSS_SOURCE_LIMITATION = (
    "A written explanation could not be generated. "
    "The stored measurements shown here are unchanged, and no missing value was estimated."
)


def _whole_report_explained(context: HealthContext) -> bool:
    """True when the renderer's report explainer answers the turn (see report_explainer)."""
    intent = context.intent.value
    if intent == "report_explanation":
        return True
    return intent in {"bio_ai_explanation", "bio_ai_score"} and len(context.bio_ai_risks or []) > 1 and not context.comparisons


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
    fallback_reason: str | None = None


def _privacy_block(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "personal health" in text or "zdr" in text or "privacy" in text


def _is_different_model(current: AnswerModelTier, target: AnswerModelTier) -> bool:
    """Escalating only helps when the target tier is a different model; otherwise it repeats the call."""
    from app.llm.registry import model_id_for_tier

    try:
        return model_id_for_tier(target) != model_id_for_tier(current)
    except Exception:  # noqa: BLE001 - unknown configuration: do not repeat the call
        return False


_EXPLANATION_OPS = {
    "EXPLAIN",
    "INTERPRET",
    "COMPARE",
    "TREND",
    "CORRELATE",
    "PRIORITIZE",
    "IDENTIFY_GAPS",
    "IDENTIFY_PATTERN",
    "RECOMMEND",
    "CONTINUE_INTERPRETATION",
    "PERSONAL_INTERPRETATION",
    "CROSS_SOURCE_ANALYSIS",
}
_EXPLANATION_KINDS = {
    "PERSONAL_RISK_EXPLANATION",
    "PRIORITIZED_CONCERNS",
    "SYMPTOM_CONTEXT",
    "CROSS_SOURCE_EXPLANATION",
}
_LOOKUP_KINDS = {"MARKER_LOOKUP", "BIO_AI_SCORE_LIST"}
_EXPLANATION_INTENTS = {
    IntentType.report_explanation,
    IntentType.blood_marker_explanation,
    IntentType.bio_ai_explanation,
    IntentType.health_scenario,
    IntentType.bio_ai_comparison,
    IntentType.trend,
}


def _eligible_for_model_wording(plan: QueryPlan, context: HealthContext) -> bool:
    """Ordinary questions with verified facts can be worded by the approved model."""
    if not settings.enable_llm or context.status == "ambiguous":
        return False
    if not (context.markers or context.bio_ai_risks):
        return False
    if plan.needs_personal_data:
        from app.llm.openrouter_policy import openrouter_policy

        return openrouter_policy().personal_interpretation_permitted()
    return True


def _missing_score_note(message: str, context: HealthContext, answer: str) -> str:
    if not re.search(r"bio-?\s*ai|risk score", message or "", re.I):
        return ""
    missing = []
    for risk in context.bio_ai_risks or []:
        score = getattr(risk, "score", None)
        if score is None:
            continue
        token = f"{score:g}"
        if token not in (answer or ""):
            name = getattr(risk, "name", None) or risk.code
            status = getattr(risk, "status", None) or ""
            missing.append(f"{name} {token} ({status})".strip())
    if not missing:
        return ""
    return "Stored scores: " + "; ".join(missing) + ". These are risk estimates, not diagnoses."


def _model_explains(plan: QueryPlan) -> bool:
    """An approved model may word the answer. Facts stay in the backend."""
    if not (settings.enable_llm and uses_answer_llm(plan.answer_model_tier)):
        return False
    if plan.needs_personal_data:
        from app.llm.openrouter_policy import openrouter_policy

        return openrouter_policy().personal_interpretation_permitted()
    return True


def _without_clinical_claim(answer: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", (answer or "").strip())
    kept = [part for part in parts if part and not _CLINICAL_CHANGE.search(part)]
    return " ".join(kept).strip()


def explanation_requested(plan: QueryPlan, message: str | None = None) -> bool:
    """True when the planner asked for an interpretation, not a stored value or score."""
    from app.pipeline.response_planner import is_report_level_request

    text = message or plan.raw_message or ""
    if is_report_level_request(text):
        return False
    ops = {str(item).upper() for item in (plan.operations or [])}
    if plan.operation:
        ops.add(str(plan.operation).upper())
    kind = (plan.task_contract or {}).get("response_type")
    if ops & _EXPLANATION_OPS:
        return True
    if kind in _EXPLANATION_KINDS:
        return True
    if kind in _LOOKUP_KINDS:
        return False
    return plan.intent in _EXPLANATION_INTENTS


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
        if _eligible_for_model_wording(plan, context) and not uses_answer_llm(plan.answer_model_tier):
            # A stored lookup still uses the existing fast tier. No new router.
            plan = plan.model_copy(update={
                "answer_model_tier": AnswerModelTier.fast_reasoning,
                "model_tier": AnswerModelTier.fast_reasoning,
            })
        lookup = self._lookup_only(plan, context)
        structured_bio_ai = (
            lookup
            and plan.intent == IntentType.bio_ai_score
            and bool(context.bio_ai_risks)
            and context.status != "ambiguous"
            and not plan.needs_user_uploaded
        )
        explain_bio = bool(re.search(r"\b(explain|interpret|what does|what do|mean|understand|how should i read|relat\w*|compare|together)\b", message or "", re.I))
        from app.routing.model_tier import asks_blood_and_score_relationship

        relationship = asks_blood_and_score_relationship(message or "")
        cross_source = bool(plan.needs_blood and plan.needs_bio_ai and re.search(r"\b(relat\w*|compare|together|fit)\b", message or "", re.I))
        explain = explanation_requested(plan, message) or explain_bio or relationship
        needs_model = explain and (bool(context.bio_ai_risks) or bool(context.markers) or plan.needs_personal_data)
        if needs_model and settings.enable_llm and not uses_answer_llm(plan.answer_model_tier):
            plan = plan.model_copy(update={"answer_model_tier": AnswerModelTier.standard_medical, "model_tier": AnswerModelTier.standard_medical})
        if (
            plan.intent == IntentType.bio_ai_explanation
            and context.bio_ai_risks
            and not settings.enable_llm
        ):
            return ReasoningResult(
                answer=self.renderer.render(message, context),
                llm_called=False,
                llm_mode="structured_bio_ai",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        if structured_bio_ai and not cross_source and not relationship and not _model_explains(plan):
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
        primary = (plan.task_contract or {}).get("primary_source")
        if primary == "blood_report" and not context.markers:
            return ReasoningResult(
                answer=(
                    "I can't access your latest blood report right now, so this isn't an interpretation of your results. "
                    "I can still explain what a blood report usually shows, as general information."
                ),
                llm_called=False,
                llm_mode="primary_source_unavailable",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        if primary == "bio_ai" and not context.bio_ai_risks:
            return ReasoningResult(
                answer=(
                    "I can't access your latest Bio-AI report right now, so this isn't an interpretation of your risk estimates. "
                    "I can still explain what those assessments mean in general."
                ),
                llm_called=False,
                llm_mode="primary_source_unavailable",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        response_plan = build_response_plan(message, plan, context)
        interpret_turn = "INTERPRET" in {str(op).upper() for op in plan.operations or []}
        if response_plan.kind == "report_overview" and context.markers and not interpret_turn and not explain and not _model_explains(plan):
            highlights = [
                m for m in context.markers
                if getattr(m.flag, "value", str(m.flag)) in {"low", "high", "critical"}
            ]
            detail = ""
            if highlights:
                names = ", ".join(m.name for m in highlights[:3])
                detail = f" A few results worth reviewing first are {names}."
            counts = context.in_range_summary
            if counts and (counts.in_range or counts.out_of_range):
                total = counts.in_range + counts.out_of_range + counts.missing + counts.unclassified
                detail = (
                    f" The report has {total} results, {counts.out_of_range} outside the reference range."
                    + detail
                )
            return ReasoningResult(
                answer=f"{response_plan.direct_answer} {response_plan.summary}{detail}".strip(),
                llm_mode="structured_report_overview",
            )
        if (plan.task_contract or {}).get("response_type") == "ABNORMAL_LIST" and context.markers and not explain and not _model_explains(plan):
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
            and not explain
            and plan.intent in {IntentType.latest_result, IntentType.previous_result}
            and plan.needs_blood
            and context.markers
            and context.status != "ambiguous"
            and not plan.needs_user_uploaded
            and not plan.needs_cross_source
            and not _model_explains(plan)
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
            reviewed_definition = bool(
                corpus_answer and definition_from_reviewed_passage(message, plan, medical_hits)
            )
            if reviewed_definition and not settings.enable_llm:
                # A reviewed passage answers a plain definition only when no model is available.
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
            except LLMUnavailableError as exc:
                if reviewed_definition:
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
                    fallback_reason="privacy" if _privacy_block(exc) else "model_unavailable",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        facts_ready = bool(context.markers or context.bio_ai_risks)
        if settings.enable_llm and uses_answer_llm(plan.answer_model_tier) and (
            plan_needs_reasoning(plan) or not lookup or relationship or explain or facts_ready
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
                from app.pipeline.evidence_inventory import (
                    authoritative_measurement_answer,
                    contradicting_answer,
                    omitted_supported_facts,
                    render_partial_trend,
                )

                verified = render_partial_trend(message, context.markers, context.comparisons)
                asks_change = bool(re.search(r"\b(improved|improvement|changed|change|compared)\b", message or "", re.I))
                deflects = bool(re.search(r"\bwould you like\b", answer or "", re.I))
                repaired = False
                if verified and asks_change and (_CLINICAL_CHANGE.search(answer or "") or deflects):
                    kept = _without_clinical_claim(answer or "")
                    if kept and not deflects:
                        answer = kept
                    else:
                        answer = verified
                        repaired = True
                elif contradicting_answer(message, context.markers, answer, context.comparisons) or _false_unit_mismatch(
                    message, context, answer
                ):
                    replacement = authoritative_measurement_answer(message, context.markers, context.comparisons)
                    if replacement:
                        answer = replacement
                        repaired = True
                omitted = omitted_supported_facts(message, context.markers, answer, context.comparisons)
                score_note = _missing_score_note(message, context, answer)
                if score_note:
                    omitted = f"{omitted}\n\n{score_note}".strip() if omitted else score_note
                if omitted:
                    answer = f"{answer.rstrip()}\n\n{omitted}"
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
                    flags=["verified_fallback"] if repaired else [],
                )
            except LLMUnavailableError as exc:
                logger.warning("llm_unavailable tier=%s", plan.answer_model_tier.value if plan.answer_model_tier else None)
                privacy = _privacy_block(exc)
                from app.pipeline.evidence_inventory import classify_marker_trends, render_partial_trend

                coverage = classify_marker_trends(message, context.markers, context.comparisons)
                partial = render_partial_trend(message, context.markers, context.comparisons) if coverage["support"] in {"partial", "full"} else None
                if partial:
                    return ReasoningResult(
                        answer=partial,
                        llm_called=False,
                        llm_mode="deterministic_fallback",
                        fallback_reason="privacy" if privacy else "model_unavailable",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                if _whole_report_explained(context):
                    # The deterministic explainer already covers every flagged result.
                    return ReasoningResult(
                        answer=self.renderer.render(message, context),
                        llm_called=False,
                        llm_mode="deterministic_fallback",
                        fallback_reason="privacy" if privacy else "model_unavailable",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                if plan.answer_model_tier == AnswerModelTier.deep_medical_reasoning:
                    # Stored facts stay. The model does not invent a link between them.
                    rendered = _answer_with_stored_facts(self.renderer.render(message, context), context)
                    answer = CROSS_SOURCE_LIMITATION
                    if rendered:
                        answer = f"{rendered}\n\n{CROSS_SOURCE_LIMITATION}"
                    return ReasoningResult(
                        answer=answer,
                        llm_called=False,
                        llm_mode="deterministic_fallback",
                        fallback_reason="privacy" if privacy else "model_unavailable",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                return ReasoningResult(
                    answer=_answer_with_stored_facts(self.renderer.render(message, context), context),
                    llm_called=False,
                    llm_mode="deterministic_fallback",
                    fallback_reason="privacy" if privacy else "model_unavailable",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        from app.llm.openrouter_policy import openrouter_policy

        privacy = bool(plan.needs_personal_data) and not openrouter_policy().personal_interpretation_permitted()
        return ReasoningResult(
            answer=self.renderer.render(message, context),
            llm_called=False,
            llm_mode="deterministic_fallback" if privacy else "deterministic",
            fallback_reason="privacy" if privacy else None,
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
