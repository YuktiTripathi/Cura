"""Adaptive answer plan: what an answer should contain, chosen before the model writes it.

Standardize the quality of answers, not their structure. The plan is built by rules from signals
the pipeline already computes (intent, conversation turn, evidence, ranges). It carries no values and
no report text, so it is safe to log. The model call, the evidence and every validator are unchanged;
the plan only says which parts the answer needs and which it must leave out.

Modes (settings.answer_plan_mode): "off" does nothing, "shadow" builds and logs the plan only,
"on" also gives the model the plan.
"""

from __future__ import annotations

import logging
import re
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("cura.answer_plan")

SCHEMA_VERSION = 1


class PlanIntent(str, Enum):
    education = "education"
    lookup = "lookup"
    out_of_range_list = "out_of_range_list"
    personal_interpretation = "personal_interpretation"
    cause = "cause"
    risk_explanation = "risk_explanation"
    trend = "trend"
    action = "action"
    follow_up = "follow_up"
    general = "general"


class Component(str, Enum):
    simple_explanation = "simple_explanation"
    personal_finding = "personal_finding"
    reference_comparison = "reference_comparison"
    mechanism = "mechanism"
    contributors = "contributors"
    implications = "implications"
    trend = "trend"
    next_steps = "next_steps"
    escalation = "escalation"


class Proportion(str, Enum):
    unknown = "unknown"
    within_range = "within_range"
    minor = "minor"
    moderate = "moderate"
    marked = "marked"


class AnswerPlan(BaseModel):
    schema_version: int = SCHEMA_VERSION
    intent: PlanIntent = PlanIntent.general
    follow_up: bool = False
    education_required: bool = False
    personal_data_required: bool = False
    components: list[Component] = Field(default_factory=list)
    detail_level: str = "concise"
    answer_length_target_words: int = 110
    required_evidence: list[str] = Field(default_factory=list)
    available_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    already_explained: list[str] = Field(default_factory=list)
    proportion: Proportion = Proportion.unknown
    focus_marker: str | None = None
    requested_points: int | None = None
    must_not_claim: list[str] = Field(default_factory=lambda: ["confirmed_diagnosis_without_diagnostic_evidence"])


ACTION_OR_FOOD = re.compile(
    r"\b(?:foods?|meals?|diet|eat|eating|recipes?|snacks?|how (?:can|do|should) i|what should i (?:do|eat|try)|"
    r"improve|raise|lower|increase|reduce|boost|fix|recheck|retest|repeat the)\b",
    re.I,
)
_IMPORTANCE = re.compile(r"\b(?:why (?:is|are|does|do) .{0,40}(?:important|matter)|what is .{0,30} for)\b", re.I)
_CAUSE = re.compile(r"\b(?:why|cause[sd]?|reason|what could explain|how come)\b", re.I)
_CHANGE = re.compile(r"\b(?:chang\w*|improv\w*|worse\w*|better|trend\w*|since|previous\w*|earlier|last (?:report|time|result)|compared? (?:it |this |that )?(?:to|with) (?:last|previous|earlier|before)|progress\w*|over time|going (?:up|down))\b", re.I)
_POINTS = re.compile(r"\b(?:in|into|as|with|using)\s+(\d|one|two|three|four|five)\s+(?:short\s+)?(?:points?|bullets?|lines?|sentences?)\b", re.I)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_OUT_OF_RANGE = re.compile(r"\b(?:out of range|outside (?:the |my )?(?:normal )?range|abnormal|which .{0,30}\b(?:high|low|off)\b)", re.I)
_FOLLOW_UP_TURNS = {"FOLLOW_UP_QUESTION", "REFERENCE_RESOLUTION", "CLARIFICATION", "CONFIRMATION", "CORRECTION"}
_WASTE_MARKERS = {"urea", "bun", "blood_urea_nitrogen", "creatinine", "uric_acid", "bilirubin"}

# Canonical order of the parts of an answer. A plan names which parts apply, never a new order.
ORDER = [
    Component.simple_explanation,
    Component.personal_finding,
    Component.reference_comparison,
    Component.mechanism,
    Component.contributors,
    Component.trend,
    Component.implications,
    Component.next_steps,
    Component.escalation,
]
_PART_TEXT = {
    Component.simple_explanation: "what the test or term is, in everyday words",
    Component.personal_finding: "the person's own value in bold with its unit, and the range on the report",
    Component.reference_comparison: "how far outside the range it is and what a gap of that size usually means",
    Component.mechanism: "two or three common reasons that can push this result this way, as possibilities, never a cause or a diagnosis",
    Component.contributors: "only the contributors that are actually in the report",
    Component.trend: "the change since the earlier result, with both dates",
    Component.implications: "whether to worry, calmly and honestly, with the reason",
    Component.next_steps: "one small specific next step, with an everyday Indian food or habit when it fits",
    Component.escalation: "how soon to see a doctor and which result to show",
}


def _flag(marker) -> str:
    flag = getattr(marker, "flag", None)
    return str(getattr(flag, "value", flag) or "").lower()


def _gap(marker) -> Proportion:
    """How far a value sits outside its range, as a share of the nearest limit. No value leaves the function."""
    value = getattr(marker, "value", None)
    low = getattr(marker, "reference_low", None)
    high = getattr(marker, "reference_high", None)
    if value is None or (low is None and high is None):
        return Proportion.unknown
    try:
        if high is not None and value > high and high:
            share = (value - high) / abs(high)
        elif low is not None and value < low and low:
            share = (low - value) / abs(low)
        else:
            return Proportion.within_range
    except (TypeError, ZeroDivisionError):
        return Proportion.unknown
    if share <= 0.10:
        return Proportion.minor
    if share <= 0.30:
        return Proportion.moderate
    return Proportion.marked


def _focus(context, message: str):
    markers = [m for m in (getattr(context, "markers", None) or []) if getattr(m, "value", None) is not None]
    if not markers:
        return None
    low = (message or "").lower()
    named = [m for m in markers if (m.name or "").lower() in low or (m.key or "").lower().replace("_", " ") in low]
    if len(named) == 1:
        return named[0]
    return markers[0] if len(markers) == 1 else None


def build_answer_plan(context, message: str) -> AnswerPlan:
    contract = getattr(context, "task_contract", None) or {}
    kind = str(contract.get("response_type") or "")
    intent_value = getattr(getattr(context, "intent", None), "value", "") or ""
    turn = str(getattr(context, "conversation_turn", None) or "")
    follow_up = turn in _FOLLOW_UP_TURNS
    rewriting = bool(getattr(context, "rewrite_previous_answer", None))
    explained = [str(x) for x in dict.fromkeys([*(getattr(context, "facts_already_explained", None) or []), *(getattr(context, "explained_entities", None) or [])])][:6]
    markers = list(getattr(context, "markers", None) or [])
    risks = list(getattr(context, "bio_ai_risks", None) or [])
    focus = _focus(context, message)
    proportion = _gap(focus) if focus is not None else Proportion.unknown
    wants_action = bool(ACTION_OR_FOOD.search(message or ""))

    plan = AnswerPlan(follow_up=follow_up and not rewriting, already_explained=[] if rewriting else explained, proportion=proportion)
    points = _POINTS.search(message or "")
    if points:
        raw = points.group(1).lower()
        plan.requested_points = int(raw) if raw.isdigit() else _WORDS.get(raw)
    plan.focus_marker = (focus.name or focus.key) if focus is not None else None

    if intent_value.startswith("bio_ai") or kind in {"PERSONAL_RISK_EXPLANATION", "BIO_AI_SCORE_LIST"}:
        plan.intent = PlanIntent.risk_explanation
        plan.personal_data_required = True
        plan.education_required = True
        parts = [Component.simple_explanation, Component.personal_finding]
        if any(getattr(r, "contributors", None) or getattr(r, "factors", None) for r in risks):
            parts.append(Component.contributors)
        parts += [Component.implications, Component.next_steps]
        plan.detail_level, plan.answer_length_target_words = "standard", 150
        plan.required_evidence = ["bio_ai_score", "score_scale"]
        plan.available_evidence = ["bio_ai_score"] if risks else []
    elif markers and _OUT_OF_RANGE.search(message or "") and not follow_up:
        plan.intent = PlanIntent.out_of_range_list
        plan.personal_data_required = True
        parts = [Component.personal_finding, Component.reference_comparison, Component.next_steps]
        plan.detail_level, plan.answer_length_target_words = "concise", 140
        plan.required_evidence = ["measured_biomarker", "laboratory_reference_interval"]
        plan.available_evidence = list(plan.required_evidence)
    elif wants_action and (markers or follow_up):
        plan.intent = PlanIntent.action if not follow_up else PlanIntent.follow_up
        plan.personal_data_required = bool(markers)
        parts = [Component.next_steps]
        if not follow_up:
            parts = [Component.personal_finding, Component.implications, Component.next_steps]
        plan.detail_level, plan.answer_length_target_words = "concise", 100
    elif _CHANGE.search(message or "") and (getattr(context, "comparisons", None) or contract.get("goal") == "compare"):
        plan.intent = PlanIntent.trend
        plan.personal_data_required = True
        parts = [Component.personal_finding, Component.trend, Component.implications]
        plan.detail_level, plan.answer_length_target_words = "concise", 100
        plan.required_evidence = ["measured_biomarker", "earlier_measurement"]
    elif markers and kind == "MARKER_LOOKUP" and contract.get("goal") == "lookup":
        # "What is my LDL?" is a brief lookup, not an explanation.
        plan.intent = PlanIntent.lookup
        plan.personal_data_required = True
        parts = [Component.personal_finding, Component.reference_comparison]
        if proportion not in {Proportion.within_range, Proportion.unknown}:
            parts.append(Component.next_steps)
        if proportion in {Proportion.moderate, Proportion.marked}:
            parts.append(Component.escalation)
        plan.detail_level, plan.answer_length_target_words = "brief", 70
        plan.required_evidence = ["measured_biomarker", "unit"]
        plan.available_evidence = ["measured_biomarker"]
    elif markers and kind == "MARKER_LOOKUP":
        plan.intent = PlanIntent.cause if _CAUSE.search(message or "") and not _IMPORTANCE.search(message or "") else PlanIntent.personal_interpretation
        plan.personal_data_required = True
        plan.education_required = True
        parts = [Component.simple_explanation, Component.personal_finding]
        if proportion == Proportion.within_range:
            parts += [Component.reference_comparison, Component.next_steps]
            plan.detail_level, plan.answer_length_target_words = "brief", 80
        else:
            parts += [Component.reference_comparison, Component.mechanism, Component.implications, Component.next_steps]
            if proportion in {Proportion.moderate, Proportion.marked}:
                parts.append(Component.escalation)
            plan.detail_level = "brief" if proportion == Proportion.minor else "standard"
            plan.answer_length_target_words = 90 if proportion == Proportion.minor else 150
        plan.required_evidence = ["measured_biomarker", "unit", "laboratory_reference_interval"]
        plan.available_evidence = ["measured_biomarker"] + (["laboratory_reference_interval"] if focus is not None and (focus.reference_low is not None or focus.reference_high is not None) else [])
    elif follow_up:
        asks_why = bool(_CAUSE.search(message or ""))
        plan.intent = PlanIntent.cause if asks_why else PlanIntent.follow_up
        plan.personal_data_required = bool(markers)
        parts = [Component.mechanism, Component.implications, Component.next_steps] if asks_why else [Component.implications, Component.next_steps]
    else:
        plan.intent = PlanIntent.education if not markers else PlanIntent.general
        plan.education_required = True
        parts = [Component.simple_explanation, Component.mechanism, Component.implications]

    if follow_up and explained:
        # Already explained in this chat: do not teach it again.
        teach = {Component.simple_explanation, Component.reference_comparison}
        if plan.intent != PlanIntent.cause:
            teach.add(Component.mechanism)  # a "why" question still needs the reasons
        parts = [c for c in parts if c not in teach]
    if focus is not None and (focus.key or "").lower() in _WASTE_MARKERS:
        plan.must_not_claim.append("goal_to_raise_or_lower_waste_marker")
    plan.components = [c for c in ORDER if c in set(parts)]
    plan.missing_evidence = [e for e in plan.required_evidence if e not in plan.available_evidence]
    return plan


def plan_prompt(plan: AnswerPlan) -> str:
    """Short, non conflicting notes from the plan. It never prescribes an answer shape.

    The model chooses the natural structure for the question. Only things the person asked for (a list of
    results, a number of points) and things already said in this chat shape the reply. Distance from a
    laboratory range is never turned into a severity label or a retest instruction here.
    """
    lines: list[str] = []
    if plan.intent == PlanIntent.out_of_range_list:
        lines.append(
            "The person asked which results are outside their range. List those results, each with its value, unit and the range on the report. "
            "Leave out results inside the range."
        )
    if plan.requested_points:
        lines.append(
            f"The person asked for {plan.requested_points} points. Give exactly {plan.requested_points} points, the most important first."
        )
    if plan.follow_up and plan.already_explained:
        lines.append(
            "Already explained in this chat, so do not explain it again: " + "; ".join(item.replace("_", " ") for item in plan.already_explained)
            + ". Answer only the new question."
        )
    if plan.proportion == Proportion.within_range:
        lines.append("The result is inside its range on the report. Say so plainly.")
    if "goal_to_raise_or_lower_waste_marker" in plan.must_not_claim:
        lines.append("Never suggest raising or lowering this marker as a goal in itself.")
    return " ".join(lines)


def log_plan(plan: AnswerPlan) -> None:
    """Safe metadata only: no values, no report text."""
    logger.info(
        "answer_plan v=%s intent=%s follow_up=%s components=%s detail=%s proportion=%s missing=%s explained=%d",
        plan.schema_version, plan.intent.value, plan.follow_up, ",".join(c.value for c in plan.components),
        plan.detail_level, plan.proportion.value, ",".join(plan.missing_evidence) or "none", len(plan.already_explained),
    )
