"""Answer director: choose the evidence the answering model sees.

CURA understands broadly, thinks deeply, and answers selectively. Retrieval may bring back
dozens of facts; this module picks the few that answer the current question, the
questionnaire answers that change the advice, and a ranked handful of next steps. More
available data improves the selection, not the length of the answer.

Budgets are presentation limits, not retrieval limits. Measured values are copied as
they are: never rounded, converted or merged.
"""

from __future__ import annotations

import dataclasses

import re
from dataclasses import dataclass, field

from app.contracts.common import IntentType, MarkerFlag
from app.contracts.health_context import HealthContext
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.health_patterns import find_patterns, theme_codes_for
from app.pipeline.health_topics import (
    TopicMatch,
    concept_spec,
    evidence_markers_for,
    is_behavioural_only,
    questionnaire_keys_for,
)
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
ASSESSMENT = "PERSONALIZED_ASSESSMENT"
CAUSES = "POSSIBLE_EXPLANATIONS"
RISK = "RISK_EXPLANATION"


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
    LOOKUP: InformationBudget(1, 0, 0, 0, 1, 0, 0, (40, 80)),
    EXPLANATION: InformationBudget(1, 2, 2, 1, 1, 0, 0, (100, 150)),
    BIO_AI: InformationBudget(3, 2, 2, 0, 1, 0, 0, (100, 150)),
    ACTION_PLAN: InformationBudget(1, 2, 3, 1, 1, 3, 1, (100, 180)),
    PRIORITIZATION: InformationBudget(3, 2, 3, 1, 1, 3, 1, (100, 180)),
    TREND: InformationBudget(1, 1, 0, 1, 1, 0, 0, (120, 180)),
    QUESTIONNAIRE_LOOKUP: InformationBudget(0, 0, 0, 0, 0, 0, 0, (40, 90)),
    OVERVIEW: InformationBudget(12, 0, 5, 3, 1, 0, 0, (180, 400)),
    ASSESSMENT: InformationBudget(1, 2, 4, 1, 1, 0, 0, (100, 150)),
    CAUSES: InformationBudget(2, 3, 3, 1, 1, 0, 0, (100, 150)),
    RISK: InformationBudget(1, 2, 2, 1, 1, 0, 0, (100, 150)),
}

# Semantic response shape -> evidence mode.
_SHAPE_MODE = {
    "DIRECT_FACT": LOOKUP,
    "EXPLANATION": EXPLANATION,
    "POSSIBLE_EXPLANATIONS": CAUSES,
    "PERSONALIZED_ASSESSMENT": ASSESSMENT,
    "COMPARISON": TREND,
    "PRIORITIZATION": PRIORITIZATION,
    "ACTION_PLAN": ACTION_PLAN,
    "OVERVIEW": OVERVIEW,
    "RISK_EXPLANATION": RISK,
}

# How the reply should be shaped for each reasoning goal (the answer model writes it).
# What a good answer to each kind of question must achieve. These are PURPOSES, not
# formats: the answer model decides the shape (one line, prose, bullets, a numbered list,
# a comparison, rarely a small table) from the wording of the question and the evidence.
GOAL_GUIDANCE = {
    LOOKUP: (
        "The member wants a value. Say whether it is in range and what that means. "
        "The result card shows the number, unit, date and range, so do not repeat them unless no card can be shown."
    ),
    EXPLANATION: (
        "The member wants to understand what this result means. Explain the meaning. "
        "Do not add diet, exercise, or next-step advice unless they asked what to do."
    ),
    CAUSES: (
        "The member wants possible reasons. Connect the listed evidence that fits or argues against each "
        "possibility; say plainly if nothing listed explains it. Never present a possibility as the cause."
    ),
    ASSESSMENT: "The member wants a judgment (is it enough, okay, serious). Give the judgment plainly, with the evidence behind it.",
    TREND: (
        "The member wants to know how things changed. Say whether the result moved toward or away from the expected range. "
        "Leave the exact previous and latest numbers to the comparison card unless no card can be shown."
    ),
    PRIORITIZATION: (
        "The member wants to know what matters most. Decide the order from the evidence: how far outside range, "
        "several markers agreeing (patterns), Bio-AI support, change over time, habits and history. A clearly "
        "significant pattern outranks a minor finding. This is a sensible order, not a formal clinical ranking."
    ),
    ACTION_PLAN: "The member wants to know what to do. Tie actions to their findings and habits, skip what they already do, no medicines or doses.",
    OVERVIEW: "The member wants the overall picture: what matters most, what is reassuring, and what to focus on.",
    RISK: "The member wants to know whether to worry. Be calibrated: evidence for and against concern, and when a clinician visit makes sense.",
    BIO_AI: (
        "The member wants to understand their Bio-AI risk. It is an estimate from several inputs, not a diagnosis "
        "and not one marker; connect it to the measured patterns and habits that point the same way and to what is "
        "reassuring. Do not describe the model's internals."
    ),
}

# Context notes chosen from the shape of the selected evidence (still purposes, not formats).
MULTI_MARKER_GUIDANCE = (
    "Several markers are involved: synthesise how they relate (a shared theme, or not) and what should not be "
    "assumed from them together, rather than describing each one separately."
)
CROSS_SOURCE_GUIDANCE = (
    "Blood results and a Bio-AI risk are both listed: one normal marker does not make the overall risk low and one "
    "abnormal marker does not make it high; reference the member's actual values that point toward or away from it."
)
FOLLOW_UP_GUIDANCE = (
    "This continues the previous turn: build on what was already said rather than starting over, and do not "
    "repeat values already given."
)

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
    semantic = getattr(context, "semantic_plan", None) or {}
    if semantic.get("personalization") == "REQUIRED" and intent not in {IntentType.questionnaire_lookup}:
        mode = _SHAPE_MODE.get(semantic.get("response_shape") or "")
        if mode == EXPLANATION and (semantic.get("bio_ai") and not semantic.get("markers")):
            return BIO_AI
        if set(semantic.get("markers") or []) == {"bio_ai"} and mode not in {TREND, ACTION_PLAN, PRIORITIZATION, OVERVIEW}:
            return BIO_AI  # "my Bio-AI risk": the assessment as a whole
        if mode == PRIORITIZATION and "overall_health" in (semantic.get("health_topics") or []) and semantic.get("primary_goal") == "SYNTHESIZE":
            return OVERVIEW
        if mode:
            return mode
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
    reasoning_goal: str | None = None
    secondary_goals: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    premise_check: dict | None = None
    checked_without_concern: list[str] = field(default_factory=list)
    extra_guidance: list[str] = field(default_factory=list)
    patterns: list[dict] = field(default_factory=list)
    reassuring: list[dict] = field(default_factory=list)
    other_notable: list[str] = field(default_factory=list)

    def payload(self) -> dict:
        """What the answering model receives instead of the full health record."""
        out = {
            "question": self.question,
            "reasoning_goal": self.reasoning_goal,
            "also_address": self.secondary_goals,
            "topics": self.topics,
            "response_mode": self.response_mode,
            "how_to_answer": " ".join([GOAL_GUIDANCE.get(self.response_mode) or "", *self.extra_guidance]).strip(),
            "premise_check": self.premise_check,
            "conversation_goal": self.conversation_goal,
            "primary_facts": self.primary_facts,
            "supporting_facts": self.supporting_facts,
            "checked_and_within_range": self.checked_without_concern,
            "trend": self.trend_facts,
            "uncertainty": self.uncertainty_facts,
            "questionnaire_context": self.questionnaire_facts,
            "personalization_context": self.personalization_facts,
            "ranked_next_steps": self.next_action_context,
            "already_doing": self.already_doing,
            "reassuring_groups": self.reassuring_groups,
            "patterns": self.patterns,
            "reassuring_systems": self.reassuring,
            "already_explained_in_this_conversation": self.already_explained,
            "answer_budget": {"max_next_steps": self.budget.next_actions},
            "other_notable_findings": self.other_notable,
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
    carried = set(_conversation_codes(context))
    requested = [
        c for c in [*(context.display_entity_codes or []), *(context.requested_entity_codes or [])]
        if c and c not in carried
    ]
    if context.resolved_topic:
        requested.append(context.resolved_topic)
    requested = list(dict.fromkeys(requested))

    semantic = getattr(context, "semantic_plan", None) or {}
    topics = _semantic_topics(semantic)
    if "bio_ai" in topics.markers and context.bio_ai_risks:
        # "my Bio-AI risk" names the whole assessment, not one score: use its elevated risks.
        elevated = [r.code for r in context.bio_ai_risks if str(r.status or "").lower() in {"high", "very high", "elevated", "moderate"}]
        topics = dataclasses.replace(
            topics,
            markers=[m for m in topics.markers if m != "bio_ai"],
            bio_ai=list(dict.fromkeys([*topics.bio_ai, *(elevated or [r.code for r in context.bio_ai_risks])])),
        )
        requested = [c for c in requested if c != "bio_ai"]
    if semantic:
        evidence.reasoning_goal = semantic.get("primary_goal")
        evidence.secondary_goals = list(semantic.get("secondary_goals") or [])
        evidence.topics = [t for t in semantic.get("health_topics") or [] if not t.endswith(("_health", "_context")) and t != "lifestyle_recovery"][:4]
        requested = list(dict.fromkeys([*topics.markers, *topics.bio_ai, *requested]))
    topic_markers = [k for k in evidence_markers_for(topics) if k not in topics.markers] if topics.concepts else []
    behavioural = bool(semantic) and is_behavioural_only(topics)

    goal = (context.personalization.primary_health_goal if context.personalization else None) or next(
        (g.goal_code for g in context.goals or [] if getattr(g, "status", "active") == "active"), None)

    # ---- patterns across systems (synthesis) and what is reassuring
    trend_codes = {
        b.entity: "worse" for b in context.baselines or []
        if getattr(getattr(b, "classification", None), "value", "") == "WORSENED" or b.newly_abnormal
    }
    panel = list(getattr(context, "panel_markers", None) or []) or markers
    patterns, reassuring = find_patterns(panel, context.bio_ai_risks or [], trend_codes=trend_codes)

    # ---- primary and supporting facts
    if mode in {OVERVIEW, PRIORITIZATION}:
        abnormal = prioritize_findings(markers, context.bio_ai_risks or [], goal)
        if mode == PRIORITIZATION and patterns:
            # One lead finding per pattern: "glucose regulation" is one priority, not two
            # (HbA1c and glucose); the rest of each pattern is supporting evidence.
            order = [p["out_of_range"][0]["code"] for p in patterns[: budget.primary]]
            others = {f["code"] for p in patterns[: budget.primary] for f in p["out_of_range"][1:]}
            by_key = {m.key: m for m in markers}
            evidence.primary_facts = [_marker_fact(by_key[c]) for c in order if c in by_key]
            evidence.supporting_facts = [_marker_fact(m) for m in markers if m.key in others][:3]
        else:
            evidence.primary_facts = [_marker_fact(m) for m in abnormal[: budget.primary]]
        evidence.supporting_facts = list(evidence.supporting_facts) + [
            _risk_fact(r) for r in (context.bio_ai_risks or []) if _elevated(r)
        ][: (5 if mode == OVERVIEW else budget.supporting)]
        if mode == OVERVIEW:
            evidence.reassuring_groups = _reassuring_groups(markers)
    elif mode == BIO_AI:
        risks = sorted(context.bio_ai_risks or [], key=lambda r: (not _elevated(r)))
        wanted = [r for r in risks if r.code in requested] or risks
        evidence.primary_facts = [_risk_fact(r) for r in wanted[: budget.primary]]
        # The marker the member named stays even when it is in range. A Bio-AI
        # score and a blood result are different kinds of evidence.
        named = [m for m in markers if m.key in requested]
        related = named + [m for m in markers if m not in named and _flag(m) in _ABNORMAL]
        evidence.supporting_facts = [_marker_fact(m) for m in related[: max(budget.supporting, len(named[:3]))]]
    elif mode == TREND and not requested:
        # "What changed / what got worse?" across the record: the markers that moved.
        moved = [b for b in context.baselines or [] if b.previous is not None and b.latest is not None and b.latest != b.previous]
        moved.sort(key=lambda b: abs(b.percentage_change or 0), reverse=True)
        codes = [b.entity for b in moved[:3]]
        evidence.primary_facts = [_marker_fact(m) for m in markers if m.key in codes]
        evidence.trend_facts = [
            {"code": b.entity, "previous": b.previous, "latest": b.latest, "direction": b.direction}
            for b in moved[:3]
        ]
    elif behavioural and mode != QUESTIONNAIRE_LOOKUP:
        # "Am I active enough?" / "what habit first?": the habit answers are the primary
        # evidence (questionnaire_context); the member's notable findings give the
        # "for my health situation" context.
        notable = prioritize_findings(markers, context.bio_ai_risks or [], goal)
        if re.search(r"\b(active enough|physical activity|exercise)\b", message or "", re.I):
            unrelated = {"mcv", "mch", "rdw", "basophils", "eosinophils", "calcium", "bilirubin", "ferritin"}
            notable = [marker for marker in notable if marker.key not in unrelated]
        evidence.supporting_facts = [_marker_fact(m) for m in notable[: budget.supporting]]
        if len(evidence.supporting_facts) < budget.supporting:
            room = budget.supporting - len(evidence.supporting_facts)
            evidence.supporting_facts += [_risk_fact(r) for r in (context.bio_ai_risks or []) if _elevated(r)][:room]
    elif topic_markers and not topics.markers and mode != QUESTIONNAIRE_LOOKUP:
        # Symptom-style topics ("why am I tired?"): check the markers that may hold context.
        # They are possibilities to look at, never causes.
        relevant = [m for m in markers if m.key in topic_markers]
        flagged = [m for m in relevant if _flag(m) in _ABNORMAL]
        evidence.primary_facts = [_marker_fact(m) for m in flagged[: budget.primary]]
        evidence.checked_without_concern = [m.name or m.key for m in relevant if _flag(m) not in _ABNORMAL][:5]
        evidence.supporting_facts = [_marker_fact(m) for m in flagged[budget.primary: budget.primary + budget.supporting]]
    elif mode != QUESTIONNAIRE_LOOKUP:
        named = [m for m in markers if m.key in requested]
        if not named:
            # "my sugar" asks for the glucose family: use whichever glucose the report stores.
            fam = set().union(*(_family(c) for c in requested)) if requested else set()
            named = [m for m in markers if m.key in fam]
        cap = min(3, max(budget.primary, len({m.key for m in named}))) if named else budget.primary
        primary = named[:cap] or ([m for m in markers if _flag(m) in _ABNORMAL] or markers)[: budget.primary]
        evidence.primary_facts = [_marker_fact(m) for m in primary]
        primary_keys = {m.key for m in primary}
        supporting_codes = [c for c in [*carried, *(context.reasoning_context_codes or [])] if c not in primary_keys]
        # Markers carried from the conversation are kept whatever their flag: they are what
        # the follow-up is being compared with.
        supporting = [m for m in markers if m.key in supporting_codes and (_flag(m) in _ABNORMAL or m.key in carried)]
        if not supporting:
            supporting = [m for m in markers if m.key not in primary_keys and _flag(m) in _ABNORMAL
                          and _same_domain(m.key, primary_keys)]
        evidence.supporting_facts = [_marker_fact(m) for m in supporting[: budget.supporting]]
        if len(evidence.supporting_facts) < budget.supporting:
            domains = {d.code for d in (domain_for_entity(k) for k in primary_keys) if d}
            aligned = [r for r in context.bio_ai_risks or [] if _elevated(r) and _risk_in_domains(r.code, domains)]
            room = budget.supporting - len(evidence.supporting_facts)
            evidence.supporting_facts += [_risk_fact(r) for r in aligned[:room]]

    facts_now = [*evidence.primary_facts, *evidence.supporting_facts]
    has_bio = any(str(fact.get("source") or "").startswith("Bio-AI") for fact in facts_now)
    has_blood = any(fact.get("source") == "measured blood result" for fact in facts_now)
    if context.bio_ai_risks and not has_bio and re.search(r"\brisk\b", message or "", re.I):
        elevated = [risk for risk in context.bio_ai_risks if _elevated(risk)]
        if elevated:
            if not evidence.primary_facts:
                evidence.primary_facts = [_risk_fact(risk) for risk in elevated[: budget.primary]]
                evidence.supporting_facts = [
                    _marker_fact(marker) for marker in markers if _flag(marker) in _ABNORMAL
                ][: budget.supporting]
            else:
                room = max(budget.supporting, 1)
                evidence.supporting_facts = [
                    *evidence.supporting_facts,
                    *[_risk_fact(risk) for risk in elevated[:room]],
                ]
            if not has_blood and markers:
                evidence.supporting_facts = [
                    *[_marker_fact(marker) for marker in markers if _flag(marker) in _ABNORMAL][: budget.supporting],
                    *evidence.supporting_facts,
                ]
    if mode == LOOKUP and (context.report_patterns or patterns):
        patterns_all = context.report_patterns or patterns
        # Enough to say whether this value is a major or a minor part of the picture.
        asked = {f.get("code") for f in evidence.primary_facts}
        evidence.other_notable = [
            p["pattern"] for p in patterns_all
            if not asked & {f["code"] for f in p["out_of_range"]}
        ][:3]
    whole_picture = mode in {OVERVIEW, PRIORITIZATION, BIO_AI} or "overall_health" in (semantic.get("health_topics") or [])
    if whole_picture:
        evidence.patterns = patterns[:5]
        evidence.reassuring = reassuring[:4]
    elif mode not in {LOOKUP, QUESTIONNAIRE_LOOKUP}:
        # Focused question: only the patterns its findings belong to, and the reassuring
        # systems those findings sit next to.
        codes = {f.get("code") for f in [*evidence.primary_facts, *evidence.supporting_facts] if f.get("code")}
        wanted = theme_codes_for(codes)
        evidence.patterns = [p for p in patterns if p["pattern"] in wanted][:2]
        evidence.reassuring = [r for r in reassuring if r["system"] in wanted][:2]

    # ---- trend for the primary fact
    change_question = bool(re.search(r"\b(changed|earlier|previous|over time|from my)\b", message or "", re.I))
    if (budget.trend or change_question) and not evidence.trend_facts:
        primary_codes = {f.get("code") for f in evidence.primary_facts}
        for row in context.comparisons or []:
            if row.previous_value is None or row.current_value is None:
                continue
            if row.topic in primary_codes or (change_question and (not primary_codes or row.topic in primary_codes or True)):
                evidence.trend_facts.append(_trend_fact(row))
        seen = {t["code"] for t in evidence.trend_facts}
        for base in context.baselines or []:
            if base.entity in primary_codes and base.entity not in seen and base.previous is not None and base.observations >= 2:
                evidence.trend_facts.append({
                    "code": base.entity, "previous": base.previous, "latest": base.latest,
                    "change": round(base.latest - base.previous, 4) if base.latest is not None else None,
                    "direction": base.direction, "unit": base.unit,
                })
        limit = budget.trend or (1 if change_question else 0)
        evidence.trend_facts = evidence.trend_facts[:limit]

    # ---- one uncertainty that changes interpretation
    if budget.missing:
        primary_codes = {f.get("code") for f in evidence.primary_facts}
        present = {m.key for m in markers}
        asked = set(requested) | set(topics.markers)
        for item in context.missing or []:
            # Only a gap in what was actually asked, and not when a sibling measurement answers
            # it (fasting glucose missing but glucose present).
            if item.key not in asked or (_family(item.key) & present) or (item.key == "bio_ai" and context.bio_ai_risks):
                continue
            evidence.uncertainty_facts.append({
                "code": item.key,
                "name": item.name,
                "reason": item.reason,
                "note": "Not in the evidence selected for this question. Do not say it is absent from the member's records.",
            })
            break
        if "glucose" in present and {"glucose", "fasting_blood_glucose"} & asked and "fasting_blood_glucose" not in present:
            evidence.uncertainty_facts.append({
                "code": "glucose",
                "note": "The report lists glucose without saying whether the sample was fasting; mention it only if it changes the interpretation.",
            })

    # ---- questionnaire as reasoning context (never the whole questionnaire)
    selection = QuestionnaireSelection()
    if budget.questionnaire and (context.questionnaire or context.questionnaire_instances or _recent(context)):
        entity_codes = [f.get("code") for f in [*evidence.primary_facts, *evidence.supporting_facts] if f.get("code")]
        planned_keys = questionnaire_keys_for(topics) if (topics.concepts or topics.markers or topics.bio_ai) else []
        subject_keys = (
            [k for c in topics.concepts for k in (concept_spec(c).questionnaire_keys if concept_spec(c) else ())]
            if behavioural else []
        )
        selection = select_questionnaire_context(
            message,
            entities=entity_codes,
            domains=list(context.domains or []),
            questionnaire=context.questionnaire_instances or context.questionnaire,
            review=mode in {OVERVIEW, PRIORITIZATION} and not planned_keys,
            recent_messages=_recent(context),
            budget=budget.questionnaire,
            keys=planned_keys or None,
            subject_keys=subject_keys,
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

    # ---- strategy variants from the shape of the selected evidence
    marker_facts = [f for f in evidence.primary_facts if f.get("source") == "measured blood result"]
    if len(marker_facts) >= 2 and mode in {EXPLANATION, CAUSES, ASSESSMENT, RISK, LOOKUP}:
        evidence.extra_guidance.append(MULTI_MARKER_GUIDANCE)
    facts = [*evidence.primary_facts, *evidence.supporting_facts]
    if any(f.get("source", "").startswith("Bio-AI") for f in facts) and any(
        f.get("source") == "measured blood result" for f in facts
    ):
        evidence.extra_guidance.append(CROSS_SOURCE_GUIDANCE)
    if getattr(context, "conversation_turn", None) in _FOLLOW_UP_TURNS:
        evidence.extra_guidance.append(FOLLOW_UP_GUIDANCE)

    # ---- the user's premise versus the measured record
    evidence.premise_check = _premise_check(semantic.get("premise"), markers, context.bio_ai_risks or [])

    # ---- observability (developer trace only)
    retrieved_facts = len(context.markers or []) + len(context.bio_ai_risks or []) + len(context.facts or [])
    selected = len(evidence.primary_facts) + len(evidence.supporting_facts) + len(evidence.trend_facts)
    evidence.trace = {
        "response_mode": mode,
        "evidence_codes": list(dict.fromkeys(
            f.get("code") for f in [*evidence.primary_facts, *evidence.supporting_facts] if f.get("code")
        )),
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


_FOLLOW_UP_TURNS = {"FOLLOW_UP_QUESTION", "REFERENCE_RESOLUTION", "CORRECTION", "ANSWER_TO_ASSISTANT", "CLARIFICATION"}


_FAMILIES = (
    {"glucose", "fasting_blood_glucose", "postprandial_glucose"},
    {"cholesterol", "total_cholesterol"},
)


def _family(code: str) -> set[str]:
    for family in _FAMILIES:
        if code in family:
            return family - {code}
    return set()


def _conversation_codes(context: HealthContext) -> list[str]:
    """Supporting markers carried in: from earlier turns, then interpretation-changing ones."""
    semantic = getattr(context, "semantic_plan", None) or {}
    return list(dict.fromkeys([*(semantic.get("conversation_markers") or []), *(semantic.get("related_markers") or [])]))


def _trend_fact(row) -> dict:
    """Previous -> latest with dates and the exact numeric change (no rounding of stored values)."""
    change = row.absolute_delta if row.absolute_delta is not None else round(row.current_value - row.previous_value, 4)
    fact = {
        "code": row.topic,
        "previous": row.previous_value,
        "previous_date": str(row.previous_date) if row.previous_date else None,
        "latest": row.current_value,
        "latest_date": str(row.current_date) if row.current_date else None,
        "change": change,
        "percent_change": round(row.percentage_change, 1) if row.percentage_change is not None else None,
        "direction": row.direction or ("up" if change > 0 else "down" if change < 0 else "unchanged"),
    }
    return {k: v for k, v in fact.items() if v is not None}


def _semantic_topics(semantic: dict) -> TopicMatch:
    return TopicMatch(
        markers=list(semantic.get("markers") or []),
        bio_ai=list(semantic.get("bio_ai") or []),
        concepts=list(semantic.get("concepts") or []),
        domains=list(semantic.get("domains") or []),
    )


def _premise_check(premise: dict | None, markers, risks) -> dict | None:
    """Reconcile what the member assumed ("why is my HbA1c high") with the measurement."""
    if not premise:
        return None
    code, claimed = premise.get("topic"), premise.get("claimed")
    marker = next((m for m in markers if m.key == code), None)
    if marker is not None:
        status = _flag(marker) or "unknown"
        holds = (claimed == "high" and status in {"high", "critical"}) or (claimed == "low" and status == "low") or (
            claimed == "abnormal" and status in _ABNORMAL)
        if holds or status == "unknown":
            return None
        return {
            "user_assumed": f"{marker.name or code} is {claimed}",
            "latest_measurement": _marker_fact(marker),
            "instruction": (
                "The latest measurement does not match the user's assumption. Say so first and kindly, with the "
                "value, then offer to compare with an older report if that is what they meant. Do not explain "
                "causes of a result the member does not have."
            ),
        }
    if code == "bio_ai" and risks:
        return None  # the assessment exists; its elevated risks are in the evidence
    if code and not any(r.code == code for r in risks):
        return {
            "user_assumed": f"{code.replace('_', ' ')} is {claimed}",
            "latest_measurement": None,
            "instruction": "This result was not found in the member's records. Say that, and do not guess a value.",
        }
    return None


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
    if context.markers or context.bio_ai_risks:
        return True
    # Habit questions ("am I active enough?") can be answered from questionnaire data alone.
    semantic = getattr(context, "semantic_plan", None) or {}
    return semantic.get("personalization") == "REQUIRED" and bool(
        context.questionnaire or context.questionnaire_instances
    )


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


def build_clinical_evidence_brief(context: HealthContext, *, primary_source: str | None) -> dict:
    """Facts for one answer. Laboratory status stays separate from clinical importance.

    Provider critical flags are kept first. Other out-of-range results are grouped by the
    existing health-domain map, in report order. This is a presentation limit, not a new
    clinical score.
    """
    primary = primary_source or "unspecified"
    if primary == "bio_ai":
        from app.pipeline.report_explainer import related_blood_results

        ranked = sorted(context.bio_ai_risks or [], key=lambda r: -(getattr(r, "score", None) or 0))
        assessments = []
        for risk in ranked:
            fact = _risk_fact(risk)
            linked = related_blood_results(risk, context.markers or [])
            if linked:
                fact["related_blood_results"] = linked
            assessments.append(fact)
        return {
            "primary_source": "bio_ai",
            "kind": "risk_estimate",
            # Every assessment in the report: the answer may name only these.
            "assessments": assessments,
            "note": "These are model risk estimates, not laboratory measurements and not diagnoses.",
        }
    markers = list(context.markers or [])
    critical = [marker for marker in markers if _flag(marker) == "critical"]
    other = [marker for marker in markers if _flag(marker) in {"high", "low"}]
    ordered = critical + [marker for marker in other if marker not in critical]
    grouped: dict[str, list] = {}
    for marker in ordered:
        domain = domain_for_entity(marker.key)
        grouped.setdefault(domain.code if domain else "other", []).append(marker)
    from app.pipeline.clinical_thresholds import clinical_notes

    notes = clinical_notes([m for m in ordered if m.value is not None])
    # The group holding the most important guideline finding is explained first.
    lead_keys = [note.marker.key for note in notes]
    grouped = dict(sorted(
        grouped.items(),
        key=lambda item: min((lead_keys.index(m.key) for m in item[1] if m.key in lead_keys), default=len(lead_keys)),
    ))
    patterns = []
    for code, rows in list(grouped.items())[:4]:
        facts = []
        for marker in rows[:4]:
            fact = _marker_fact(marker)
            fact["laboratory_status"] = fact.pop("status", None)
            direction = _trend_direction(context, marker.key)
            if direction:
                fact["earlier_report"] = direction
            facts.append(fact)
        patterns.append({"group": code, "measured_results": facts})
    in_range = [
        marker.name
        for marker in markers
        if _flag(marker) == "normal" and marker.name
    ][:6]
    return {
        "primary_source": "blood_report" if primary == "blood_report" else primary,
        "kind": "measured_laboratory_result",
        "patterns": patterns,
        "within_laboratory_range": in_range,
        "all_listed_results_within_range": bool(markers) and not ordered,
        # Published guideline ranges (ADA, NCEP, ACC/AHA, Endocrine Society): how far outside.
        "guideline_notes": [note.text for note in notes],
        "note": (
            "laboratory_status describes the laboratory reference range only. "
            "It is not a clinical-importance score. Do not invent results that are not listed."
        ),
    }


def _trend_direction(context: HealthContext, key: str) -> str | None:
    for row in context.comparisons or []:
        topic = str(getattr(row, "topic", "") or "")
        if topic == key or topic.replace(" ", "_") == key:
            direction = getattr(row, "direction", None)
            return str(direction) if direction else None
    return None
