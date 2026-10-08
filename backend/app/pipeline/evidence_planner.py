"""Evidence planning: which personal evidence could change THIS answer?

Deterministic application code. Takes a ``SemanticHealthPlan`` (goal x topic x
personalization x time need) and selects a narrow set of validated capabilities,
then applies them to the existing ``QueryPlan`` flags that drive retrieval.

The model advises; the application decides. Only capabilities in
``SUPPORTED_SOURCES`` can ever be selected, and personal sources are only enabled
when the plan's personalization requirement allows them.
"""

from __future__ import annotations

import logging

from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.health_topics import (
    TopicMatch,
    evidence_bio_ai_for,
    evidence_markers_for,
    is_behavioural_only,
    questionnaire_keys_for,
)
from app.pipeline.semantic_plan import (
    ExecutionPath,
    HealthSource,
    Personalization,
    ReasoningGoal,
    ReasoningTask,
    SemanticHealthPlan,
    TemporalNeed,
)

logger = logging.getLogger("cura.semantic")

SUPPORTED_SOURCES = frozenset(HealthSource)
_PERSONAL = {
    HealthSource.blood,
    HealthSource.bio_ai,
    HealthSource.questionnaire,
    HealthSource.profile,
    HealthSource.goals,
    HealthSource.history,
    HealthSource.uploaded_document,
}
_EXPLAINING = {
    ReasoningGoal.explain,
    ReasoningGoal.causes,
    ReasoningGoal.assess,
    ReasoningGoal.risk,
    ReasoningGoal.action,
}
_EVALUATIVE = {
    ReasoningGoal.assess,
    ReasoningGoal.action,
    ReasoningGoal.causes,
    ReasoningGoal.prioritize,
    ReasoningGoal.risk,
    ReasoningGoal.explain,
}


def _add(bucket: list[HealthSource], *items: HealthSource) -> None:
    for item in items:
        if item in SUPPORTED_SOURCES and item not in bucket:
            bucket.append(item)


def plan_evidence(plan: SemanticHealthPlan, topics: TopicMatch) -> SemanticHealthPlan:
    """Fill required/optional sources and reasoning tasks. Narrow by default."""
    required: list[HealthSource] = []
    optional: list[HealthSource] = []
    tasks: list[ReasoningTask] = []
    goals = {plan.primary_goal, *plan.secondary_goals}

    if plan.personalization == Personalization.none:
        _add(required, HealthSource.medical_knowledge)
        tasks.append(ReasoningTask.explain_general_concept)
    elif plan.personalization == Personalization.optional:
        # "What does an HbA1c of 5.3 usually mean?" - answer generally; the member's
        # own record may add context but is never required.
        _add(required, HealthSource.medical_knowledge)
        if topics.markers:
            _add(optional, HealthSource.blood)
        tasks.append(ReasoningTask.explain_general_concept)
    elif plan.primary_goal == ReasoningGoal.document_lookup:
        _add(required, HealthSource.uploaded_document)
    else:
        whole_picture = "overall_health" in plan.health_topics or "overall_health" in topics.domains
        behavioural = is_behavioural_only(topics)
        if plan.primary_goal == ReasoningGoal.lookup and not plan.secondary_goals:
            # A value lookup reads exactly the record that holds the value.
            if topics.markers:
                _add(required, HealthSource.blood)
            if topics.bio_ai:
                _add(required, HealthSource.bio_ai)
            if behavioural:
                _add(required, HealthSource.questionnaire)
            tasks.append(ReasoningTask.retrieve_current_value)
        elif whole_picture:
            _add(required, HealthSource.blood, HealthSource.bio_ai)
            _add(optional, HealthSource.questionnaire, HealthSource.profile, HealthSource.goals)
            if goals & {ReasoningGoal.prioritize, ReasoningGoal.action}:
                # A plan or a priority is personal only with the member's habits in view.
                _add(required, HealthSource.questionnaire)
            tasks += [ReasoningTask.identify_priority, ReasoningTask.combine_blood_and_bio_ai]
        elif behavioural:
            # "Am I active enough?", "what habit should I change first?"
            _add(required, HealthSource.questionnaire)
            _add(optional, HealthSource.profile, HealthSource.goals)
            if goals & _EVALUATIVE:
                # Judging a habit "for my health" needs the member's current findings.
                _add(optional, HealthSource.blood, HealthSource.bio_ai)
            tasks += [ReasoningTask.select_relevant_questionnaire_context, ReasoningTask.identify_supportive_habits]
            if goals & {ReasoningGoal.prioritize, ReasoningGoal.action, ReasoningGoal.assess}:
                tasks.append(ReasoningTask.identify_relevant_lifestyle_gaps)
        else:
            if evidence_markers_for(topics):
                _add(required, HealthSource.blood)
            if topics.bio_ai:
                _add(required, HealthSource.bio_ai)
            elif evidence_bio_ai_for(topics) and goals & {ReasoningGoal.risk, ReasoningGoal.synthesize, ReasoningGoal.causes}:
                _add(optional, HealthSource.bio_ai)
            if topics.concepts:
                _add(required, HealthSource.questionnaire)
            elif goals & {ReasoningGoal.action, ReasoningGoal.causes, ReasoningGoal.prioritize, ReasoningGoal.assess} and questionnaire_keys_for(topics):
                _add(optional, HealthSource.questionnaire)
            if goals & {ReasoningGoal.action, ReasoningGoal.prioritize}:
                _add(optional, HealthSource.goals, HealthSource.profile)
            tasks += [ReasoningTask.retrieve_current_value, ReasoningTask.assess_against_reference]
            if HealthSource.questionnaire in required + optional:
                tasks.append(ReasoningTask.select_relevant_questionnaire_context)
            if HealthSource.blood in required and (HealthSource.bio_ai in required + optional):
                tasks.append(ReasoningTask.combine_blood_and_bio_ai)
        if plan.temporal_requirement in {TemporalNeed.historical, TemporalNeed.trend, TemporalNeed.comparison}:
            _add(required, HealthSource.history)
            tasks.append(ReasoningTask.retrieve_history)
            if plan.temporal_requirement != TemporalNeed.historical:
                tasks.append(ReasoningTask.compare_values)
        if plan.premise:
            tasks.append(ReasoningTask.reconcile_user_premise)
        if goals & {ReasoningGoal.causes, ReasoningGoal.risk}:
            tasks.append(ReasoningTask.identify_uncertainty)
        _add(optional, HealthSource.conversation)
    plan.required_sources = required
    plan.optional_sources = [s for s in optional if s not in required]
    plan.reasoning_tasks = list(dict.fromkeys(tasks))
    return plan


# ---------------------------------------------------------------- QueryPlan application


def _sources_to_fetch(semantic: SemanticHealthPlan) -> set[HealthSource]:
    """Optional sources are fetched only off the FAST path (they run concurrently)."""
    wanted = set(semantic.required_sources)
    if semantic.execution_path != ExecutionPath.fast:
        wanted |= set(semantic.optional_sources)
    return wanted & SUPPORTED_SOURCES


def _intent_for(semantic: SemanticHealthPlan, topics_markers: list[str], topics_bio: list[str]) -> IntentType:
    goal = semantic.primary_goal
    if goal == ReasoningGoal.compare:
        if topics_markers:
            return IntentType.trend
        if topics_bio:
            return IntentType.bio_ai_comparison
        # "What changed since last time?" - every marker with history, via the scenario path.
        return IntentType.health_scenario
    if goal == ReasoningGoal.lookup:
        if topics_markers:
            return IntentType.latest_result
        if topics_bio:
            return IntentType.bio_ai_score
        return IntentType.questionnaire_lookup
    if topics_markers:
        return IntentType.blood_marker_explanation
    if topics_bio:
        return IntentType.bio_ai_explanation
    # No single named measurement: an interpretive, multi-source personal answer.
    return IntentType.health_scenario


def reconcile_query_plan(plan: QueryPlan, semantic: SemanticHealthPlan) -> tuple[QueryPlan, list[str]]:
    """Make the routed QueryPlan consistent with the semantic plan.

    Only three corrections are made, all conservative:
      1. needless clarification -> answer (meaning was sufficient);
      2. a personal question routed as general (or to the whole-report summary when it
         asks something specific) -> personal, with narrow sources;
      3. a personal plan missing a required source -> that source is added.
    Existing personal plans are never widened beyond required/optional sources and
    never narrowed (their established behaviour is preserved).
    Returns the plan and the list of corrections applied (for tracing).
    """
    changes: list[str] = []
    if plan.document_ids or plan.intent == IntentType.casual_conversation:
        return plan, changes
    if plan.needs_user_uploaded:
        # "My blood reports" can be routed as an uploaded-document question. With no
        # document attached, the member's stored results must still be read.
        if HealthSource.blood in semantic.required_sources and not plan.needs_blood:
            plan = plan.model_copy(update={"needs_blood": True, "needs_supershyft": True, "knowledge_scope": KnowledgeScope.personal})
            changes.append("added_required:blood")
        return plan, changes
    if semantic.clarification_needed:
        return plan, changes
    personal_needed = semantic.personalization == Personalization.required
    clarifying = plan.intent == IntentType.ambiguous_clarification
    general_routed = plan.knowledge_scope == KnowledgeScope.general or not plan.needs_personal_data
    if not personal_needed:
        if clarifying:
            changes.append("clarification_removed:general_answer")
            plan = plan.model_copy(update={"intent": IntentType.general_health_question, "knowledge_scope": KnowledgeScope.general, "source": QuerySource.general, "needs_general": True})
        return plan, changes

    wanted = _sources_to_fetch(semantic)
    # The whole-report summary template answers "how am I doing?"; a specific question
    # ("am I active enough?", "what lifestyle change first?") routed there is re-planned.
    misrouted_summary = (
        plan.intent == IntentType.broad_health_summary
        and semantic.primary_goal != ReasoningGoal.synthesize
        and "overall_health" not in semantic.health_topics
    )
    if clarifying or general_routed or misrouted_summary:
        changes.append(
            "clarification_removed" if clarifying else "general_to_personal" if general_routed else "summary_to_focused"
        )
        intent = _intent_for(semantic, semantic.markers, semantic.bio_ai)
        topic = (semantic.markers or semantic.bio_ai or [None])[0]
        update = {
            "intent": intent,
            "knowledge_scope": KnowledgeScope.personal,
            "needs_supershyft": True,
            "needs_general": False,
            "topic": topic or plan.topic,
            "topic_name": (topic or "").replace("_", " ") or plan.topic_name,
            "requested_metrics": list(dict.fromkeys([*semantic.markers, *semantic.bio_ai])) or list(plan.requested_metrics or []),
            "domains": list(dict.fromkeys([*semantic.domains, *(plan.domains or [])])),
            "personal_reference": True,
            "semantic_scoped": True,
        }
        plan = plan.model_copy(update=update)
        plan.needs_blood = HealthSource.blood in wanted
        plan.needs_bio_ai = HealthSource.bio_ai in wanted
        plan.needs_questionnaire = HealthSource.questionnaire in wanted
        plan.needs_profile = HealthSource.profile in wanted
        plan.needs_goals = HealthSource.goals in wanted
        plan.history = HealthSource.history in wanted
        plan.needs_lifestyle = plan.needs_questionnaire and HealthSource.profile in wanted
        if plan.history and plan.time_scope in {None, "", "none"}:
            plan.time_scope = "previous"
    elif (
        plan.intent == IntentType.latest_result
        and semantic.primary_goal in _EXPLAINING
        and semantic.goal_from_cue
        and semantic.markers
    ):
        # "Help me understand my HbA1c result" asks for meaning, not just the number.
        changes.append("lookup_to_explanation")
        plan = plan.model_copy(update={"intent": IntentType.blood_marker_explanation, "answer_depth": plan.answer_depth})
    else:
        added = []
        flag_for = {
            HealthSource.blood: "needs_blood",
            HealthSource.bio_ai: "needs_bio_ai",
            HealthSource.questionnaire: "needs_questionnaire",
            HealthSource.profile: "needs_profile",
            HealthSource.goals: "needs_goals",
            HealthSource.history: "history",
        }
        extra = list(semantic.required_sources)
        if semantic.execution_path != ExecutionPath.fast and HealthSource.questionnaire in semantic.optional_sources:
            # Habits can change advice and the questionnaire read runs concurrently: fetch it.
            extra.append(HealthSource.questionnaire)
        for source in extra:
            attr = flag_for.get(source)
            if attr and not getattr(plan, attr):
                setattr(plan, attr, True)
                added.append(source.value)
        if added:
            changes.append("added_required:" + ",".join(added))
    if plan.needs_questionnaire and not plan.needs_blood and not plan.needs_bio_ai:
        plan.source = QuerySource.questionnaire
    elif plan.needs_blood and plan.needs_bio_ai:
        plan.source = QuerySource.mixed
    elif plan.needs_blood:
        plan.source = QuerySource.blood
    elif plan.needs_bio_ai:
        plan.source = QuerySource.bio_ai
    data_sources = []
    if plan.needs_blood:
        data_sources.append("blood_reports")
    if plan.needs_bio_ai:
        data_sources.append("bio_ai_report")
    if plan.needs_questionnaire:
        data_sources.append("questionnaire")
    if plan.needs_profile or plan.needs_goals:
        data_sources.append("lifestyle")
    if changes:
        plan.data_sources = list(dict.fromkeys([*data_sources, *(plan.data_sources or [])]))
        logger.info("semantic_reconcile changes=%s intent=%s sources=%s", changes, plan.intent.value, plan.data_sources)
    return plan, changes


def questionnaire_keys_for_plan(semantic: SemanticHealthPlan) -> list[str]:
    return questionnaire_keys_for(
        TopicMatch(markers=semantic.markers, bio_ai=semantic.bio_ai, concepts=semantic.concepts, domains=semantic.domains)
    )
