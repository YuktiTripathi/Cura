from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.intent import BIO_KEYS, classify_intent, knowledge_scope_for
from app.pipeline.ontology import attach_ontology
from app.pipeline.source_routing import apply_source_routing
from app.contracts.context_ref import ContextRef
from app.pipeline.operations import apply_operation_metadata, named_personal_sources
from app.pipeline.planner import attach_task_plan
from app.pipeline.response_planner import repair_report_level_plan
from app.pipeline.conversation_state import apply_to_query_plan
from app.contracts.conversation_state import ConversationState
from app.pipeline.lab_parameters import match_lab_keys, primary_lab_key
from app.pipeline.questionnaire_intent import (
    explicit_questionnaire_request,
    is_questionnaire_topic,
)
from app.pipeline.questionnaire_topics import questionnaire_topic


def build_query_plan(
    message: str,
    follow_up_topic: str | None = None,
    follow_up_name: str | None = None,
    prior_personal: bool = False,
    document_ids: list[str] | None = None,
    uploaded_document_count: int = 0,
    prior_source_mode: str | None = None,
    context_ref: ContextRef | None = None,
    conversation_state: ConversationState | None = None,
) -> QueryPlan:
    intent, topic, name, depth = classify_intent(message, follow_up_topic, prior_personal=prior_personal)
    if intent == IntentType.follow_up and topic:
        if topic in BIO_KEYS:
            intent = IntentType.bio_ai_score
        elif is_questionnaire_topic(topic):
            pass
        else:
            intent = IntentType.latest_result

    scope = knowledge_scope_for(intent)
    personal = scope == KnowledgeScope.personal

    needs_blood = personal and intent in {
        IntentType.latest_result,
        IntentType.previous_result,
        IntentType.trend,
        IntentType.blood_marker_explanation,
        IntentType.missing_data,
        IntentType.report_explanation,
        IntentType.health_goal_progress,
    }
    needs_bio_ai = personal and intent in {
        IntentType.bio_ai_score,
        IntentType.bio_ai_explanation,
        IntentType.bio_ai_comparison,
        IntentType.report_explanation,
        IntentType.health_goal_progress,
    }
    if personal and intent in {IntentType.health_scenario, IntentType.nutrition_guidance}:
        needs_blood = True
        needs_bio_ai = True
    if personal and intent == IntentType.broad_health_summary:
        text = message.lower()
        if "blood" in text:
            needs_blood = True
        elif "bio-ai" in text or "bio ai" in text:
            needs_bio_ai = True
        elif "eat" in text or "nutrition" in text or "diet" in text:
            needs_blood = True
        else:
            needs_blood = True
            needs_bio_ai = True

    needs_lifestyle = personal and (
        intent == IntentType.bio_ai_explanation
        or intent
        in {
            IntentType.health_scenario,
            IntentType.nutrition_guidance,
            IntentType.personal_profile,
            IntentType.health_goal_progress,
        }
        or (intent == IntentType.broad_health_summary and any(w in message.lower() for w in ("eat", "nutrition", "diet")))
    )
    needs_profile = personal and intent in {
        IntentType.personal_profile,
        IntentType.health_goal_progress,
        IntentType.nutrition_guidance,
    }
    needs_goals = personal and intent == IntentType.health_goal_progress
    history = intent in {
        IntentType.previous_result,
        IntentType.trend,
        IntentType.bio_ai_comparison,
        IntentType.bio_ai_explanation,
        IntentType.health_scenario,
        IntentType.health_goal_progress,
        IntentType.report_explanation,
    }
    wants_questionnaire = personal and (
        intent == IntentType.questionnaire_lookup
        or explicit_questionnaire_request(message)
        or (intent == IntentType.follow_up and is_questionnaire_topic(topic))
        or is_questionnaire_topic(follow_up_topic)
    )
    if wants_questionnaire and intent == IntentType.questionnaire_lookup and not topic:
        topic = questionnaire_topic(message)
        name = name or (topic.replace("_", " ") if topic else "questionnaire")
    if wants_questionnaire and intent == IntentType.questionnaire_lookup and not named_personal_sources(message) - {"questionnaire"}:
        needs_blood = False
        needs_bio_ai = False
        needs_lifestyle = False
        needs_profile = False
    named = named_personal_sources(message)
    if personal and len(named) >= 2:
        if "blood" in named:
            needs_blood = True
        if "bio_ai" in named:
            needs_bio_ai = True
        if "goals" in named:
            needs_goals = True
            needs_profile = True
        if intent == IntentType.questionnaire_lookup:
            intent = IntentType.report_explanation
            history = True
    if personal and match_lab_keys(message) and intent != IntentType.questionnaire_lookup:
        needs_blood = True
    lowered_msg = message.lower()
    if personal and any(token in lowered_msg for token in ("last year", "previous year", "histor")):
        history = True
    if wants_questionnaire and any(
        token in lowered_msg for token in ("changed", "previous", "compare", "latest questionnaire")
    ):
        history = True
    source = QuerySource.general if not personal else QuerySource.none
    if personal:
        if wants_questionnaire and not needs_blood and not needs_bio_ai:
            source = QuerySource.questionnaire
        elif needs_blood and needs_bio_ai:
            source = QuerySource.mixed
        elif needs_blood:
            source = QuerySource.blood
        elif needs_bio_ai:
            source = QuerySource.bio_ai
        elif needs_lifestyle:
            source = QuerySource.lifestyle
        else:
            source = QuerySource.supershyft

    plan = QueryPlan(
        intent=intent,
        source=source,
        knowledge_scope=scope,
        topic=topic,
        topic_name=name or follow_up_name,
        history=history,
        reports="relevant",
        answer_depth=depth,
        needs_blood=needs_blood,
        needs_bio_ai=needs_bio_ai,
        needs_lifestyle=needs_lifestyle,
        needs_profile=needs_profile,
        needs_goals=needs_goals,
        needs_questionnaire=wants_questionnaire,
        compare=intent in {IntentType.trend, IntentType.bio_ai_comparison, IntentType.health_goal_progress}
        or (wants_questionnaire and history),
        follow_up=intent == IntentType.follow_up,
        raw_message=message,
        needs_supershyft=personal,
        needs_general=not personal,
        time_scope="year" if history and "year" in message.lower() else ("previous" if history else "none"),
    )
    plan = attach_ontology(plan, message)
    if intent == IntentType.report_explanation:
        plan.time_operation = "latest_report"
        plan.medical_evidence_required = True
    if intent in {
        IntentType.blood_marker_explanation,
        IntentType.nutrition_guidance,
        IntentType.health_goal_progress,
    }:
        plan.medical_evidence_required = True
    if plan.needs_guidance and personal and (needs_blood or needs_bio_ai):
        plan.needs_general = True
    if wants_questionnaire and (needs_blood or needs_bio_ai):
        plan.medical_evidence_required = True
    if intent == IntentType.casual_conversation:
        plan.needs_supershyft = False
        plan.needs_general = True
        plan.source = QuerySource.general
    if context_ref:
        plan = _apply_context_ref(plan, context_ref)
        if context_ref.document_id and context_ref.document_id not in (document_ids or []):
            document_ids = [*(document_ids or []), context_ref.document_id]
    plan = apply_source_routing(
        plan,
        document_ids=document_ids,
        uploaded_document_count=uploaded_document_count,
        prior_source_mode=prior_source_mode,
    )
    if intent in {
        IntentType.blood_marker_explanation,
        IntentType.nutrition_guidance,
        IntentType.health_goal_progress,
        IntentType.report_explanation,
    }:
        plan.medical_evidence_required = True
    if intent == IntentType.report_explanation:
        plan.time_operation = "latest_report"
    if plan.needs_questionnaire and (plan.needs_blood or plan.needs_bio_ai):
        plan.medical_evidence_required = True
    if document_ids:
        plan.document_ids = list(document_ids)
        plan.active_document_id = plan.document_ids[0] if len(plan.document_ids) == 1 else None
    plan = apply_operation_metadata(plan)
    plan = apply_to_query_plan(plan, conversation_state)
    plan = attach_task_plan(plan, message)
    plan = repair_report_level_plan(plan, message)
    if plan.needs_questionnaire and (plan.needs_blood or plan.needs_bio_ai or plan.needs_goals):
        plan.medical_evidence_required = True
        if plan.needs_blood or plan.needs_bio_ai:
            plan.source = QuerySource.mixed
            plan.needs_supershyft = True
    return plan


def _apply_context_ref(plan: QueryPlan, ref: ContextRef) -> QueryPlan:
    update: dict = {"report_id": ref.report_id, "explicit_source_ref": True}
    if ref.type == "blood_marker":
        topic = primary_lab_key(ref.marker_code or "") or (ref.marker_code or "").lower().replace(" ", "_")
        update.update(
            intent=IntentType.latest_result,
            knowledge_scope=KnowledgeScope.personal,
            topic=topic,
            topic_name=ref.marker_code,
            needs_blood=True,
            needs_bio_ai=False,
            needs_lifestyle=False,
            needs_supershyft=ref.source == "supershyft",
            needs_general=False,
        )
    elif ref.type == "blood_report":
        update.update(
            intent=IntentType.broad_health_summary,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            needs_bio_ai=False,
            needs_supershyft=ref.source == "supershyft",
            needs_general=False,
        )
    elif ref.type == "bio_ai_risk":
        update.update(
            intent=IntentType.bio_ai_explanation,
            knowledge_scope=KnowledgeScope.personal,
            topic=(ref.risk_code or "").lower().replace(" ", "_"),
            topic_name=ref.risk_code,
            needs_blood=False,
            needs_bio_ai=True,
            needs_lifestyle=True,
            needs_supershyft=True,
            needs_general=False,
        )
    elif ref.type == "bio_ai_report":
        update.update(
            intent=IntentType.bio_ai_score,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=False,
            needs_bio_ai=True,
            needs_supershyft=True,
            needs_general=False,
        )
    elif ref.type == "health_scenario":
        update.update(
            intent=IntentType.health_scenario,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            needs_bio_ai=True,
            needs_lifestyle=True,
            needs_supershyft=True,
            needs_general=False,
        )
    elif ref.type == "nutrition_item":
        update.update(
            intent=IntentType.nutrition_guidance,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            needs_bio_ai=True,
            needs_lifestyle=True,
            needs_supershyft=True,
            needs_general=False,
        )
    return plan.model_copy(update=update)
