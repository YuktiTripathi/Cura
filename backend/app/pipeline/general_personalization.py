"""Narrow optional personal context for an otherwise general educational turn."""

import re

from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.health_topics import (
    evidence_bio_ai_for,
    evidence_markers_for,
    extract_topics,
    questionnaire_keys_for,
)

_GENERAL_ONLY = re.compile(
    r"\b(?:general(?:ly)? only|just (?:the )?(?:general|medical )?(?:meaning|concept|explanation)|"
    r"without (?:using |looking at |checking )?(?:my |the )?(?:personal )?(?:reports?|results?|records?|health data|data)|"
    r"do not use (?:my )?(?:reports?|results?|records?|health data)|"
    r"don'?t use (?:my )?(?:reports?|results?|records?|health data)|"
    r"forget (?:my |the )?(?:reports?|results?|records?))\b",
    re.I,
)
_HYPOTHETICAL_OR_POPULATION = re.compile(
    r"\b(?:if my|suppose my|imagine my|commonly discussed|in people|for most people)\b",
    re.I,
)
_PERSONAL_CONNECTION = re.compile(
    r"\b(?:for me|my health|my results?|my reports?|in my case|"
    r"relate(?:s|d)? to me|relate(?:s|d)? to my|affect(?:s|ed)? my health|based on my)\b",
    re.I,
)
_BROAD_CONCEPT = re.compile(
    r"^\s*(?:what is|explain|tell me about)\s+(?:cholesterol|metabolic syndrome)\s*[?.!]*\s*$",
    re.I,
)
_CONCEPT_QUESTION = re.compile(
    r"\b(?:what (?:is|are|does)|explain|meaning of|tell me about|kya (?:hai|hota|hoti))\b",
    re.I,
)
_ACTION_QUESTION = re.compile(
    r"\b(?:how (?:to|can|do|should)(?: i)?|manage|lower|reduce|improve)\b",
    re.I,
)


def attach_general_personalization(plan: QueryPlan, message: str) -> QueryPlan:
    """Keep the general objective while requesting only topic-relevant sources."""
    if re.search(r"\bmy doctor told\b", message or "", re.I):
        plan.intent = IntentType.general_health_question
        plan.knowledge_scope = KnowledgeScope.general
        plan.source = QuerySource.general
        plan.needs_blood = False
        plan.needs_bio_ai = False
        plan.needs_supershyft = False
        plan.needs_general = True
        plan.general_personalization = False
        return plan
    if (
        plan.intent != IntentType.general_health_question
        or plan.knowledge_scope != KnowledgeScope.general
        or plan.needs_user_uploaded
    ):
        return plan
    if _GENERAL_ONLY.search(message or "") or _HYPOTHETICAL_OR_POPULATION.search(message or ""):
        return plan
    if re.search(r"\bwhat does .{0,48}\bdo\b", message or "", re.I):
        return plan
    from app.pipeline.intent import is_personal_utterance

    if re.search(
        r"\b(?:common reasons|common causes|lifestyle changes|what foods|generally)\b",
        message or "",
        re.I,
    ) and not is_personal_utterance(message or ""):
        return plan
    topics_for_gate = extract_topics(message, conversation_entities=plan.conversation_entities)
    asks_action_about_marker = bool(_ACTION_QUESTION.search(message or "") and evidence_markers_for(topics_for_gate))
    # A definition can be marked for optional context, but it must not retrieve records.
    if (_CONCEPT_QUESTION.search(message or "") or _BROAD_CONCEPT.search(message or "")) and not (
        _PERSONAL_CONNECTION.search(message or "") or asks_action_about_marker
    ):
        plan.general_personalization = True
        plan.semantic_scoped = True
        plan.needs_general = True
        plan.needs_supershyft = False
        plan.needs_blood = False
        plan.needs_bio_ai = False
        plan.needs_questionnaire = False
        plan.needs_lifestyle = False
        plan.source = QuerySource.general
        return plan
    if not (_PERSONAL_CONNECTION.search(message or "") or asks_action_about_marker):
        return plan
    topics = extract_topics(message, conversation_entities=plan.conversation_entities)
    # Topic mappings are conservative "may be relevant" links, not causal claims.
    # A definition can include one to three related findings without another model call.
    markers = evidence_markers_for(topics)
    if asks_action_about_marker:
        from app.pipeline.health_domains import domain_for_entity

        related: list[str] = []
        for key in markers:
            domain = domain_for_entity(key)
            if domain:
                related.extend(domain.primary_entities)
        markers = list(dict.fromkeys([*markers, *related]))
    markers = markers[:4]
    bio_ai = [
        code
        for code in evidence_bio_ai_for(topics)
        if code not in {"metabolic_age", "metabolic_score"}
    ][:2]
    if "thyroid" in bio_ai and not re.search(r"\bthyroid (?:health|risk|condition)\b", message or "", re.I):
        if not topics.markers and topics.bio_ai == ["thyroid"]:
            bio_ai = [code for code in bio_ai if code != "thyroid"]
    questionnaire = questionnaire_keys_for(topics, limit=6)
    if not (markers or bio_ai or questionnaire):
        return plan
    plan.general_personalization = True
    plan.semantic_scoped = True
    plan.needs_blood = bool(markers)
    plan.needs_bio_ai = bool(bio_ai)
    plan.needs_questionnaire = bool(questionnaire)
    plan.needs_lifestyle = bool(questionnaire)
    plan.needs_profile = False
    plan.needs_goals = False
    plan.needs_supershyft = True
    plan.needs_general = True
    plan.source = QuerySource.mixed
    plan.requested_metrics = list(dict.fromkeys([*markers, *bio_ai]))
    plan.reasoning_context = list(dict.fromkeys([*plan.reasoning_context, *questionnaire]))
    return plan


def enforce_general_only_request(plan: QueryPlan, message: str) -> QueryPlan:
    """Finalize the narrow supplement or an explicit opt-out after plan repair."""
    from app.pipeline.task_contract import stamp_answer_spec

    from app.pipeline.health_sources import sync_plan_sources

    return stamp_answer_spec(sync_plan_sources(_finalize_personal_scope(plan, message)), message)


def _finalize_personal_scope(plan: QueryPlan, message: str) -> QueryPlan:
    from app.pipeline.intent import is_educational_utterance, is_personal_utterance, requires_personal_record

    if re.search(r"\bmy doctor told\b", message or "", re.I):
        plan.intent = IntentType.general_health_question
        plan.knowledge_scope = KnowledgeScope.general
        plan.source = QuerySource.general
        plan.needs_blood = False
        plan.needs_bio_ai = False
        plan.needs_supershyft = False
        plan.needs_general = True
        plan.general_personalization = False
        return plan
    refers_to_document = bool(
        re.search(
            r"\b(?:this|the|my|uploaded)\b(?:\s+\w+){0,4}\s+(?:report|pdf|document|upload)\b",
            message or "",
            re.I,
        )
    )
    if (
        plan.needs_user_uploaded
        and is_educational_utterance(message)
        and not is_personal_utterance(message)
        and not refers_to_document
        and not plan.needs_cross_source
    ):
        plan.needs_user_uploaded = False
        plan.needs_blood = False
        plan.needs_supershyft = False
        plan.intent = IntentType.general_health_question
        plan.knowledge_scope = KnowledgeScope.general
        plan.source = QuerySource.general
        plan.needs_general = True
        return plan
    if (
        plan.needs_user_uploaded
        and not plan.needs_cross_source
        and not (plan.needs_bio_ai or plan.needs_questionnaire or plan.needs_lifestyle)
    ):
        plan.needs_blood = False
        plan.needs_bio_ai = False
        plan.needs_questionnaire = False
        plan.needs_lifestyle = False
        plan.needs_supershyft = False
        plan.source = QuerySource.user_uploaded
        return plan
    prior_personal = plan.knowledge_scope == KnowledgeScope.personal or bool(plan.follow_up)
    if (
        is_educational_utterance(message)
        and not is_personal_utterance(message)
        and not requires_personal_record(
            message,
            prior_personal=prior_personal,
            follow_up_topic=plan.topic,
        )
        and not _PERSONAL_CONNECTION.search(message or "")
        and not plan.needs_user_uploaded
        and not plan.needs_cross_source
        and not plan.personal_reference
    ):
        plan.knowledge_scope = KnowledgeScope.general
        plan.intent = IntentType.general_health_question
        plan.needs_supershyft = False
        plan.needs_blood = False
        plan.needs_bio_ai = False
        plan.needs_questionnaire = False
        plan.needs_lifestyle = False
        plan.needs_general = True
        plan.source = QuerySource.general
        kept_out = re.search(
            r"\b(?:common reasons|common causes|lifestyle changes|what foods|generally|my doctor told)\b",
            message or "",
            re.I,
        )
        plan.general_personalization = bool(
            not kept_out
            and (_CONCEPT_QUESTION.search(message or "") or _BROAD_CONCEPT.search(message or ""))
        )
        return plan
    general_only = bool(_GENERAL_ONLY.search(message or ""))
    non_personal_example = bool(_HYPOTHETICAL_OR_POPULATION.search(message or ""))
    if general_only or non_personal_example:
        return plan.model_copy(
            update={
                "knowledge_scope": KnowledgeScope.general,
                "source": QuerySource.general,
                "general_personalization": False,
                "semantic_scoped": False,
                "needs_blood": False,
                "needs_bio_ai": False,
                "needs_questionnaire": False,
                "needs_lifestyle": False,
                "needs_profile": False,
                "needs_goals": False,
                "needs_supershyft": False,
                "needs_general": True,
            }
        )
    if not plan.general_personalization:
        return plan
    topics = extract_topics(message, conversation_entities=plan.conversation_entities)
    markers = evidence_markers_for(topics)[:4]
    bio_ai = evidence_bio_ai_for(topics)[:2]
    questionnaire = questionnaire_keys_for(topics, limit=6)
    extra = [key for key in (plan.requested_metrics or []) if key not in markers and key not in bio_ai]
    metrics = list(dict.fromkeys([*markers, *bio_ai, *extra]))
    return plan.model_copy(
        update={
            "requested_metrics": metrics,
            "reasoning_context": questionnaire,
            "needs_blood": bool(markers),
            "needs_bio_ai": bool(bio_ai),
            "needs_questionnaire": bool(questionnaire),
            "needs_lifestyle": bool(questionnaire),
            "needs_profile": False,
            "needs_goals": False,
        }
    )


def limit_general_personal_context(context) -> None:
    """Keep at most three significant, diverse verified facts for general education."""
    if not context.general_personalization:
        return
    ranked: list[tuple[int, int, str, str]] = []
    for marker in context.markers or []:
        status = str(getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", ""))).lower()
        significance = 5 if status == "critical" else 4 if status in {"high", "low"} else 1
        ranked.append((significance, 2, "marker", marker.key))
    for risk in context.bio_ai_risks or []:
        status = (risk.status or "").lower()
        significance = 4 if status and status not in {"healthy", "normal", "low"} else 1
        ranked.append((significance, 1, "risk", risk.code))
    for answer in context.questionnaire or []:
        ranked.append((2, 0, "questionnaire", answer.question_key))
    chosen = sorted(ranked, key=lambda row: (row[0], row[1]), reverse=True)[:3]
    marker_keys = {key for _score, _kind_rank, kind, key in chosen if kind == "marker"}
    risk_keys = {key for _score, _kind_rank, kind, key in chosen if kind == "risk"}
    asked = {str(code).lower().replace("_score", "") for code in (getattr(context, "requested_entity_codes", None) or [])}
    risk_keys |= {risk.code for risk in context.bio_ai_risks or [] if (risk.code or "").lower() in asked}
    question_keys = {key for _score, _kind_rank, kind, key in chosen if kind == "questionnaire"}
    context.markers = [item for item in context.markers or [] if item.key in marker_keys]
    context.bio_ai_risks = [item for item in context.bio_ai_risks or [] if item.code in risk_keys]
    context.questionnaire = [item for item in context.questionnaire or [] if item.question_key in question_keys]
    context.evidence = [
        item
        for item in context.evidence or []
        if (
            (item.marker and any(marker.name == item.marker for marker in context.markers))
            or (item.risk_code and item.risk_code in risk_keys)
            or (not item.marker and not item.risk_code)
        )
    ]
    context.evidence_ids = [item.evidence_id for item in context.evidence]
    # Optional mapped facts that are absent are not shortcomings in a general explanation.
    context.missing = []
