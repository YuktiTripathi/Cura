"""Semantic health planning: what is the user trying to accomplish?

Every chat turn is decomposed into a small typed plan:

    reasoning goal(s)  x  health topic(s)  x  personalization  x  time need

The plan describes OPERATIONS, never medical conclusions. Jev (the existing routing
model call) may supply the goal / personalization / time scope as validated enum
answers in the same request; this module supplies the deterministic reading used as
the fallback and as the application-side check. Topic extraction, the evidence
registry and source policy are deterministic configuration (``health_topics``).

Goal detection works on general linguistic features - interrogatives, comparatives,
evaluative and advisory words - per clause, so unseen phrasings of the same task land
on the same goal. It is not a table of known questions.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.pipeline.health_topics import TopicMatch, extract_topics, is_behavioural_only
from app.pipeline.language import normalize_for_intent


class ReasoningGoal(str, Enum):
    lookup = "LOOKUP"
    explain = "EXPLAIN"
    causes = "CAUSES"
    assess = "ASSESS"
    compare = "COMPARE"
    prioritize = "PRIORITIZE"
    action = "ACTION"
    synthesize = "SYNTHESIZE"
    risk = "RISK"
    general_education = "GENERAL_EDUCATION"
    document_lookup = "DOCUMENT_LOOKUP"
    follow_up = "FOLLOW_UP"


class Personalization(str, Enum):
    none = "NONE"
    optional = "OPTIONAL"
    required = "REQUIRED"


class TemporalNeed(str, Enum):
    none = "NONE"
    current = "CURRENT"
    historical = "HISTORICAL"
    trend = "TREND"
    comparison = "COMPARISON"


class HealthSource(str, Enum):
    """Capabilities the application can actually retrieve. Nothing else is accepted."""

    blood = "blood"
    bio_ai = "bio_ai"
    questionnaire = "questionnaire"
    profile = "profile"
    goals = "goals"
    history = "history"
    conversation = "conversation"
    uploaded_document = "uploaded_document"
    medical_knowledge = "medical_knowledge"


class ReasoningTask(str, Enum):
    retrieve_current_value = "retrieve_current_value"
    retrieve_history = "retrieve_history"
    compare_values = "compare_values"
    assess_against_reference = "assess_against_reference"
    identify_priority = "identify_priority"
    identify_relevant_lifestyle_gaps = "identify_relevant_lifestyle_gaps"
    identify_supportive_habits = "identify_supportive_habits"
    combine_blood_and_bio_ai = "combine_blood_and_bio_ai"
    select_relevant_questionnaire_context = "select_relevant_questionnaire_context"
    reconcile_user_premise = "reconcile_user_premise"
    identify_uncertainty = "identify_uncertainty"
    explain_general_concept = "explain_general_concept"


class ExecutionPath(str, Enum):
    """Latency class. FAST never pays for broad personalized reasoning."""

    fast = "FAST"
    standard = "STANDARD"
    deep = "DEEP"


class ResponseShape(str, Enum):
    direct_fact = "DIRECT_FACT"
    explanation = "EXPLANATION"
    possible_explanations = "POSSIBLE_EXPLANATIONS"
    personalized_assessment = "PERSONALIZED_ASSESSMENT"
    comparison = "COMPARISON"
    prioritization = "PRIORITIZATION"
    action_plan = "ACTION_PLAN"
    overview = "OVERVIEW"
    risk_explanation = "RISK_EXPLANATION"
    general_education = "GENERAL_EDUCATION"
    clarification = "CLARIFICATION"


class SemanticHealthPlan(BaseModel):
    primary_goal: ReasoningGoal
    secondary_goals: list[ReasoningGoal] = Field(default_factory=list)
    health_topics: list[str] = Field(default_factory=list)
    personalization: Personalization = Personalization.none
    temporal_requirement: TemporalNeed = TemporalNeed.none
    required_sources: list[HealthSource] = Field(default_factory=list)
    optional_sources: list[HealthSource] = Field(default_factory=list)
    reasoning_tasks: list[ReasoningTask] = Field(default_factory=list)
    response_shape: ResponseShape = ResponseShape.explanation
    execution_path: ExecutionPath = ExecutionPath.standard
    clarification_needed: bool = False
    clarification_reason: str | None = None
    premise: dict | None = None  # {"topic": "hba1c", "claimed": "high"} - checked later against data
    planner: str = "deterministic"  # deterministic | jev+deterministic
    # False when no goal cue was found and the goal is only the neutral default.
    goal_from_cue: bool = Field(default=True, exclude=True)

    # Internal detail kept off the wire contract.
    markers: list[str] = Field(default_factory=list, exclude=True)
    bio_ai: list[str] = Field(default_factory=list, exclude=True)
    concepts: list[str] = Field(default_factory=list, exclude=True)
    domains: list[str] = Field(default_factory=list, exclude=True)

    def trace(self) -> dict:
        return {
            "primary_goal": self.primary_goal.value,
            "secondary_goals": [g.value for g in self.secondary_goals],
            "health_topics": list(self.health_topics),
            "personalization_requirement": self.personalization.value,
            "temporal_requirement": self.temporal_requirement.value,
            "required_sources": [s.value for s in self.required_sources],
            "optional_sources": [s.value for s in self.optional_sources],
            "reasoning_tasks": [t.value for t in self.reasoning_tasks],
            "response_shape": self.response_shape.value,
            "execution_path": self.execution_path.value,
            "clarification_needed": self.clarification_needed,
            "clarification_reason": self.clarification_reason,
            "premise": self.premise,
            "planner": self.planner,
        }


# ---------------------------------------------------------------- linguistic features

def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


# Cue families describe the SHAPE of a request, not particular questions. Each list is
# small, generic and multilingual (English, Indian English, romanized Hindi).
_CUES: dict[ReasoningGoal, tuple[re.Pattern[str], ...]] = {
    ReasoningGoal.compare: (
        _rx(r"\b(?:(?:has|have|what'?s|what has|what|anything)\s+(?:[\w-]+\s+){0,3}changed|changed (?:since|from)|improved|improving|worse|worsened|worsening|since|compared?|comparison|versus|vs\.?|better than|worse than|become (?:better|worse))\b"),
        _rx(r"\b(?:went|gone|going|got|has|have)\s+(?:up|down|higher|lower|better|worse)\b"),
        _rx(r"\b(?:increased|decreased|dropped|rose|risen|fallen|trend|over time|than before|than last time|from last time)\b"),
    ),
    ReasoningGoal.prioritize: (
        _rx(r"\b(?:focus(?:ing)? on|fix first|work on first|first|firstly|priorit\w*|most important|matters? most|biggest|top|main thing|start with|where (?:do|should) i start|which one|only (?:change|do|fix) one|one thing|pehle|sabse)\b"),
        _rx(r"\b(?:most|really) (?:matters?|important|relevant|useful)\b"),
        _rx(r"\b(?:matters? (?:most|less|least)|probably matter|less important|least important|least worrying|(?:needs?|deserves?) (?:the )?most attention|most attention|top \d+|top (?:three|two|five))\b"),
        _rx(r"\bwhich (?:of my|habit|change|result|thing)\w*\b.*\b(?:most|first)\b"),
    ),
    ReasoningGoal.risk: (
        _rx(r"\b(?:worr(?:y|ied|ying)|dangerous|serious|scary|scared|alarming|risk of|at risk|chance of|implications?|what could (?:this|it|that) (?:mean|lead)|lead to|concerned|warrants? (?:concern|attention)|darr?na)\b"),
    ),
    ReasoningGoal.causes: (
        _rx(r"\b(?:why|reason|reasons|cause[sd]?|causing|how come|what explains|what could explain|kyun|kyon|kyu)\b"),
    ),
    ReasoningGoal.assess: (
        _rx(r"\b(?:enough|okay|ok|fine|alright|good|bad|healthy|unhealthy|normal|concerning|on track|too (?:high|low|much|little)|sufficient|adequate|thik|theek|sahi)\b"),
        _rx(r"\bdoing (?:well|good|okay|fine|right)\b"),
        _rx(r"\bshould i be (?:doing|getting|eating|sleeping|walking|moving) (?:more|less)\b"),
        _rx(r"\b(?:am i|is my|are my)\b.*\b(?:enough|okay|ok|fine|good|bad|healthy|normal|high|low)\b"),
    ),
    ReasoningGoal.action: (
        _rx(r"\b(?:what (?:should|can|do) i do|what to do|how (?:can|do|should|to) (?:i )?(?:improve|lower|reduce|raise|increase|fix|manage|control|bring|get|boost|change)|improve|lower|reduce|raise|boost|fix|tips?|steps?|plan|recommend\w*|suggest\w*|advice|advise|work on|change|changes|what else|kaise|kya karu|kya karna)\b"),
    ),
    ReasoningGoal.synthesize: (
        _rx(r"\b(?:pay attention to|stand(?:s)? out|reassuring|good news|(?:looks?|is|are) (?:fine|okay|ok|good) in my|anything (?:in|on|from) my|anything i should|what do my (?:reports|results) (?:say|show)|overall|overview|big picture|in general how|how am i doing|fit together|together|all my|everything|whole|complete|summar\w*|both|combined?)\b"),
    ),
    ReasoningGoal.explain: (
        _rx(r"\b(?:because of|due to|caused by|related to|linked to|connected (?:to|with)|is that why|is it from|has to do with)\b"),
        _rx(r"\b(?:mean|means|meaning|explain|interpret\w*|understand|what does|what do|tell me about|how can both|both be true|makes? sense|matlab)\b"),
    ),
    ReasoningGoal.lookup: (
        _rx(r"\b(?:what(?:'s| is| was| are| were) my|show(?: me)? my|tell me my|my latest|value|level|reading|result|score|what did i (?:say|report|answer|write)|when was)\b"),
    ),
    ReasoningGoal.document_lookup: (
        _rx(r"\b(?:uploaded|upload|pdf|attached|attachment|this document|the document|my document|scan)\b"),
    ),
}

# Primary-goal precedence inside the clause that carries the question.
_PRECEDENCE = (
    ReasoningGoal.document_lookup,
    ReasoningGoal.prioritize,
    ReasoningGoal.risk,
    ReasoningGoal.causes,
    ReasoningGoal.assess,
    ReasoningGoal.compare,
    ReasoningGoal.action,
    ReasoningGoal.explain,
    ReasoningGoal.synthesize,
    ReasoningGoal.lookup,
)

_SELF = _rx(
    r"\b(?:i|i'm|im|i've|ive|i'd|me|my|mine|myself|am i|do i|should i|mera|meri|mere|mujhe|main|hum)\b"
)
_HYPOTHETICAL = _rx(
    r"\b(?:(?:if|suppose|supposing|what if|say)\s+my\b|in general|generally|typically|usually|someone|somebody|a person|people|anyone|if (?:a|an|someone)|"
    r"what is (?:a|an)\b|what are\b|normal range for)\b"
)
_EXPLICIT_VALUE = _rx(r"\b(?:of|at|is|=)\s*\d+(?:\.\d+)?\s*(?:%|mg|ng|mmol|g/dl|iu|pg|u/l)?\b")
# A message that is essentially a number to judge ("Is 120 bad?", "140 ok?") with no named
# measure. "Top 3 things", "last 2 reports" are counts, not measurements.
_BARE_NUMBER = _rx(
    r"^\s*(?:is|are|what about|and|my)?\s*(?:a |an )?\d+(?:\.\d+)?\s*(?:%|mg/?dl|mmol/?l|units?)?\s*"
    r"(?:bad|good|ok|okay|high|low|normal|fine|dangerous|safe|too high|too low)?\s*\??\s*$"
)
_REFERRING = _rx(r"\b(?:it|this|that|these|those|them|they|same)\b")
_TREND = _rx(r"\b(?:trend|over time|improving|getting (?:better|worse)|progress|track(?:ing)?|history|historical)\b")
_HISTORICAL = _rx(r"\b(?:previous|last time|before|earlier|older|old report|last year|past)\b")
_DIRECTION = _rx(
    r"\b(?:why (?:is|are) my|my)\s+([a-z0-9 \-]{2,30}?)\s+(?:is |are |so |still |that )?(?:still )?"
    r"(high|higher|elevated|raised|low|lower|abnormal|bad|out of range)\b"
)
_STILL_HIGH = _rx(r"\b(?:still|so)\s+(high|low|elevated)\b")
# "this result", "my report": the member's own record even when no marker is named.
_RECORD_NOUN = _rx(r"\b(?:result|results|report|reports|values|numbers|labs?|blood ?work|test results)\b")
_IMPLICITLY_PERSONAL = {ReasoningGoal.prioritize, ReasoningGoal.compare, ReasoningGoal.synthesize}
_DEFINITION = _rx(r"^\s*(?:what (?:is|are) (?:a|an|the)?\s*\w+\??$|define|meaning of)")
_NEEDS_SUBJECT = {
    ReasoningGoal.lookup, ReasoningGoal.compare, ReasoningGoal.explain, ReasoningGoal.risk,
    ReasoningGoal.causes, ReasoningGoal.assess, ReasoningGoal.action,
}
_WORD_HIGH = {"high": "high", "higher": "high", "elevated": "high", "raised": "high", "low": "low", "lower": "low", "abnormal": "abnormal", "bad": "abnormal", "out of range": "abnormal"}


def _clauses(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+|\s*;\s*", text) if p.strip()]
    return parts or [text]


def _goals_in(text: str) -> list[ReasoningGoal]:
    found = [goal for goal in _PRECEDENCE if any(p.search(text) for p in _CUES.get(goal, ()))]
    # "how am I doing overall" is a synthesis, not an assessment of one thing.
    if ReasoningGoal.synthesize in found and ReasoningGoal.assess in found and re.search(r"\bdoing\b", text, re.I) and not re.search(r"\bdoing (?:well|good)\b", text, re.I):
        found.remove(ReasoningGoal.assess)
    return found


def _question_clause(clauses: list[str]) -> str:
    asked = [c for c in clauses if c.endswith("?") or re.match(r"^(?:what|why|how|is|are|am|do|does|should|can|could|which|where|when|will|kya|kaise|kyun)\b", c, re.I)]
    return asked[-1] if asked else clauses[-1]


def infer_goals(message: str) -> tuple[ReasoningGoal, list[ReasoningGoal]]:
    text = normalize_for_intent(message or "")
    clauses = _clauses(text)
    asked = _question_clause(clauses)
    primary_candidates = _goals_in(asked)
    every = _goals_in(text)
    if primary_candidates:
        primary = primary_candidates[0]
    elif every:
        primary = every[0]
    else:
        primary = ReasoningGoal.explain  # no cue: a neutral default, see goal_from_cue
    # Lookup only wins when nothing richer is asked of the value.
    if primary == ReasoningGoal.lookup and len(primary_candidates) > 1:
        primary = primary_candidates[1]
    secondary = [g for g in dict.fromkeys([*primary_candidates, *every]) if g != primary and g != ReasoningGoal.lookup]
    # Contrast between two sources ("my sugar is fine, so why is my risk high") needs synthesis.
    return primary, secondary[:3]


def _premise(text: str, topics: TopicMatch) -> dict | None:
    """A presupposed direction about a named marker: 'why is my HbA1c high'."""
    targets = [*topics.markers, *topics.bio_ai]
    if not targets:
        return None
    match = _DIRECTION.search(text) or _STILL_HIGH.search(text)
    if not match:
        return None
    word = match.group(match.lastindex).lower()
    topic = targets[0]
    if match.lastindex and match.lastindex >= 2:
        named = extract_topics(match.group(1))
        near = [*named.markers, *named.bio_ai]
        if near:
            topic = near[0]
    return {"topic": topic, "claimed": _WORD_HIGH.get(word, "abnormal")}


# ---------------------------------------------------------------- planning

def build_semantic_plan(
    message: str,
    *,
    conversation_entities: list[str] | None = None,
    prior_personal: bool = False,
    has_documents: bool = False,
    jev_goal: str | None = None,
    jev_personalization: str | None = None,
    jev_temporal: str | None = None,
) -> SemanticHealthPlan:
    from app.pipeline.evidence_planner import plan_evidence

    text = normalize_for_intent(message or "")
    topics = extract_topics(message, conversation_entities=None)
    referring = bool(_REFERRING.search(text)) and topics.empty
    if referring and conversation_entities:
        topics = extract_topics(message, conversation_entities=conversation_entities)

    primary, secondary = infer_goals(message)
    planner = "deterministic"
    if jev_goal:
        try:
            jev_primary = ReasoningGoal(jev_goal)
        except ValueError:
            jev_primary = None
        if jev_primary and jev_primary not in {ReasoningGoal.follow_up}:
            if jev_primary != primary:
                secondary = [g for g in [primary, *secondary] if g != jev_primary][:3]
            primary = jev_primary
            planner = "jev+deterministic"

    self_ref = bool(_SELF.search(text))
    conditional = bool(re.search(r"\b(?:if|suppose|supposing|what if)\s+my\b", text, re.I))
    # "What are the top 3 things I should work on?" is about the member: a generic phrasing
    # only signals general knowledge when the user does not refer to themselves.
    hypothetical = conditional or (bool(_HYPOTHETICAL.search(text)) and not self_ref)
    explicit_value = bool(_EXPLICIT_VALUE.search(text)) and not re.search(r"\bmy\b", text, re.I)

    # Personalization: does the answer depend on THIS member's data?
    if primary == ReasoningGoal.document_lookup or (has_documents and re.search(r"\b(?:document|pdf|uploaded|report i uploaded)\b", text, re.I)):
        personalization = Personalization.required
        primary = ReasoningGoal.document_lookup
    elif self_ref and not hypothetical:
        personalization = Personalization.required
    elif referring and (prior_personal or conversation_entities):
        personalization = Personalization.required
    elif ({primary, *secondary} & _IMPLICITLY_PERSONAL) and not hypothetical and not _DEFINITION.search(text) and (
        primary in _IMPLICITLY_PERSONAL or not topics.empty
    ):
        # "Which habit matters most right now?", "What has become worse?" - a ranking,
        # change or overview with no other subject is about the member asking.
        personalization = Personalization.required
    elif explicit_value or (hypothetical and not topics.empty):
        personalization = Personalization.optional
    else:
        personalization = Personalization.none
    if (
        personalization == Personalization.required
        and topics.empty
        and not (referring and conversation_entities)
        and not _RECORD_NOUN.search(text)
        and primary in {ReasoningGoal.explain, ReasoningGoal.causes, ReasoningGoal.risk, ReasoningGoal.lookup}
    ):
        # "I was sick when I took this test, does that matter?" - a question about a
        # circumstance, not about a named result: answer it, adding personal context only
        # if the routed plan already brings it.
        personalization = Personalization.optional
    if jev_personalization in {"NONE", "OPTIONAL", "REQUIRED"}:
        # The application stays authoritative: Jev may lower personalization, and may
        # raise it only when the message refers to the member at all.
        jev_level = Personalization(jev_personalization)
        if jev_level == Personalization.required and (self_ref or referring):
            personalization = jev_level
        elif jev_level != Personalization.required:
            personalization = jev_level if personalization != Personalization.required or not self_ref else personalization

    if personalization == Personalization.none and primary not in {ReasoningGoal.document_lookup}:
        secondary = [g for g in [primary, *secondary] if g not in {ReasoningGoal.general_education}][:3]
        primary = ReasoningGoal.general_education
        secondary = [g for g in secondary if g != primary]

    # Time need
    if primary == ReasoningGoal.compare or ReasoningGoal.compare in secondary:
        temporal = TemporalNeed.trend if _TREND.search(text) else TemporalNeed.comparison
    elif _TREND.search(text):
        temporal = TemporalNeed.trend
    elif _HISTORICAL.search(text):
        temporal = TemporalNeed.historical
    elif personalization == Personalization.required:
        temporal = TemporalNeed.current
    else:
        temporal = TemporalNeed.none
    if jev_temporal in {t.value for t in TemporalNeed} and personalization == Personalization.required:
        jev_t = TemporalNeed(jev_temporal)
        if jev_t != TemporalNeed.none:
            temporal = jev_t

    # Clarify only when meaning is missing AND neither the message nor the conversation
    # can supply it. Low router confidence is never a reason on its own.
    clarification_reason = None
    if topics.empty and not conversation_entities:
        if _BARE_NUMBER.match(text):
            clarification_reason = "number_without_measure"
        elif referring and primary in _NEEDS_SUBJECT and not self_ref:
            clarification_reason = "unresolved_reference"

    plan = SemanticHealthPlan(
        primary_goal=primary,
        secondary_goals=secondary,
        health_topics=topics.all,
        personalization=personalization,
        temporal_requirement=temporal,
        clarification_needed=clarification_reason is not None,
        clarification_reason=clarification_reason,
        premise=_premise(text, topics) if personalization == Personalization.required else None,
        planner=planner,
        goal_from_cue=bool(_goals_in(text)) or planner != "deterministic",
        markers=topics.markers,
        bio_ai=topics.bio_ai,
        concepts=topics.concepts,
        domains=topics.domains,
    )
    if plan.personalization == Personalization.required and topics.empty and not plan.clarification_needed:
        # "What should I change first?" / "How am I doing?" - the member's whole picture.
        plan.health_topics = ["overall_health"]
    plan_evidence(plan, topics)
    plan.response_shape = _shape(plan)
    plan.execution_path = _path(plan, topics)
    return plan


def _shape(plan: SemanticHealthPlan) -> ResponseShape:
    if plan.clarification_needed:
        return ResponseShape.clarification
    return {
        ReasoningGoal.lookup: ResponseShape.direct_fact,
        ReasoningGoal.explain: ResponseShape.explanation,
        ReasoningGoal.causes: ResponseShape.possible_explanations,
        ReasoningGoal.assess: ResponseShape.personalized_assessment,
        ReasoningGoal.compare: ResponseShape.comparison,
        ReasoningGoal.prioritize: ResponseShape.prioritization,
        ReasoningGoal.action: ResponseShape.action_plan,
        ReasoningGoal.synthesize: ResponseShape.overview,
        ReasoningGoal.risk: ResponseShape.risk_explanation,
        ReasoningGoal.general_education: ResponseShape.general_education,
        ReasoningGoal.document_lookup: ResponseShape.explanation,
        ReasoningGoal.follow_up: ResponseShape.explanation,
    }[plan.primary_goal]


def _path(plan: SemanticHealthPlan, topics: TopicMatch) -> ExecutionPath:
    if plan.clarification_needed:
        return ExecutionPath.fast
    if plan.primary_goal == ReasoningGoal.general_education or plan.personalization == Personalization.none:
        return ExecutionPath.fast
    if plan.primary_goal == ReasoningGoal.lookup and not plan.secondary_goals:
        return ExecutionPath.fast
    broad = plan.primary_goal in {ReasoningGoal.synthesize, ReasoningGoal.prioritize} and "overall_health" in plan.health_topics
    many = len([s for s in plan.required_sources if s != HealthSource.medical_knowledge]) >= 3 or len(plan.secondary_goals) >= 2
    if broad or many:
        return ExecutionPath.deep
    return ExecutionPath.standard


def behavioural_question(plan: SemanticHealthPlan) -> bool:
    return is_behavioural_only(TopicMatch(markers=plan.markers, bio_ai=plan.bio_ai, concepts=plan.concepts, domains=plan.domains))
