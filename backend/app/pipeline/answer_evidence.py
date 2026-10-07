"""Answer director: choose the evidence the answering model sees.

CURA understands broadly, thinks deeply, and answers selectively. Retrieval may bring back
dozens of facts; this module picks the few that answer the current question, the
questionnaire answers that change the advice, and a ranked handful of next steps. More
available data improves the selection, not the length of the answer.

Budgets are presentation limits, not retrieval limits. Measured values are copied as
they are: never rounded, converted or merged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.contracts.common import IntentType, MarkerFlag
from app.contracts.health_context import HealthContext
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.questionnaire_relevance import (
    LEVER,
    SUPPORTIVE,
    QuestionnaireSelection,
    select_questionnaire_context,
)

LOOKUP = "SINGLE_VALUE"
EXPLANATION = "INTERPRETATION"
ACTION_PLAN = "ACTION_PLAN"
PRIORITIZATION = "PRIORITIZATION"
OVERVIEW = "HEALTH_OVERVIEW"
TREND = "TREND"
QUESTIONNAIRE_LOOKUP = "QUESTIONNAIRE_LOOKUP"
BIO_AI = "BIO_AI_INTERPRETATION"


@dataclass(frozen=True)
class InformationBudget:
    primary: int
    supporting: int
    questionnaire: int
    trend: int
    missing: int
    next_actions: int
    proactive: int
    words: tuple[int, int]


BUDGETS: dict[str, InformationBudget] = {
    LOOKUP: InformationBudget(1, 0, 0, 0, 1, 0, 1, (40, 100)),
    EXPLANATION: InformationBudget(1, 2, 2, 1, 1, 2, 1, (80, 180)),
    BIO_AI: InformationBudget(3, 2, 2, 0, 1, 2, 1, (80, 180)),
    ACTION_PLAN: InformationBudget(1, 2, 3, 1, 1, 3, 1, (80, 180)),
    PRIORITIZATION: InformationBudget(3, 2, 3, 0, 1, 3, 1, (80, 200)),
    TREND: InformationBudget(1, 1, 0, 1, 1, 1, 1, (60, 150)),
    QUESTIONNAIRE_LOOKUP: InformationBudget(0, 0, 0, 0, 0, 0, 0, (30, 90)),
    OVERVIEW: InformationBudget(12, 0, 5, 3, 1, 3, 1, (180, 350)),
}

_ABNORMAL = {"low", "high", "critical"}
_ACTION = re.compile(
    r"\b(how (?:can|do|should) i|what (?:can|should) i (?:do|eat|change)|what to do|tips|"
    r"(?:improve|lower|reduce|raise|increase|bring (?:down|up)|manage)\s+my|plan)\b",
    re.I,
)
_PRIORITIZE = re.compile(r"\b(focus on|priorit\w*|most important|first|matters most|start with)\b", re.I)
_TREND_WORDS = re.compile(r"\b(trend|changed|improved|getting (?:better|worse)|over time|compare|previous)\b", re.I)


def response_mode_for(context: HealthContext, message: str) -> str:
    """Which kind of answer the member is asking for. Drives budgets and presentation."""
    intent = context.intent
    text = message or ""
    if intent == IntentType.questionnaire_lookup:
        return QUESTIONNAIRE_LOOKUP
    if intent in {IntentType.health_scenario, IntentType.broad_health_summary} or "overall_health" in (context.domains or []):
        return PRIORITIZATION if _PRIORITIZE.search(text) and not re.search(r"\boverall|how am i\b", text, re.I) else OVERVIEW
    if _ACTION.search(text):
        return ACTION_PLAN
    if intent in {IntentType.trend, IntentType.previous_result} or (_TREND_WORDS.search(text) and intent != IntentType.latest_result):
        return TREND
    if intent in {IntentType.bio_ai_score, IntentType.bio_ai_explanation, IntentType.bio_ai_comparison}:
        return BIO_AI
    if _PRIORITIZE.search(text):
        return PRIORITIZATION
    if intent == IntentType.latest_result:
        return LOOKUP
    return EXPLANATION


def _flag(marker) -> str:
    raw = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
    return str(raw or "").lower()


def _marker_fact(marker) -> dict:
    """A measured value exactly as stored. No conversion, rounding or new fields."""
    fact = {
        "code": marker.key,
        "name": marker.name,
        "value": marker.value,
        "unit": marker.unit,
        "status": _flag(marker) or None,
        "reference_low": marker.reference_low,
        "reference_high": marker.reference_high,
        "measured_at": str(marker.measured_at) if marker.measured_at else None,
        "source": "measured blood result",
    }
    return {k: v for k, v in fact.items() if v is not None}


def _risk_fact(risk) -> dict:
    fact = {
        "code": risk.code,
        "name": risk.name,
        "score": risk.score,
        "status": risk.status,
        "contributing_factors": list(risk.contributing_factors or [])[:3] or None,
        "source": "Bio-AI risk assessment (not a diagnosis)",
    }
    return {k: v for k, v in fact.items() if v not in (None, [], "")}


def _elevated(risk) -> bool:
    status = (risk.status or "").lower()
    return any(word in status for word in ("high", "elevated", "moderate", "attention", "risk")) and "low" not in status


@dataclass
class AnswerEvidence:
    question: str
    response_mode: str
    conversation_goal: str | None
    budget: InformationBudget
    primary_facts: list[dict] = field(default_factory=list)
    supporting_facts: list[dict] = field(default_factory=list)
    trend_facts: list[dict] = field(default_factory=list)
    uncertainty_facts: list[dict] = field(default_factory=list)
    questionnaire_facts: list[dict] = field(default_factory=list)
    personalization_facts: dict = field(default_factory=dict)
    next_action_context: list[dict] = field(default_factory=list)
    already_doing: list[str] = field(default_factory=list)
    reassuring_groups: list[dict] = field(default_factory=list)
    already_explained: list[str] = field(default_factory=list)
    questionnaire: QuestionnaireSelection | None = None
    trace: dict = field(default_factory=dict)

    def payload(self) -> dict:
        """What the answering model receives instead of the full health record."""
        out = {
            "question": self.question,
            "response_mode": self.response_mode,
            "conversation_goal": self.conversation_goal,
            "primary_facts": self.primary_facts,
            "supporting_facts": self.supporting_facts,
            "trend": self.trend_facts,
            "uncertainty": self.uncertainty_facts,
            "questionnaire_context": self.questionnaire_facts,
            "personalization_context": self.personalization_facts,
            "ranked_next_steps": self.next_action_context,
            "already_doing": self.already_doing,
            "reassuring_groups": self.reassuring_groups,
            "already_explained_in_this_conversation": self.already_explained,
            "answer_budget": {
                "target_words": f"{self.budget.words[0]}-{self.budget.words[1]}",
                "max_next_steps": self.budget.next_actions,
                "max_follow_up_questions": 1,
            },
        }
        return {k: v for k, v in out.items() if v not in (None, [], {})}


# Recommendation categories/words tied to a habit the member may already have.
_HABIT_OF = {
    "activity": ({"physical_activity_frequency", "exercise_frequency_week", "exercise_level", "daily_active_duration"},
                 re.compile(r"\b(exercis\w*|walk\w*|activ\w*|workout|move more|aerobic|cardio)\b", re.I)),
    "sleep": ({"sleeping_hours"}, re.compile(r"\bsleep\w*\b", re.I)),
    "alcohol": ({"alcohol_frequency"}, re.compile(r"\balcohol|drink\w*\b", re.I)),
    "tobacco": ({"tobacco_frequency"}, re.compile(r"\b(smok\w*|tobacco)\b", re.I)),
}


def rank_next_steps(recommendations, selection: QuestionnaireSelection, limit: int) -> tuple[list[dict], list[str]]:
    """Rank approved recommendations by personal relevance; drop ones the member already does.

    priority ~ clinical relevance (approved for this finding) x personalization:
    a recommendation that targets a reported gap ranks first; one the member already
    does is removed from the list and noted under ``already_doing`` instead.
    """
    supportive = {s.key for s in selection.signals if s.stance == SUPPORTIVE}
    levers = {s.key for s in selection.signals if s.stance == LEVER}
    ranked: list[tuple[int, dict]] = []
    already: list[str] = []
    for index, rec in enumerate(recommendations or []):
        text = f"{rec.category} {rec.text}"
        habit = next((name for name, (keys, pattern) in _HABIT_OF.items()
                      if rec.category == name or pattern.search(text)), None)
        keys = _HABIT_OF[habit][0] if habit else set()
        if keys & supportive and not keys & levers:
            already.append(habit)
            continue
        score = 2 if keys & levers else 1
        ranked.append((score * 100 - index, {"text": rec.text, "category": rec.category}))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in ranked[:limit]], list(dict.fromkeys(already))


def _reassuring_groups(markers) -> list[dict]:
    groups: dict[str, list[str]] = {}
    for marker in markers:
        if _flag(marker) != "normal":
            continue
        domain = domain_for_entity(marker.key)
        title = domain.code.replace("_", " ").replace(" health", "") if domain else "other results"
        groups.setdefault(title, []).append(marker.key)
    return [{"area": area, "within_range": keys[:6]} for area, keys in list(groups.items())[:6]]


def build_answer_evidence(context: HealthContext, message: str) -> AnswerEvidence:
    mode = response_mode_for(context, message)
    budget = BUDGETS[mode]
    evidence = AnswerEvidence(
        question=message,
        response_mode=mode,
        conversation_goal=context.conversation_goal,
        budget=budget,
        already_explained=list(dict.fromkeys([*(context.facts_already_explained or []), *(context.explained_entities or [])]))[:6],
    )
    markers = [m for m in context.markers or [] if m.value is not None]
    requested = [c for c in [*(context.display_entity_codes or []), *(context.requested_entity_codes or [])] if c]
    if context.resolved_topic:
        requested.append(context.resolved_topic)
    requested = list(dict.fromkeys(requested))

    goal = (context.personalization.primary_health_goal if context.personalization else None) or next(
        (g.goal_code for g in context.goals or [] if getattr(g, "status", "active") == "active"), None)

    # ---- primary and supporting facts
    if mode in {OVERVIEW, PRIORITIZATION}:
        abnormal = prioritize_findings(markers, context.bio_ai_risks or [], goal)
        evidence.primary_facts = [_marker_fact(m) for m in abnormal[: budget.primary]]
        evidence.supporting_facts = [_risk_fact(r) for r in (context.bio_ai_risks or []) if _elevated(r)][
            : (5 if mode == OVERVIEW else budget.supporting)]
        if mode == OVERVIEW:
            evidence.reassuring_groups = _reassuring_groups(markers)
    elif mode == BIO_AI:
        risks = sorted(context.bio_ai_risks or [], key=lambda r: (not _elevated(r)))
        wanted = [r for r in risks if r.code in requested] or risks
        evidence.primary_facts = [_risk_fact(r) for r in wanted[: budget.primary]]
        related = [m for m in markers if _flag(m) in _ABNORMAL]
        evidence.supporting_facts = [_marker_fact(m) for m in related[: budget.supporting]]
    elif mode != QUESTIONNAIRE_LOOKUP:
        named = [m for m in markers if m.key in requested]
        cap = min(3, max(budget.primary, len({m.key for m in named}))) if named else budget.primary
        primary = named[:cap] or ([m for m in markers if _flag(m) in _ABNORMAL] or markers)[: budget.primary]
        evidence.primary_facts = [_marker_fact(m) for m in primary]
        primary_keys = {m.key for m in primary}
        supporting_codes = [c for c in (context.reasoning_context_codes or []) if c not in primary_keys]
        supporting = [m for m in markers if m.key in supporting_codes and _flag(m) in _ABNORMAL]
        if not supporting:
            supporting = [m for m in markers if m.key not in primary_keys and _flag(m) in _ABNORMAL
                          and _same_domain(m.key, primary_keys)]
        evidence.supporting_facts = [_marker_fact(m) for m in supporting[: budget.supporting]]
        if len(evidence.supporting_facts) < budget.supporting:
            domains = {d.code for d in (domain_for_entity(k) for k in primary_keys) if d}
            aligned = [r for r in context.bio_ai_risks or [] if _elevated(r) and _risk_in_domains(r.code, domains)]
            room = budget.supporting - len(evidence.supporting_facts)
            evidence.supporting_facts += [_risk_fact(r) for r in aligned[:room]]

    # ---- trend for the primary fact
    if budget.trend:
        primary_codes = {f.get("code") for f in evidence.primary_facts}
        for base in context.baselines or []:
            if base.entity in primary_codes and base.previous is not None and base.observations >= 2:
                evidence.trend_facts.append({
                    "code": base.entity, "previous": base.previous, "latest": base.latest,
                    "direction": base.direction,
                })
        evidence.trend_facts = evidence.trend_facts[: budget.trend]

    # ---- one uncertainty that changes interpretation
    if budget.missing:
        primary_codes = {f.get("code") for f in evidence.primary_facts}
        for item in context.missing or []:
            if item.key in primary_codes or mode in {EXPLANATION, ACTION_PLAN}:
                evidence.uncertainty_facts.append({"code": item.key, "name": item.name, "reason": item.reason})
                break

    # ---- questionnaire as reasoning context (never the whole questionnaire)
    selection = QuestionnaireSelection()
    if budget.questionnaire and (context.questionnaire or context.questionnaire_instances or _recent(context)):
        entity_codes = [f.get("code") for f in [*evidence.primary_facts, *evidence.supporting_facts] if f.get("code")]
        selection = select_questionnaire_context(
            message,
            entities=entity_codes,
            domains=list(context.domains or []),
            questionnaire=context.questionnaire_instances or context.questionnaire,
            review=mode in {OVERVIEW, PRIORITIZATION},
            recent_messages=_recent(context),
            budget=budget.questionnaire,
        )
        evidence.questionnaire_facts = [s.for_model() for s in selection.signals]
    evidence.questionnaire = selection

    # ---- personalization: goals and recent context, only when they change the answer
    perso = context.personalization
    if mode not in {LOOKUP, QUESTIONNAIRE_LOOKUP, TREND}:
        if goal:
            evidence.personalization_facts["goal"] = goal
        if perso:
            recent = perso.recent_user_context.model_dump(exclude_none=True, exclude={"source"})
            recent = {k: v for k, v in recent.items() if v}
            if recent:
                evidence.personalization_facts["user_stated_recently"] = recent
        if context.profile and mode in {EXPLANATION, ACTION_PLAN, OVERVIEW, PRIORITIZATION}:
            conditions = [str(f.value) for f in (context.profile.relevant_conditions or [])][:2]
            if conditions:
                evidence.personalization_facts["known_conditions"] = conditions

    # ---- ranked next steps
    if budget.next_actions:
        evidence.next_action_context, evidence.already_doing = rank_next_steps(
            context.recommendations, selection, budget.next_actions)
        for signal in selection.signals:
            if signal.stance == SUPPORTIVE and signal.label not in evidence.already_doing:
                evidence.already_doing.append(signal.label)

    # ---- observability (developer trace only)
    retrieved_facts = len(context.markers or []) + len(context.bio_ai_risks or []) + len(context.facts or [])
    selected = len(evidence.primary_facts) + len(evidence.supporting_facts) + len(evidence.trend_facts)
    evidence.trace = {
        "response_mode": mode,
        "conversation_goal": context.conversation_goal,
        "retrieved_fact_count": retrieved_facts,
        "selected_answer_fact_count": selected,
        "facts_dropped_from_model_context": max(0, retrieved_facts - selected),
        "questionnaire_retrieved": selection.retrieved_keys,
        "questionnaire_selected_keys": selection.selected_keys,
        "questionnaire_overridden_by_conversation": selection.overridden_keys,
        "profile_fields_selected": sorted(evidence.personalization_facts),
        "next_steps_selected": len(evidence.next_action_context),
        "already_doing": evidence.already_doing,
    }
    return evidence


def _recent(context: HealthContext) -> list[str]:
    return list(getattr(context, "recent_user_messages", None) or [])


def _same_domain(key: str, primary_keys: set[str]) -> bool:
    domain = domain_for_entity(key)
    return bool(domain) and any((domain_for_entity(p) or domain).code == domain.code for p in primary_keys)


_RISK_DOMAINS = {
    "type_2_diabetes": {"glycemic_health", "metabolic_health"},
    "metabolic_score": {"metabolic_health", "glycemic_health"},
    "metabolic_age": {"metabolic_health"},
    "dyslipidemia": {"lipid_health", "cardiovascular_health"},
    "cardiac_health": {"cardiovascular_health", "lipid_health"},
    "hypertension": {"blood_pressure_health", "cardiovascular_health"},
    "nafld": {"liver_health", "metabolic_health"},
    "obesity": {"weight_body_composition", "metabolic_health"},
}


def _risk_in_domains(code: str, domains: set[str]) -> bool:
    return bool(_RISK_DOMAINS.get(code, set()) & domains)


_LEGACY_INTENTS = {
    IntentType.questionnaire_lookup,
    IntentType.health_goal_progress,
    IntentType.personal_profile,
    IntentType.report_explanation,
}


def uses_answer_evidence(context: HealthContext) -> bool:
    """Standard questions get the selected evidence; specialised flows keep their payload."""
    if context.intent in _LEGACY_INTENTS:
        return False
    if context.uploaded_documents or context.source_conflicts or context.cross_source:
        return False
    if "PREPARE_CLINICIAN_DISCUSSION" in (context.operations or []):
        return False
    return bool(context.markers or context.bio_ai_risks)


# Health goals -> the domains they make more important when ranking priorities.
_GOAL_DOMAINS = {
    "improve_metabolic_health": {"glycemic_health", "metabolic_health", "lipid_health", "weight_body_composition"},
    "heart_health": {"cardiovascular_health", "lipid_health", "blood_pressure_health"},
    "improve_heart_health": {"cardiovascular_health", "lipid_health", "blood_pressure_health"},
    "weight_management": {"weight_body_composition", "metabolic_health", "glycemic_health"},
    "lose_weight": {"weight_body_composition", "metabolic_health", "glycemic_health"},
    "improve_energy": {"energy_fatigue_context", "red_cell_anaemia_health", "iron_status", "vitamin_b12_folate_status"},
}


def _deviation(marker) -> float:
    """How far outside the reported range, as a fraction of the nearest bound."""
    value, low, high = marker.value, marker.reference_low, marker.reference_high
    if value is None:
        return 0.0
    if high is not None and value > high and high:
        return (value - high) / abs(high)
    if low is not None and value < low and low:
        return (low - value) / abs(low)
    return 0.0


def prioritize_findings(markers, risks, goal: str | None) -> list:
    """Order abnormal results by what matters most, not by report order.

    score = how far outside range + agreement from an elevated Bio-AI risk in the same area
            + being part of a cluster of related abnormal results + fit with the member's goal.
    Critical values always come first.
    """
    abnormal = [m for m in markers if _flag(m) in _ABNORMAL]
    goal_domains = _GOAL_DOMAINS.get(goal or "", set())
    elevated_domains = set()
    for risk in risks:
        if _elevated(risk):
            elevated_domains |= _RISK_DOMAINS.get(risk.code, set())
    domain_counts: dict[str, int] = {}
    for marker in abnormal:
        domain = domain_for_entity(marker.key)
        if domain:
            domain_counts[domain.code] = domain_counts.get(domain.code, 0) + 1

    def score(marker) -> float:
        domain = domain_for_entity(marker.key)
        code = domain.code if domain else ""
        related = {code} | set(getattr(domain, "related_domains", ()) or ()) if domain else set()
        value = min(_deviation(marker), 1.0)
        value += 0.35 if related & elevated_domains else 0.0
        value += 0.25 if domain_counts.get(code, 0) >= 2 else 0.0
        value += 0.3 if related & goal_domains else 0.0
        value += 5.0 if _flag(marker) == "critical" else 0.0
        return value

    return sorted(abnormal, key=score, reverse=True)
