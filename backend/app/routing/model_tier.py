"""Map Jev capability onto a provider-independent model tier.

Jev chooses DETERMINISTIC | FAST_REASONING | STANDARD_MEDICAL | DEEP_MEDICAL_REASONING.
CURA maps those tiers to models. Jev must not name providers or model IDs.
"""

from __future__ import annotations

import re

from app.contracts.common import (
    AnswerComplexity,
    AnswerModelTier,
    IntentType,
    ReasoningDepth,
    parse_model_tier,
)
from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import match_lab_keys
from app.pipeline.operations import named_personal_sources
from app.routing.schemas import JevDecision

_RANK = {
    AnswerModelTier.deterministic: 0,
    AnswerModelTier.fast_reasoning: 1,
    AnswerModelTier.standard_medical: 2,
    AnswerModelTier.deep_medical_reasoning: 3,
}
_LIST_ONLY = re.compile(
    r"\b(list only|just list|only list|without (?:an |any )?(?:explanation|interpretation)|"
    r"just (?:the |my )?results|show (?:me )?(?:only )?(?:the )?values?|"
    r"show (?:all )?(?:my )?(?:high|low|abnormal) (?:markers?|results?|values?)|"
    r"list (?:all )?(?:my )?(?:high|low|abnormal) (?:markers?|results?|values?)|"
    r"which markers are (?:high|low|abnormal|normal)"
    r")\b",
    re.I,
)
_INTERPRET = re.compile(
    r"\b("
    r"what does|what could|mean|why|"
    r"explain|interpret|how is|how are|"
    r"how should i read|read my|"
    r"analyze|analyse|review|summarize|summarise|"
    r"should i (?:focus|worry)|related|connected|pattern|"
    r"overall|together|consistent"
    r")\b",
    re.I,
)
_UNCERTAINTY = re.compile(
    r"\b("
    r"contradict|conflict|doesn't match|does not match|"
    r"several (?:possible )?explanations|differential|"
    r"what might explain|balance|uncertain|missing information"
    r")\b",
    re.I,
)
_SCENARIO = re.compile(
    r"\b(health scenario|complete health|overall health|bigger-picture|comprehensive overview)\b",
    re.I,
)
_RELATED = re.compile(r"\b(related|connected|in common|cluster|pattern|group)\b", re.I)
_ORGAN_REVIEW = re.compile(
    r"\b(?:how (?:is|are|does)|read on|look(?:ing)? at).{0,40}\b(?:liver|kidney|thyroid)\b|"
    r"\b(?:liver|kidney|thyroid)\s+(?:function|results?|markers?|numbers?)\b",
    re.I,
)


def apply_answer_model_routing(
    plan: QueryPlan,
    *,
    decision: JevDecision | None = None,
    jev_fallback: bool = False,
) -> QueryPlan:
    inferred = infer_answer_model_routing(plan)
    selected = inferred.tier
    complexity = inferred.complexity
    depth = inferred.reasoning_depth
    reasons = list(inferred.reasons)
    pdf_analysis = inferred.pdf_analysis
    reasoning = inferred.reasoning
    if decision and not jev_fallback:
        if decision.reasoning_required:
            reasoning = True
        if decision.pdf_analysis_required:
            pdf_analysis = True
        jev_tier = parse_model_tier(decision.answer_model_tier) if decision.answer_model_tier else None
        if jev_tier:
            selected = jev_tier
            if _RANK[inferred.tier] >= _RANK[AnswerModelTier.deep_medical_reasoning] and _RANK[selected] < _RANK[
                AnswerModelTier.standard_medical
            ]:
                selected = inferred.tier
                reasons.append("inferred_complexity_prevented_under_routing")
            else:
                reasons.append("jev_selected_tier")
        elif decision.complexity:
            selected = {
                AnswerComplexity.low: AnswerModelTier.deterministic,
                AnswerComplexity.medium: AnswerModelTier.standard_medical,
                AnswerComplexity.high: AnswerModelTier.deep_medical_reasoning,
            }[decision.complexity]
            if _RANK[inferred.tier] >= _RANK[AnswerModelTier.deep_medical_reasoning] and selected == AnswerModelTier.deterministic:
                selected = inferred.tier
                reasons.append("inferred_complexity_prevented_under_routing")
            else:
                reasons.append("jev_complexity_mapped_to_tier")
        if decision.complexity:
            complexity = decision.complexity
        if getattr(decision, "reasoning_depth", None):
            depth = decision.reasoning_depth
    selected, depth, extra = _constrain_tier(plan, selected, depth, reasoning)
    reasons.extend(extra)
    if selected == AnswerModelTier.deep_medical_reasoning:
        complexity = AnswerComplexity.high
        depth = ReasoningDepth.deep
    elif selected == AnswerModelTier.standard_medical:
        complexity = complexity or AnswerComplexity.medium
        depth = depth or ReasoningDepth.standard
    elif selected == AnswerModelTier.fast_reasoning:
        complexity = complexity or AnswerComplexity.low
        depth = depth or ReasoningDepth.none
    else:
        complexity = AnswerComplexity.low
        depth = ReasoningDepth.none
    plan.answer_model_tier = selected
    plan.model_tier = selected
    plan.complexity = complexity
    plan.reasoning_depth = depth
    plan.model_selection_reasons = list(dict.fromkeys(reasons))
    plan.reasoning_required = reasoning or uses_medical_answer_llm(selected)
    plan.pdf_analysis_required = pdf_analysis
    return plan


class _Inference:
    __slots__ = ("complexity", "tier", "reasoning", "pdf_analysis", "reasoning_depth", "reasons")

    def __init__(self, complexity, tier, reasoning, pdf_analysis, reasoning_depth, reasons):
        self.complexity = complexity
        self.tier = tier
        self.reasoning = reasoning
        self.pdf_analysis = pdf_analysis
        self.reasoning_depth = reasoning_depth
        self.reasons = reasons


def infer_answer_model_routing(plan: QueryPlan) -> _Inference:
    message = plan.raw_message or ""
    mentioned = list(dict.fromkeys(match_lab_keys(message)))
    domains = list(plan.domains or [])
    domain_count = len(domains)
    named_sources = named_personal_sources(message)
    source_count = len(named_sources) or (1 if plan.needs_personal_data else 0)
    ops = {str(item).upper() for item in (plan.operations or [])}
    if plan.operation:
        ops.add(plan.operation.upper())
    selectors = {str(item).upper() for item in (plan.selectors or [])}
    metric_count = len(mentioned)
    if metric_count == 0 and plan.topic and plan.topic not in domains:
        metric_count = 1
    if metric_count == 0 and domain_count:
        metric_count = 1
    pdf_analysis = bool(
        plan.needs_user_uploaded
        and (
            _SCENARIO.search(message)
            or re.search(r"\b(analyze|analyse|review|summarize|summarise|interpret)\b", message, re.I)
        )
    )
    text_interpret = bool(
        _INTERPRET.search(message)
        or _ORGAN_REVIEW.search(message)
        or plan.needs_guidance
        or plan.intent
        in {
            IntentType.blood_marker_explanation,
            IntentType.bio_ai_explanation,
            IntentType.nutrition_guidance,
            IntentType.report_explanation,
        }
    )
    related = bool(_RELATED.search(message) or "RELATED" in selectors or "IDENTIFY_PATTERN" in ops or "CORRELATE" in ops or "GROUP" in ops)
    list_only = bool(
        _LIST_ONLY.search(message)
        or (selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and not text_interpret and not related)
    )
    interpret = bool(
        text_interpret
        or plan.medical_evidence_required
        or (ops & _REASONING_OPS and not list_only)
        or (plan.knowledge_scope.value == "general" and plan.intent == IntentType.general_health_question)
    )
    history = bool(
        plan.history
        or plan.compare
        or "TREND" in ops
        or "COMPARE" in ops
        or "HISTORICAL" in selectors
        or re.search(r"\b(over time|trend|previous|history|last three|changed)\b", message, re.I)
    )
    cross = bool(plan.needs_cross_source or len(named_sources) >= 2)
    recommend = bool(plan.needs_guidance or "RECOMMEND" in ops)
    scenario = bool(_SCENARIO.search(message) or plan.intent == IntentType.health_scenario)
    if plan.intent == IntentType.broad_health_summary and (len(named_sources) >= 2 or _SCENARIO.search(message)):
        scenario = True
    uncertainty = bool(_UNCERTAINTY.search(message) or "IDENTIFY_GAPS" in ops)
    conversation = bool(plan.conversation_turn and plan.conversation_turn not in {"NEW_QUESTION", None})

    reasons: list[str] = []
    score = 0
    if mentioned:
        score += min(len(mentioned), 4)
        reasons.append(f"entities:{len(mentioned)}")
    elif metric_count:
        score += 1
        reasons.append(f"entities:{metric_count}")
    if domain_count:
        score += 2 * max(0, domain_count - 1)
        reasons.append(f"domains:{domain_count}")
    if source_count:
        score += 2 * max(0, source_count - 1)
        reasons.append(f"sources:{source_count}")
    reasoning_ops = ops & _REASONING_OPS
    if reasoning_ops and not list_only:
        score += min(3, len(reasoning_ops))
        reasons.append("reasoning_operations")
    if history:
        score += 2
        reasons.append("historical_comparison")
    if cross:
        score += 3
        reasons.append("cross_source_reasoning")
    if related:
        score += 2
        reasons.append("related_findings")
    if recommend:
        score += 2
        reasons.append("personalized_recommendations")
    if uncertainty:
        score += 3
        reasons.append("substantial_uncertainty")
    if conversation and interpret:
        score += 1
        reasons.append("conversation_state_resolution")
    if pdf_analysis:
        score += 3
        reasons.append("uploaded_report_analysis")
    if scenario:
        score += 5
        reasons.append("complete_health_synthesis")

    lookup_only = _lookup_only(plan, interpret, list_only, metric_count, ops)
    if lookup_only and not scenario:
        reasons.append("deterministic_retrieval")
        return _Inference(
            AnswerComplexity.low,
            AnswerModelTier.deterministic,
            False,
            False,
            ReasoningDepth.none,
            reasons,
        )
    deep = bool(
        scenario
        or pdf_analysis
        or (domain_count >= 2 and (history or cross or related or uncertainty))
        or (len(mentioned) >= 3 and (history or related or uncertainty or cross))
        or (cross and (related or uncertainty or history))
        or (score >= 8 and (domain_count >= 2 or cross or related or uncertainty or history))
    )
    if deep:
        reasons.append("deep_medical_complexity")
        return _Inference(
            AnswerComplexity.high,
            AnswerModelTier.deep_medical_reasoning,
            True,
            pdf_analysis,
            ReasoningDepth.deep,
            reasons,
        )
    reasons.append("standard_medical_default")
    return _Inference(
        AnswerComplexity.medium,
        AnswerModelTier.standard_medical,
        True,
        pdf_analysis,
        ReasoningDepth.standard,
        reasons,
    )


def uses_medical_answer_llm(tier: AnswerModelTier | str | None) -> bool:
    parsed = parse_model_tier(tier) if not isinstance(tier, AnswerModelTier) else tier
    return parsed in {AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning}


_REASONING_OPS = {
    "EXPLAIN",
    "INTERPRET",
    "PERSONAL_INTERPRETATION",
    "SUMMARIZE",
    "CORRELATE",
    "GROUP",
    "PRIORITIZE",
    "IDENTIFY_GAPS",
    "IDENTIFY_PATTERN",
    "RECOMMEND",
    "CONTINUE_INTERPRETATION",
    "ASSESS_GOAL_PROGRESS",
    "PREPARE_CLINICIAN_DISCUSSION",
    "UPDATE_CONTEXT",
    "DOCUMENT_NARRATIVE_RETRIEVAL",
    "DOCUMENT_SUMMARY",
    "DOCUMENT_CROSS_SOURCE_COMPARE",
}


def _lookup_only(plan: QueryPlan, interpret: bool, list_only: bool, metric_count: int, ops: set[str]) -> bool:
    if plan.knowledge_scope.value == "general" and plan.intent != IntentType.casual_conversation:
        return False
    if interpret and not list_only:
        return False
    if ops & (_REASONING_OPS - {"TREND", "COMPARE"}):
        if not list_only:
            return False
    if list_only:
        return True
    if plan.intent in {IntentType.latest_result, IntentType.previous_result, IntentType.missing_data} and metric_count <= 2:
        if "TREND" in ops or "COMPARE" in ops:
            return not interpret
        return True
    if plan.intent == IntentType.trend and not interpret:
        return True
    if plan.intent == IntentType.casual_conversation:
        return True
    if plan.intent == IntentType.bio_ai_score and not interpret and metric_count <= 1:
        return True
    return False


def _constrain_tier(
    plan: QueryPlan,
    selected: AnswerModelTier,
    depth: ReasoningDepth,
    reasoning: bool,
) -> tuple[AnswerModelTier, ReasoningDepth, list[str]]:
    extra: list[str] = []
    if selected == AnswerModelTier.fast_reasoning and reasoning:
        selected = AnswerModelTier.standard_medical
        depth = ReasoningDepth.standard
        extra.append("fast_reasoning_not_used_for_medical_answers")
    if selected == AnswerModelTier.deterministic and reasoning and plan.knowledge_scope.value == "general":
        selected = AnswerModelTier.standard_medical
        depth = ReasoningDepth.standard
        extra.append("general_explanation_requires_standard_medical")
    if selected == AnswerModelTier.deterministic and reasoning and plan.intent in {
        IntentType.blood_marker_explanation,
        IntentType.bio_ai_explanation,
        IntentType.nutrition_guidance,
        IntentType.report_explanation,
        IntentType.health_scenario,
    }:
        selected = AnswerModelTier.standard_medical if plan.intent != IntentType.health_scenario else AnswerModelTier.deep_medical_reasoning
        depth = ReasoningDepth.deep if selected == AnswerModelTier.deep_medical_reasoning else ReasoningDepth.standard
        extra.append("interpretation_promoted_from_deterministic")
    return selected, depth, extra


def promote_for_retrieved_complexity(plan: QueryPlan, context) -> QueryPlan:
    """Promote clearly complex personal-health turns before the first answer-model call.

    Initial routing happens before retrieval. Once trusted context is available we can see
    conflicts, breadth and cross-source density that were impossible to know at route time.
    Promoting here avoids paying for STANDARD_MEDICAL and then a second DEEP call.
    """
    if plan.answer_model_tier != AnswerModelTier.standard_medical:
        return plan

    ops = {str(item).upper() for item in (plan.operations or [])}
    if plan.operation:
        ops.add(plan.operation.upper())
    marker_count = len(getattr(context, "markers", None) or [])
    risk_count = len(getattr(context, "bio_ai_risks", None) or [])
    domain_count = len(plan.domains or [])
    conflicts = len(getattr(context, "source_conflicts", None) or [])
    comparisons = len(getattr(context, "comparisons", None) or [])

    reason = None
    if conflicts:
        reason = "retrieved_source_conflict"
    elif plan.needs_cross_source and (comparisons or marker_count + risk_count >= 3):
        reason = "retrieved_cross_source_complexity"
    elif plan.intent in {IntentType.health_scenario, IntentType.broad_health_summary} and marker_count + risk_count >= 5:
        reason = "retrieved_whole_health_breadth"
    elif domain_count >= 2 and marker_count + risk_count >= 4:
        reason = "retrieved_multi_domain_breadth"
    elif ops & {"CORRELATE", "IDENTIFY_PATTERN", "IDENTIFY_GAPS", "PRIORITIZE"} and marker_count + risk_count >= 4:
        reason = "retrieved_reasoning_breadth"

    if not reason:
        return plan
    plan.answer_model_tier = AnswerModelTier.deep_medical_reasoning
    plan.model_tier = AnswerModelTier.deep_medical_reasoning
    plan.complexity = AnswerComplexity.high
    plan.reasoning_depth = ReasoningDepth.deep
    plan.reasoning_required = True
    plan.model_selection_reasons = list(dict.fromkeys([*(plan.model_selection_reasons or []), reason, "pre_generation_deep_promotion"]))
    return plan
