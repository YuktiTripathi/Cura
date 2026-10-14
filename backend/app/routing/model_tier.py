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
from app.pipeline.lab_parameters import is_lab_key, match_lab_keys
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


_ROUTINE_FLASH = {
    IntentType.bio_ai_score,
    IntentType.bio_ai_explanation,
    IntentType.nutrition_guidance,
}


def _keep_on_flash(plan: QueryPlan) -> bool:
    """Bio-AI reports and nutrition guidance stay on Gemini. Sonnet is for synthesis."""
    if plan.intent == IntentType.health_scenario or _SCENARIO.search(plan.raw_message or ""):
        return False
    if plan.intent in _ROUTINE_FLASH:
        if _RELATED.search(plan.raw_message or "") or _UNCERTAINTY.search(plan.raw_message or ""):
            return False
        if re.search(r"\b(overall picture|increased|decreased|over time|contradict)\b", plan.raw_message or "", re.I):
            return False
        return True
    text = plan.raw_message or ""
    return bool(re.search(r"\b(bio-?ai report|my nutrition|about my nutrition|what should i eat)\b", text, re.I))


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
        not _keep_on_flash(plan)
        and (
            scenario
            or pdf_analysis
            or (domain_count >= 2 and (history or cross or related or uncertainty))
            or (len(mentioned) >= 3 and (history or related or uncertainty or cross))
            or (cross and (related or uncertainty or history))
            or (score >= 8 and (domain_count >= 2 or cross or related or uncertainty or history))
        )
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
    return parsed in {AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning}


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
    if selected == AnswerModelTier.deep_medical_reasoning and _keep_on_flash(plan):
        selected = AnswerModelTier.standard_medical
        depth = ReasoningDepth.standard
        extra.append("routine_question_stays_on_gemini")
    return selected, depth, extra


def promote_for_retrieved_complexity(plan: QueryPlan, context) -> QueryPlan:
    """Promote one tier before the single answer call when retrieval reveals more than the
    router could see (conflicting sources, cross-source evidence). Never a second call.

    Breadth alone (a whole report read so a lookup can say "this is a minor finding") is
    not complexity: the question decides the tier, not how many rows were fetched.
    """
    tier = plan.answer_model_tier
    if tier not in {AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical}:
        return plan
    if forced_answer_tier() is not None or _keep_on_flash(plan):
        return plan
    marker_count = len(getattr(context, "markers", None) or [])
    risk_count = len(getattr(context, "bio_ai_risks", None) or [])
    conflicts = len(getattr(context, "source_conflicts", None) or [])
    comparisons = len(getattr(context, "comparisons", None) or [])

    reason = None
    if conflicts:
        reason = "retrieved_source_conflict"
    elif tier == AnswerModelTier.standard_medical and plan.needs_cross_source and (comparisons or marker_count + risk_count >= 3) and risk_count:
        reason = "retrieved_cross_source_complexity"
    elif tier == AnswerModelTier.fast_reasoning and plan.needs_cross_source and risk_count and marker_count:
        reason = "retrieved_cross_source_context"
    if not reason:
        return plan
    target = AnswerModelTier.standard_medical if tier == AnswerModelTier.fast_reasoning else AnswerModelTier.deep_medical_reasoning
    promoted = _set_tier(plan, target)
    promoted.initial_answer_tier = plan.initial_answer_tier or tier
    promoted.model_selection_reasons = list(dict.fromkeys([
        *(plan.model_selection_reasons or []), reason,
        "pre_generation_deep_promotion" if target == AnswerModelTier.deep_medical_reasoning else "pre_generation_promotion",
    ]))
    return promoted


# ---------------------------------------------------------------- answer-tier policy
#
# One policy decides which answer model writes a turn, per turn, from reasoning
# requirements (not clinical severity, not intent alone):
#
#   FAST      straightforward: a value, a range check, a low-risk definition
#   STANDARD  personal interpretation: meaning, causes, a simple trend, lifestyle links
#   DEEP      synthesis: blood + Bio-AI, conflicting findings, whole-record comparison or
#             prioritisation, several interacting markers
#
# Inputs are cheap and known before retrieval: the semantic plan (goal, named markers,
# Bio-AI, lifestyle concepts, sources, time need), the message's wording and the
# conversation state. Retrieval may still promote one step (promote_for_retrieved_complexity)
# before the single answer call.

FAST_MAX_SCORE = 2
STANDARD_MAX_SCORE = 5

_GOAL_WEIGHT = {
    "LOOKUP": 0,
    "GENERAL_EDUCATION": 0,
    "DOCUMENT_LOOKUP": 1,
    "ASSESS": 3,  # reduced to 1 for a plain range check on one value
    "EXPLAIN": 3,
    "RISK": 3,
    "ACTION": 3,
    "CAUSES": 3,
    "COMPARE": 3,
    "PRIORITIZE": 4,
    "SYNTHESIZE": 4,
}
_CONTRAST = re.compile(
    r"\b(?:even though|even if|although|though|despite|in spite of|doesn'?t match|does not match|"
    r"don'?t match|contradict\w*|conflict\w*|why (?:is|are|would|does) .{0,40}\bif\b|"
    r"yet|whereas|while my|but (?:my|the|it|i|then|still|why)|how can both|both be true|makes? no sense)\b",
    re.I,
)
_BREADTH = re.compile(
    r"\b(?:across|all (?:of )?my (?:reports?|data|results|tests)|overall|whole|big(?:ger)? picture|everything|"
    r"fit together|tie together|tell the same story|same story|all of (?:that|this|it)|"
    r"together|in combination|connect(?:ed)? (?:to each other|together))\b",
    re.I,
)
_NUANCED_PRIORITY = re.compile(r"\b(?:minor|matter(?:s)? less|least|not (?:a )?(?:big )?(?:deal|worry)|can (?:ignore|wait)|actually matters)\b", re.I)
_UNCERTAIN = re.compile(r"\b(?:not sure|unclear|uncertain|confus\w*|missing|don'?t understand|no idea)\b", re.I)
_RELATION = re.compile(r"\b(?:related|relate|connected|linked|because of|due to|affect\w*|contribut\w*|cause\w*)\b", re.I)
_SOURCE_WORDS = {
    "blood": re.compile(r"\b(?:blood|lab|report|hba1c|glucose|cholesterol|ldl|hdl|triglycerides?|marker)", re.I),
    "bio_ai": re.compile(r"\bbio[\s-]?ai\b|\brisk score|\b(?:diabetes|cardiac|metabolic|heart) risk\b", re.I),
    "lifestyle": re.compile(r"\b(?:lifestyle|questionnaire|exercis\w*|diet|sleep\w*|stress|activity|active|walk\w*|eat\w*|smok\w*|alcohol|weight loss)\b", re.I),
}
_TIER_NAME = {
    AnswerModelTier.fast_reasoning: "fast",
    AnswerModelTier.standard_medical: "standard",
    AnswerModelTier.deep_medical_reasoning: "deep",
}
_FORCE = {"fast": AnswerModelTier.fast_reasoning, "standard": AnswerModelTier.standard_medical, "deep": AnswerModelTier.deep_medical_reasoning}


class TierAssessment:
    __slots__ = ("score", "tier", "reasons")

    def __init__(self, score: int, tier: AnswerModelTier, reasons: list[str]):
        self.score = score
        self.tier = tier
        self.reasons = reasons

    def as_dict(self) -> dict:
        return {"complexity_score": self.score, "answer_tier": tier_name(self.tier), "routing_reason": list(self.reasons)}


def tier_name(tier: AnswerModelTier | str | None) -> str | None:
    parsed = tier if isinstance(tier, AnswerModelTier) else parse_model_tier(tier)
    return _TIER_NAME.get(parsed) if parsed else None


def tier_for_score(score: int) -> AnswerModelTier:
    if score <= FAST_MAX_SCORE:
        return AnswerModelTier.fast_reasoning
    if score <= STANDARD_MAX_SCORE:
        return AnswerModelTier.standard_medical
    return AnswerModelTier.deep_medical_reasoning


def assess_answer_complexity(
    message: str,
    semantic,
    plan: QueryPlan | None = None,
    *,
    conversation_markers: list[str] | None = None,
    continuing: bool = False,
) -> TierAssessment:
    """Score how much reasoning the answer needs. Pure function of cheap signals."""
    text = message or ""
    goal = getattr(getattr(semantic, "primary_goal", None), "value", None) or "EXPLAIN"
    secondary = {getattr(g, "value", g) for g in getattr(semantic, "secondary_goals", None) or []}
    markers = [m for m in (getattr(semantic, "markers", None) or []) if m != "bio_ai"]
    carried = [m for m in (conversation_markers or []) if m not in markers and is_lab_key(m)]
    bio_named = bool(getattr(semantic, "bio_ai", None)) or "bio_ai" in (getattr(semantic, "markers", None) or [])
    concepts = list(getattr(semantic, "concepts", None) or [])
    sources = {getattr(s, "value", s) for s in getattr(semantic, "required_sources", None) or []}
    temporal = getattr(getattr(semantic, "temporal_requirement", None), "value", None)
    reasons: list[str] = []
    score = 0

    weight = _GOAL_WEIGHT.get(goal, 3)
    reasoning_goal = weight >= 3
    if not getattr(semantic, "goal_from_cue", True) and not (_CONTRAST.search(text) or _RELATION.search(text) or _BREADTH.search(text)):
        # No reasoning cue at all ("Is my HDL within range?", "And my HDL?"): the neutral
        # default goal is not evidence that the answer needs interpretation.
        weight, reasoning_goal = 1, False
        reasons.append("no_reasoning_cue")
    elif goal == "ASSESS" and len(markers) <= 1 and not concepts and not bio_named and not _CONTRAST.search(text):
        weight, reasoning_goal = 1, False  # "is my TSH normal?" is a range check
        reasons.append("range_check")
    elif weight:
        reasons.append(f"goal:{goal.lower()}")
    score += weight

    # Biomarkers the answer has to reason about together (named now or carried from the
    # conversation). One marker adds nothing; each further one adds reasoning load.
    involved = len(markers) + (len(carried) if reasoning_goal else 0)
    if involved >= 2:
        score += min(3, involved - 1)
        reasons.append(f"multi_marker:{involved}")

    # Data sources the answer must combine.
    # Only what the member actually brings into the question counts; the sources a
    # synthesis question may optionally read are not, by themselves, extra reasoning.
    used = set()
    if markers or carried or _SOURCE_WORDS["blood"].search(text):
        used.add("blood")
    if bio_named or _SOURCE_WORDS["bio_ai"].search(text):
        used.add("bio_ai")
    lifestyle = bool(concepts) or bool(_SOURCE_WORDS["lifestyle"].search(text))
    if lifestyle:
        used.add("lifestyle")
    if {"blood", "bio_ai"} <= used and reasoning_goal:
        score += 3
        reasons.append("blood+bioai")
    elif "bio_ai" in used and reasoning_goal:
        score += 1
        reasons.append("bioai")
    if lifestyle and reasoning_goal:
        score += 1
        reasons.append("lifestyle_personalization")

    if reasoning_goal and _CONTRAST.search(text):
        score += 3
        reasons.append("conflicting_findings")
    if reasoning_goal and _BREADTH.search(text):
        score += 3
        reasons.append("whole_record_synthesis")
    if goal == "COMPARE" and not markers:
        score += 3
        reasons.append("cross_report_comparison")
    elif goal != "COMPARE" and (temporal in {"TREND", "HISTORICAL", "COMPARISON"} or "COMPARE" in secondary) and reasoning_goal:
        score += 1
        reasons.append("trend_and_current_state")
    if goal == "PRIORITIZE" and _NUANCED_PRIORITY.search(text):
        score += 2
        reasons.append("nuanced_prioritization")
    # "How are X, Y and Z connected?": the number of things to relate drives the load.
    things = len(markers) + len(concepts) + len([d for d in getattr(semantic, "domains", None) or [] if not markers])
    if reasoning_goal and things >= 2 and _RELATION.search(text):
        bonus = 2 if things >= 3 else 1
        score += bonus
        reasons.append(f"relationship_between_findings:{things}")
    if reasoning_goal and _UNCERTAIN.search(text):
        score += 1
        reasons.append("uncertainty")
    if continuing and reasoning_goal:
        score += 1
        reasons.append("follow_up_needs_prior_context")
    route_reasons = set((plan.model_selection_reasons if plan is not None else None) or [])
    if "uploaded_report_analysis" in route_reasons:
        score += 3
        reasons.append("uploaded_document_analysis")

    return TierAssessment(score, tier_for_score(score), reasons)


def select_answer_tier(plan: QueryPlan, assessment: TierAssessment) -> QueryPlan:
    """Apply the policy to a plan that will be answered by a model (deterministic stays so)."""
    from app.core.config import settings

    from app.pipeline.narrative import wants_narrative_summary

    if wants_narrative_summary(plan.raw_message, plan) and settings.enable_llm and plan.intent == IntentType.health_scenario:
        # An overall reading has to connect several findings. A one-theme template cannot.
        plan = plan.model_copy(update={
            "operations": list(dict.fromkeys([*(plan.operations or []), "SUMMARIZE"])),
            "reasoning_required": True,
        })
        return _set_tier(plan, AnswerModelTier.standard_medical)
    reasoning_turn = any(r.startswith("goal:") and r not in {"goal:lookup", "goal:general_education", "goal:document_lookup"} for r in assessment.reasons)
    if not uses_medical_answer_llm(plan.answer_model_tier):
        # A route-time "lookup" that in fact asks for reasoning about the member's own data
        # ("compare my reports and explain what matters") is answered by a model.
        if not (plan.needs_personal_data and reasoning_turn and assessment.score > FAST_MAX_SCORE):
            return plan
    if reasoning_turn and plan.needs_personal_data:
        # The answer interprets, so no structured value template may short-circuit it.
        plan = plan.model_copy(update={"operations": list(dict.fromkeys([*(plan.operations or []), "INTERPRET"]))})
    tier = assessment.tier
    reasons = list(assessment.reasons)
    forced = forced_answer_tier()
    if forced is not None:
        tier = forced
        reasons.append(f"forced:{tier_name(forced)}")
    return _set_tier(plan.model_copy(update={
        "complexity_score": assessment.score,
        "initial_answer_tier": tier,
        "model_selection_reasons": list(dict.fromkeys([*(plan.model_selection_reasons or []), *reasons])),
    }), tier)


def forced_answer_tier() -> AnswerModelTier | None:
    """CURA_FORCE_ANSWER_TIER, honoured outside production only."""
    from app.core.config import settings

    value = (settings.cura_force_answer_tier or "").strip().lower()
    if not value or not settings.is_development:
        return None
    return _FORCE.get(value)


def _set_tier(plan: QueryPlan, tier: AnswerModelTier) -> QueryPlan:
    depth = {
        AnswerModelTier.fast_reasoning: ReasoningDepth.none,
        AnswerModelTier.standard_medical: ReasoningDepth.standard,
        AnswerModelTier.deep_medical_reasoning: ReasoningDepth.deep,
    }[tier]
    complexity = {
        AnswerModelTier.fast_reasoning: AnswerComplexity.low,
        AnswerModelTier.standard_medical: AnswerComplexity.medium,
        AnswerModelTier.deep_medical_reasoning: AnswerComplexity.high,
    }[tier]
    return plan.model_copy(update={
        "answer_model_tier": tier,
        "model_tier": tier,
        "reasoning_depth": depth,
        "complexity": complexity,
        "reasoning_required": True,
    })
