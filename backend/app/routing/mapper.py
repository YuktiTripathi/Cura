from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, QuerySource
from app.contracts.context_ref import ContextRef
from app.contracts.query import QueryPlan
from app.pipeline.intent import NAMES
from app.pipeline.ontology import canonicalize_metric_key, normalize_requested_metrics
from app.pipeline.query_planner import _apply_context_ref
from app.pipeline.questionnaire_intent import explicit_questionnaire_request
from app.pipeline.questionnaire_topics import questionnaire_topic
from app.pipeline.source_routing import annotate_plan
from app.pipeline.health_sources import sync_plan_sources
from app.pipeline.general_personalization import attach_general_personalization
from app.pipeline.operations import named_personal_sources
from app.pipeline.planner import attach_task_plan
from app.pipeline.response_planner import repair_report_level_plan
from app.pipeline.task_contract import apply_task_contract
from app.routing.model_tier import apply_answer_model_routing
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevSource, JevTimeRange


def force_general_plan(plan: QueryPlan) -> QueryPlan:
    return annotate_plan(
        plan.model_copy(
            update={
                "intent": IntentType.general_health_question,
                "source": QuerySource.general,
                "knowledge_scope": KnowledgeScope.general,
                "needs_blood": False,
                "needs_bio_ai": False,
                "needs_lifestyle": False,
                "needs_profile": False,
                "needs_goals": False,
                "needs_questionnaire": False,
                "needs_supershyft": False,
                "needs_general": True,
                "needs_user_uploaded": False,
                "needs_cross_source": False,
                "history": False,
                "compare": False,
                "time_scope": "none",
                "data_sources": [],
            }
        )
    )


def plan_from_jev(
    decision: JevDecision,
    message: str,
    *,
    follow_up_topic: str | None = None,
    follow_up_name: str | None = None,
    document_ids: list[str] | None = None,
    uploaded_document_count: int = 0,
    prior_source_mode: str | None = None,
    context_ref: ContextRef | None = None,
) -> QueryPlan:
    """Map a validated Jev decision onto the existing QueryPlan contract.

    document_ids / uploaded_document_count / prior_source_mode stay in the
    signature for resolve_plan compatibility. They are not re-interpreted by
    the legacy heuristic source router after a validated Jev decision.
    """
    del uploaded_document_count, prior_source_mode
    topic = _topic(decision, follow_up_topic)
    name = NAMES.get(topic or "", topic) or follow_up_name
    intent, scope, needs_blood, needs_bio, needs_life, history, compare = _flags(decision)
    needs_questionnaire = _needs_questionnaire(decision, message)
    source = _query_source(decision.source)
    if needs_questionnaire and source == QuerySource.lifestyle and not needs_life:
        source = QuerySource.questionnaire
    if scope == KnowledgeScope.general:
        source = QuerySource.general
    metrics: list[str] = []
    for item in decision.requested_metrics or decision.requested_entities:
        key = canonicalize_metric_key(item)
        if key and key not in metrics:
            metrics.append(key)
    plan = QueryPlan(
        intent=intent,
        source=source,
        knowledge_scope=scope,
        topic=topic,
        topic_name=name,
        history=history or decision.requires_historical_data,
        reports="relevant",
        answer_depth=AnswerDepth.focused if decision.requires_retrieval else AnswerDepth.simple,
        needs_blood=needs_blood,
        needs_bio_ai=needs_bio,
        needs_lifestyle=needs_life,
        needs_questionnaire=needs_questionnaire,
        compare=compare,
        follow_up=bool(follow_up_topic and not decision.requested_metrics),
        raw_message=message,
        needs_supershyft=scope == KnowledgeScope.personal
        and not decision.requires_clarification
        and decision.source != JevSource.uploaded_documents,
        needs_general=scope == KnowledgeScope.general,
        needs_user_uploaded=decision.requires_document_search
        or decision.source == JevSource.uploaded_documents,
        needs_cross_source=decision.source == JevSource.multiple_sources,
        time_scope=decision.time_range.value,
        requested_metrics=metrics,
    )
    # Ontology may canonicalize marker/entity names only. It must not change
    # source, personal-data dependency, or operation after a validated Jev route.
    plan = normalize_requested_metrics(plan)
    ids = list(document_ids or [])
    if context_ref:
        plan = _apply_context_ref(plan, context_ref)
        if context_ref.document_id and context_ref.document_id not in ids:
            ids.append(context_ref.document_id)
    plan.document_ids = ids
    plan.active_document_id = ids[0] if len(ids) == 1 else None

    plan.time_operation = _time_operation(decision)
    plan.needs_guidance = _needs_guidance(decision)
    plan.personal_reference = bool(decision.requires_personal_data)
    plan.medical_evidence_required = _needs_medical_evidence(decision) or plan.intent in {
        IntentType.blood_marker_explanation,
        IntentType.bio_ai_explanation,
        IntentType.nutrition_guidance,
        IntentType.report_explanation,
        IntentType.health_goal_progress,
    }
    plan.needs_profile = plan.intent in {
        IntentType.personal_profile,
        IntentType.health_goal_progress,
        IntentType.nutrition_guidance,
    } or plan.needs_lifestyle
    plan.needs_goals = plan.intent == IntentType.health_goal_progress
    if needs_questionnaire:
        q_topic = questionnaire_topic(message)
        if q_topic and not plan.topic:
            plan.topic = q_topic
            plan.topic_name = NAMES.get(q_topic, q_topic.replace("_", " "))
        if plan.needs_blood or plan.needs_bio_ai:
            plan.medical_evidence_required = True
    named = named_personal_sources(message)
    if plan.knowledge_scope == KnowledgeScope.personal or plan.needs_personal_data:
        if "blood" in named:
            plan.needs_blood = True
            plan.needs_supershyft = True
        if "bio_ai" in named:
            plan.needs_bio_ai = True
            plan.needs_supershyft = True
        if "questionnaire" in named:
            plan.needs_questionnaire = True
        if "goals" in named:
            plan.needs_goals = True
            plan.needs_profile = True
            plan.needs_supershyft = True
        if named >= {"blood", "bio_ai"} or len(named) >= 2:
            plan.source = QuerySource.mixed
            plan.needs_supershyft = True
            if decision.source == JevSource.multiple_sources or len(named) >= 2:
                plan.needs_cross_source = False
    plan.data_sources = _data_sources(plan)
    plan = attach_task_plan(sync_plan_sources(plan), message, decision=decision)
    plan = repair_report_level_plan(plan, message)
    plan = sync_plan_sources(plan)
    plan = attach_general_personalization(plan, message)
    return apply_answer_model_routing(plan, decision=decision)

def _time_operation(decision: JevDecision) -> str:
    if decision.operation == JevOperation.compare:
        return "compare"
    if decision.operation == JevOperation.trend:
        return "trend"
    if decision.time_range == JevTimeRange.previous:
        return "previous"
    if decision.time_range == JevTimeRange.latest:
        return "latest_marker"
    if decision.operation == JevOperation.summarize:
        return "latest_report"
    return "latest_marker"


def _needs_guidance(decision: JevDecision) -> bool:
    return decision.intent in {
        JevIntent.lab_result_interpretation,
        JevIntent.bio_ai_report_interpretation,
        JevIntent.nutrition_question,
        JevIntent.lifestyle_question,
        JevIntent.medical_risk_question,
        JevIntent.symptom_question,
        JevIntent.medication_question,
        JevIntent.preventive_health_question,
    } or decision.operation in {JevOperation.interpret, JevOperation.retrieve_and_explain}


def _needs_medical_evidence(decision: JevDecision) -> bool:
    return decision.intent in {
        JevIntent.general_health_question,
        JevIntent.medical_risk_question,
        JevIntent.symptom_question,
        JevIntent.medication_question,
        JevIntent.preventive_health_question,
        JevIntent.nutrition_question,
        JevIntent.lifestyle_question,
        JevIntent.fitness_question,
        JevIntent.lab_result_interpretation,
        JevIntent.bio_ai_report_interpretation,
        JevIntent.questionnaire_interpretation,
    } or decision.operation in {JevOperation.interpret, JevOperation.retrieve_and_explain}


def _data_sources(plan: QueryPlan) -> list[str]:
    sources: list[str] = []
    if plan.needs_blood:
        sources.append("blood_reports")
    if plan.needs_bio_ai:
        sources.append("bio_ai_report")
    if plan.needs_lifestyle or plan.needs_profile:
        sources.append("lifestyle")
    if plan.needs_goals:
        sources.append("health_goals")
    if plan.needs_user_uploaded:
        sources.append("uploaded_documents")
    if plan.needs_questionnaire:
        sources.append("questionnaire")
    return sources


def _topic(decision: JevDecision, follow_up_topic: str | None) -> str | None:
    for item in decision.requested_metrics or decision.requested_entities:
        key = canonicalize_metric_key(item)
        if key:
            return key
    return follow_up_topic


def _flags(decision: JevDecision) -> tuple[IntentType, KnowledgeScope, bool, bool, bool, bool, bool]:
    if decision.requires_clarification or decision.intent == JevIntent.clarification:
        return IntentType.ambiguous_clarification, KnowledgeScope.general, False, False, False, False, False
    if decision.intent == JevIntent.casual_conversation:
        return IntentType.casual_conversation, KnowledgeScope.general, False, False, False, False, False

    personal = decision.requires_personal_data
    if decision.intent == JevIntent.unsupported:
        return IntentType.missing_data, KnowledgeScope.general, False, False, False, False, False

    if not personal and not decision.requires_document_search:
        return IntentType.general_health_question, KnowledgeScope.general, False, False, False, False, False

    if decision.intent == JevIntent.personal_profile_lookup:
        entities = " ".join(
            (decision.requested_entities or []) + (decision.requested_metrics or [])
        ).lower()
        if "goal" in entities or decision.operation in {JevOperation.trend, JevOperation.compare}:
            return IntentType.health_goal_progress, KnowledgeScope.personal, True, True, True, True, True
        return IntentType.personal_profile, KnowledgeScope.personal, False, False, True, False, False

    if decision.intent in {JevIntent.questionnaire_lookup, JevIntent.questionnaire_interpretation}:
        mixed = decision.source == JevSource.multiple_sources
        history = decision.requires_historical_data
        needs_blood = mixed and _jev_mentions_blood(decision)
        needs_bio = mixed and _jev_mentions_bio(decision)
        if mixed and not needs_blood and not needs_bio:
            needs_blood = True
        if mixed:
            return IntentType.health_scenario, KnowledgeScope.personal, needs_blood, needs_bio, False, history, True
        return IntentType.questionnaire_lookup, KnowledgeScope.personal, False, False, False, history, history

    if decision.intent in {JevIntent.nutrition_question, JevIntent.lifestyle_question}:
        return (
            IntentType.nutrition_guidance,
            KnowledgeScope.personal,
            decision.source == JevSource.multiple_sources,
            decision.source == JevSource.multiple_sources,
            True,
            decision.requires_historical_data,
            decision.requires_historical_data,
        )

    if decision.intent in {
        JevIntent.bio_ai_report_lookup,
        JevIntent.bio_ai_report_interpretation,
    } or decision.source in {JevSource.bio_ai_report, JevSource.bio_ai_trends}:
        if decision.requires_historical_data or decision.source == JevSource.bio_ai_trends:
            return IntentType.bio_ai_comparison, KnowledgeScope.personal, False, True, False, True, True
        intent = (
            IntentType.bio_ai_explanation
            if decision.intent == JevIntent.bio_ai_report_interpretation
            or decision.operation in {JevOperation.interpret, JevOperation.retrieve_and_explain}
            else IntentType.bio_ai_score
        )
        return intent, KnowledgeScope.personal, False, True, False, False, False

    if decision.operation == JevOperation.summarize:
        mixed = decision.source == JevSource.multiple_sources
        bio = decision.source in {JevSource.bio_ai_report, JevSource.bio_ai_trends}
        return (
            IntentType.report_explanation,
            KnowledgeScope.personal,
            mixed or not bio,
            mixed or bio,
            False,
            False,
            False,
        )

    if decision.time_range == JevTimeRange.previous:
        return IntentType.previous_result, KnowledgeScope.personal, True, False, False, True, True
    if decision.intent == JevIntent.health_trend_analysis or decision.operation == JevOperation.trend:
        return IntentType.trend, KnowledgeScope.personal, True, False, False, True, True
    if decision.source == JevSource.multiple_sources:
        if decision.operation in {
            JevOperation.interpret,
            JevOperation.retrieve_and_explain,
            JevOperation.summarize,
        }:
            return IntentType.health_scenario, KnowledgeScope.personal, True, True, True, decision.requires_historical_data, True
        return IntentType.trend, KnowledgeScope.personal, True, True, True, decision.requires_historical_data, True
    if decision.intent == JevIntent.lab_result_interpretation:
        return IntentType.blood_marker_explanation, KnowledgeScope.personal, True, False, False, False, False
    if decision.intent == JevIntent.uploaded_document_query:
        return (
            IntentType.latest_result,
            KnowledgeScope.personal if personal else KnowledgeScope.general,
            False,
            False,
            False,
            False,
            False,
        )
    if decision.intent == JevIntent.lab_result_lookup or decision.source in {
        JevSource.blood_reports,
        JevSource.lab_results,
    }:
        return IntentType.latest_result, KnowledgeScope.personal, True, False, False, False, False
    return IntentType.latest_result, KnowledgeScope.personal, True, False, False, False, False


def _query_source(source: JevSource) -> QuerySource:
    return {
        JevSource.profile: QuerySource.supershyft,
        JevSource.assessment: QuerySource.supershyft,
        JevSource.questionnaire: QuerySource.questionnaire,
        JevSource.blood_reports: QuerySource.blood,
        JevSource.lab_results: QuerySource.blood,
        JevSource.bio_ai_report: QuerySource.bio_ai,
        JevSource.bio_ai_trends: QuerySource.bio_ai,
        JevSource.health_metrics: QuerySource.supershyft,
        JevSource.uploaded_documents: QuerySource.user_uploaded,
        JevSource.nutrition: QuerySource.lifestyle,
        JevSource.multiple_sources: QuerySource.mixed,
        JevSource.none: QuerySource.none,
    }[source]


def _needs_questionnaire(decision: JevDecision, message: str) -> bool:
    if decision.intent in {JevIntent.questionnaire_lookup, JevIntent.questionnaire_interpretation}:
        return True
    if decision.source == JevSource.questionnaire:
        return True
    return explicit_questionnaire_request(message)


def _jev_mentions_blood(decision: JevDecision) -> bool:
    blob = " ".join((decision.requested_metrics or []) + (decision.requested_entities or [])).lower()
    return any(
        token in blob
        for token in ("ldl", "hdl", "hba1c", "blood", "cholesterol", "triglyceride", "glucose")
    )


def _jev_mentions_bio(decision: JevDecision) -> bool:
    blob = " ".join((decision.requested_metrics or []) + (decision.requested_entities or [])).lower()
    return any(token in blob for token in ("dyslipidemia", "metabolic", "bio-ai", "bio ai", "score"))