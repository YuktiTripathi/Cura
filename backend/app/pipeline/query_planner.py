import re

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.intent import BIO_KEYS, classify_intent, knowledge_scope_for
from app.pipeline.ontology import attach_ontology
from app.pipeline.source_routing import apply_source_routing
from app.contracts.context_ref import ContextRef
from app.pipeline.operations import apply_operation_metadata, named_personal_sources
from app.pipeline.planner import attach_task_plan
from app.pipeline.response_planner import repair_report_level_plan
from app.pipeline.task_contract import apply_task_contract
from app.pipeline.conversation_state import apply_to_query_plan, ensure_named_report_metrics
from app.contracts.conversation_state import ConversationState
from app.pipeline.lab_parameters import match_lab_keys, primary_lab_key
from app.pipeline.questionnaire_intent import (
    explicit_questionnaire_request,
    is_questionnaire_topic,
)
from app.pipeline.questionnaire_topics import questionnaire_topic
from app.pipeline.general_personalization import attach_general_personalization, enforce_general_only_request


def _personal_lifestyle_theme(message: str) -> str | None:
    """This person's sleep, movement, eating or stress. A general question stays general."""

    text = message or ""
    # "my sleep" or "I sleep five hours" is this person's habit. "Tell me", "explain to me" and "how much
    # exercise should I get" are general questions.
    if not re.search(r"\bmy\b|\bi'm\b|\bi've\b|\bi (?:sleep|slept|exercise|walk|run|eat|ate|drink|work out|train|smoke|feel|am|have|usually|only|never|always|don't|do not)\b", text, re.I):
        return None
    if re.search(r"\bsleep\b", text, re.I):
        return "sleep"
    if re.search(r"\b(exercise|exercising|activity|active)\b", text, re.I):
        return "activity"
    if re.search(r"\b(eating habits|eat|diet|food)\b", text, re.I):
        return "food"
    if re.search(r"\bstress\b", text, re.I) and not re.search(r"\boxidative stress\b", text, re.I):
        return "stress"
    return None


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
        if intent == IntentType.health_scenario:
            needs_bio_ai = True
    from app.pipeline.prompt_modules import is_nutrition_overview

    broad_nutrition = personal and is_nutrition_overview(message)
    if broad_nutrition:
        needs_blood = True
        needs_bio_ai = True
        needs_lifestyle = True
        needs_profile = True
    metabolic_story = personal and bool(re.search(r"\bmetabolic age\b", message or "", re.I)) and bool(
        re.search(r"\b(what does|say about|mean|means|health)\b", message or "", re.I)
    )
    if metabolic_story:
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
        or metabolic_story
    )
    needs_profile = personal and intent in {
        IntentType.personal_profile,
        IntentType.health_goal_progress,
        IntentType.nutrition_guidance,
    } or metabolic_story
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
        or broad_nutrition
        or metabolic_story
        or bool(re.search(
            r"\b(?:i recorded|how long do you sit|sit continuously|close blood relatives|family history)\b",
            message or "",
            re.I,
        ))
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
    if match_lab_keys(message) and intent != IntentType.questionnaire_lookup and (personal or prior_personal):
        needs_blood = True
        if prior_personal and not personal:
            personal = True
            scope = KnowledgeScope.personal
            intent = IntentType.blood_marker_explanation
    lowered_msg = message.lower()
    if personal and any(token in lowered_msg for token in ("last year", "previous year", "histor")):
        history = True
    if wants_questionnaire and any(
        token in lowered_msg for token in ("changed", "previous", "compare", "latest questionnaire")
    ):
        history = True
    explicit_answer_lookup = intent == IntentType.questionnaire_lookup and not named_personal_sources(message) - {"questionnaire"}
    theme = _personal_lifestyle_theme(message)
    links_to_results = bool(re.search(
        r"\b(affect|affects|affecting|impact|results?|report|blood|risk|score|levels?)\b",
        message or "", re.I,
    ))
    asks_for_profile = bool(re.search(r"\b(?:profile|based on my)\b", message or "", re.I))
    if theme and theme != "food" and not explicit_answer_lookup and not links_to_results and not asks_for_profile and intent != IntentType.nutrition_guidance:
        # "What is my sleep?" and "Am I physically active enough?" ask about the habit, not the whole report.
        scope = KnowledgeScope.personal
        personal = True
        wants_questionnaire = True
        needs_blood = needs_bio_ai = needs_profile = False
        needs_lifestyle = True
        intent = IntentType.questionnaire_lookup
    elif theme and not explicit_answer_lookup:
        # "How is my sleep affecting my health?" connects a habit to results. "What did I answer about my
        # sleep?" asks only for the questionnaire answer, so it stays a questionnaire lookup.
        # A question about one named result ("What can I eat to lower my LDL?") needs that result and the
        # person's habits, not every Bio-AI score.
        scope = KnowledgeScope.personal
        personal = True
        if theme == "food" and intent == IntentType.general_health_question:
            intent = IntentType.nutrition_guidance
        needs_blood = True
        needs_bio_ai = needs_bio_ai or not match_lab_keys(message)
        needs_lifestyle = True
        needs_profile = True
        wants_questionnaire = True
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
        if re.search(r"\bbio-?ai\b", message or "", re.I) and not re.search(
            r"\b(?:blood|lab) report\b", message or "", re.I
        ):
            plan.needs_blood = False
            plan.needs_questionnaire = False
        elif re.search(r"\b(?:blood|lab) report\b", message or "", re.I):
            plan.needs_bio_ai = False
            plan.needs_questionnaire = False
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
        plan = _apply_card_context(plan, context_ref, message)
        if context_ref.document_id and context_ref.document_id not in (document_ids or []):
            document_ids = [*(document_ids or []), context_ref.document_id]
    plan = apply_source_routing(
        plan,
        document_ids=document_ids,
        uploaded_document_count=uploaded_document_count,
        prior_source_mode=prior_source_mode,
    )
    plan = attach_general_personalization(plan, message)
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
    plan = ensure_named_report_metrics(apply_to_query_plan(plan, conversation_state))
    plan = attach_task_plan(plan, message)
    plan = repair_report_level_plan(plan, message)
    plan = apply_task_contract(plan, message)
    if plan.needs_questionnaire and (plan.needs_blood or plan.needs_bio_ai or plan.needs_goals):
        plan.medical_evidence_required = True
        if plan.needs_blood or plan.needs_bio_ai:
            plan.source = QuerySource.mixed
            plan.needs_supershyft = True
    return _own_result_for_test_question(enforce_general_only_request(plan, message), message)


_NEED_A_TEST = re.compile(r"\b(?:do i need|should i (?:get|do|have|take)|need an?)\b[^?]{0,30}\btests?\b", re.I)


def _own_result_for_test_question(plan: QueryPlan, message: str) -> QueryPlan:
    """"Do I need a thyroid test?" is answered better when the person's own thyroid result is on the table."""
    from app.pipeline.lab_parameters import FAMILY_QUERY_KEYS, is_lab_key

    topic = plan.topic or ""
    if plan.needs_blood or not _NEED_A_TEST.search(message or "") or not (topic in FAMILY_QUERY_KEYS or is_lab_key(topic)):
        return plan
    return plan.model_copy(update={"needs_blood": True, "needs_personal_data": True})


def _apply_kind_needs(update: dict, entry_point: str | None) -> None:
    """A card's entry point names a turn kind; the registry says which sources that kind needs."""
    from app.pipeline.turn_kinds import ENTRY_POINT_KINDS, spec_for

    kind = ENTRY_POINT_KINDS.get(entry_point or "")
    if kind is None:
        return
    spec = spec_for(kind)
    update.update(entry_point=entry_point, needs_blood=spec.needs_blood, needs_bio_ai=spec.needs_bio_ai)
    if spec.needs_questionnaire:
        update["needs_questionnaire"] = True


def _named_keys(plan: QueryPlan) -> set[str]:
    keys = {item for item in (plan.requested_metrics or []) if item}
    if plan.topic:
        keys.add(plan.topic)
    return keys


def _apply_card_context(plan: QueryPlan, ref: ContextRef, message: str) -> QueryPlan:
    """Card context is a hint. A named topic in the message wins. General questions stay general."""
    from app.core.config import settings

    if settings.member_snapshot_enabled:
        named = _named_keys(plan)
        card_key = (ref.marker_code or ref.risk_code or "").strip().lower().replace(" ", "_")
        if plan.needs_general and not plan.needs_supershyft and not named:
            logger_keys = "general"
            _log_evidence(logger_keys, ref, plan)
            return plan
        if named and card_key and card_key not in named and not any(card_key in item or item in card_key for item in named):
            _log_evidence(",".join(sorted(named)), ref, plan)
            return plan
    plan = _apply_context_ref(plan, ref)
    if settings.member_snapshot_enabled and ref.marker_code and ref.type == "blood_marker":
        from app.biomarkers.medical_registry import related_ids

        key = primary_lab_key(ref.marker_code) or ref.marker_code.lower().replace(" ", "_")
        text = (message or "").lower()
        expand = any(word in text for word in ("why", "related", "connected", "together", "compare", "other"))
        extras = [item for item in related_ids(key) if item and item != key] if expand else []
        metrics = list(plan.requested_metrics or [])
        for item in extras[:6]:
            if item not in metrics:
                metrics.append(item)
        if key not in metrics:
            metrics.insert(0, key)
        plan = plan.model_copy(update={"requested_metrics": metrics})
        if any(word in (message or "").lower() for word in ("previous", "history", "compare", "trend", "last time")):
            plan = plan.model_copy(update={"history": True, "compare": True})
    _log_evidence(",".join(sorted(_named_keys(plan))), ref, plan)
    return plan


def _log_evidence(entities: str, ref: ContextRef, plan: QueryPlan) -> None:
    import logging

    logging.getLogger("cura.snapshot").info(
        "evidence_selection entities=%s card_type=%s personal=%s history=%s",
        entities or "-",
        ref.type,
        bool(plan.needs_supershyft or plan.needs_blood or plan.needs_bio_ai),
        bool(plan.history or plan.compare),
    )


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
            intent=IntentType.report_explanation,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            needs_bio_ai=False,
            needs_questionnaire=False,
            needs_supershyft=ref.source == "supershyft",
            needs_general=False,
            source=QuerySource.blood,
        )
        if ref.entry_point == "blood_report_overview":
            update.update(
                entry_point="blood_report_overview",
                answer_depth=AnswerDepth.broad,
                topic=None,
                requested_metrics=[],
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
        _apply_kind_needs(update, ref.entry_point)
    elif ref.type == "bio_ai_report":
        update.update(
            intent=IntentType.bio_ai_explanation,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=False,
            needs_bio_ai=True,
            needs_questionnaire=False,
            needs_supershyft=True,
            needs_general=False,
            source=QuerySource.bio_ai,
        )
        _apply_kind_needs(update, ref.entry_point)
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
