"""Question-fulfillment checks. Failures stay internal; the user sees a repaired answer."""

from __future__ import annotations

import re

from app.contracts.common import AnswerModelTier
from app.contracts.health_context import HealthContext
from app.contracts.operations import QualityGateResult
from app.contracts.query import QueryPlan
from app.pipeline.operations import AnswerOperation

_BACKEND = re.compile(
    r"(I had trouble formatting that answer|parse_error|Traceback|LLMUnavailable|"
    r"json_schema|recommendation_candidates|\"claims\")",
    re.I,
)
_GENERIC = re.compile(
    r"\b(it depends|in general|many people|typically|as a whole|overall health is (?:good|fine))\b",
    re.I,
)
# A second answer call costs a full model round trip, so only failures a stronger model
# can actually fix trigger one: unreconciled findings across sources, or no usable output.
# Wording issues (a marker not named, generic phrasing) are handled by the validator.
_ESCALATE_FLAGS = {
    "contradictions_unaddressed",
    "backend_leak",
    "structured_output_failed",
}


def review_answer(answer: str, plan: QueryPlan, context: HealthContext) -> QualityGateResult:
    flags: list[str] = []
    text = answer or ""
    if _BACKEND.search(text) or (text.strip().startswith("{") and "answer" in text):
        flags.append("backend_leak")
    operation = (plan.operation or "").upper()
    ops = {str(item).upper() for item in (plan.operations or [])}
    ops.add(operation)
    if "TREND" in ops or "VERIFY_PREMISE" in ops:
        if context.comparisons:
            if not any(str(item.previous_date or "") and str(item.current_date or "") for item in context.comparisons):
                flags.append("trend_missing_dates")
            if not any(item.direction for item in context.comparisons):
                flags.append("trend_missing_direction")
        elif not any("did not" in text.lower() or "no change" in text.lower() or "unchanged" in text.lower() for _ in [0]):
            if context.premise_verified is False:
                pass
            elif not re.search(r"\b(increased|decreased|unchanged|did not|no (?:change|trend))\b", text, re.I):
                flags.append("trend_unfulfilled")
    if operation == AnswerOperation.recommend.value and plan.requested_count:
        listed = len(re.findall(r"(?:^|\n)\s*(?:\d+[\.\)]|[\-•])\s+\S", text))
        if listed < plan.requested_count and not _count_sentences(text, plan.requested_count):
            flags.append("count_unfulfilled")
    if operation == AnswerOperation.provenance.value:
        if not re.search(r"\b(report|blood-|\d{4}-\d{2}-\d{2}|source)\b", text, re.I):
            flags.append("provenance_unfulfilled")
    named = {item.split(":")[0] for item in (plan.data_sources or [])}
    if len(named) >= 2:
        mentioned = 0
        blob = text.lower()
        for token in ("blood", "bio-ai", "bio ai", "questionnaire", "goal"):
            if token in blob:
                mentioned += 1
        missing_outcomes = [
            row
            for row in (context.source_outcomes or [])
            if getattr(row, "status", None) and str(getattr(row.status, "value", row.status)) in {"empty", "unavailable"}
        ]
        if mentioned < 1 and missing_outcomes:
            flags.append("multi_source_gap_undisclosed")
    if plan.needs_personal_data and (context.markers or context.bio_ai_risks):
        has_number = bool(re.search(r"\d", text))
        has_marker = any(
            (m.name or m.key or "").lower() in text.lower()
            for m in (context.markers or [])[:8]
        )
        if not has_number and not has_marker and _GENERIC.search(text) and len(text) > 80:
            flags.append("generic_despite_personal")
    wanted = [str(item).lower() for item in (plan.display_entities or plan.requested_metrics or []) if item]
    if wanted and len(text) > 40:
        blob = text.lower()
        hits = sum(1 for item in wanted if item in blob)
        if hits == 0 and not re.search(r"\b(not available|not present|couldn't find|not found)\b", text, re.I):
            flags.append("entity_unmentioned")
    if (context.source_conflicts or []) and not re.search(r"\b(conflict|differ|disagrees?|does not match|contradict)\b", text, re.I):
        flags.append("contradictions_unaddressed")
    ops = {str(item).upper() for item in (plan.operations or [])}
    if ops & {"CORRELATE", "IDENTIFY_PATTERN", "GROUP"} and not re.search(
        r"\b(related|pattern|together|connected|cluster)\b", text, re.I
    ):
        flags.append("reasoning_incomplete")
    contract = plan.task_contract or {}
    response_type = contract.get("response_type")
    if response_type == "BIO_AI_SCORE_LIST" and context.bio_ai_risks:
        named = sum(1 for risk in context.bio_ai_risks if (risk.name or "") and (risk.name or "").lower() in text.lower())
        if named == 0 and re.search(r"\b(not available|unavailable|couldn't find)\b", text, re.I):
            flags.append("bio_ai_scores_denied")
    if response_type == "ABNORMAL_LIST" and context.markers and re.search(r"\b(upload)\b", text, re.I):
        flags.append("blood_report_denied")
    flags.extend(_evidence_obligation_flags(text, response_type, context))
    from app.pipeline.numeric_grounding import unsupported_adjacent_numbers

    flags.extend(unsupported_adjacent_numbers(text, getattr(context, "evidence_package", None)))
    return QualityGateResult(passed=not flags, flags=flags)


def _evidence_obligation_flags(text: str, response_type: str | None, context: HealthContext) -> list[str]:
    """Checks against the normalized package. Skipped when that package was not built."""
    package = getattr(context, "evidence_package", None) or {}
    if not package:
        return []
    flags: list[str] = []
    blob = (text or "").lower()
    risks = package.get("bio_ai_risks") or []
    measurements = package.get("measurements") or []
    missing = {row.get("source"): row.get("status") for row in (package.get("missing") or [])}
    if response_type == "BIO_AI_SCORE_LIST" and risks:
        named = [row for row in risks if (row.get("name") or "").lower() in blob]
        if not named:
            flags.append("requested_score_omitted")
    if response_type == "ABNORMAL_LIST" and measurements:
        named = [row for row in measurements if (row.get("name") or "").lower() in blob]
        if not named:
            flags.append("requested_measurement_omitted")
    for source, status in missing.items():
        if status in {"NOT_PRESENT", "NOT_RETRIEVED", "RETRIEVAL_FAILED"} and re.search(
            r"\b(your (?:latest|blood|bio-ai).{0,40}(?:is|shows|score))\b", text or "", re.I
        ):
            flags.append("unavailable_source_claimed")
            break
    known: set[float] = set()
    for row in measurements + risks:
        value = row.get("value", row.get("score"))
        if isinstance(value, (int, float)):
            known.add(float(value))
    if known and response_type in {"BIO_AI_SCORE_LIST", "ABNORMAL_LIST", "PERSONAL_RISK_EXPLANATION"}:
        for raw in re.findall(r"\b\d+(?:\.\d+)?\b", text or ""):
            number = float(raw)
            if number in {1, 2, 3} or number >= 1900:
                continue
            if not any(abs(number - item) < 0.05 for item in known):
                flags.append("unsupported_number")
                break
    return flags


def should_escalate_to_deep(flags: list[str], plan: QueryPlan, context: HealthContext, answer: str, llm_result=None) -> bool:
    if plan.answer_model_tier not in {AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical}:
        return False
    reasons = set(flags or [])
    if llm_result is not None and getattr(llm_result, "parse_error", None):
        reasons.add("structured_output_failed")
    return bool(reasons & _ESCALATE_FLAGS)


def _count_sentences(text: str, needed: int) -> bool:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    return len(parts) >= needed
