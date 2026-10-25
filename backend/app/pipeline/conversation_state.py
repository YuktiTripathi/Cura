"""Classify the current turn and resolve references before Jev / Task Planning.

Conversation state is semantic continuity only. Personal values are still re-fetched.
"""

from __future__ import annotations

import json
import re

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.conversation_state import ConversationState, ExpectedReplyType, TurnType
from app.contracts.query import QueryPlan
from app.db.models import Conversation
from app.pipeline.health_domains import HealthDomainResolver, domain_for_code
from app.pipeline.intent import extract_topics, is_contextual_follow_up
from app.pipeline.lab_parameters import is_lab_key
from app.pipeline.language import normalize_for_intent
from app.pipeline.ontology import match_bio_keys


def ensure_named_report_metrics(plan: QueryPlan) -> QueryPlan:
    """Re-fetch a marker the question names. Do not copy the value from chat text."""
    from app.pipeline.lab_parameters import match_lab_keys

    text = plan.raw_message or ""
    named = [key for key in match_lab_keys(text) if key]
    if not named:
        return plan
    personal_turn = plan.conversation_turn in {
        "follow_up_question",
        "reference_resolution",
        "clarification",
        "correction",
    } or bool(re.search(r"\bmy\b|\d", text, re.I))
    if not personal_turn:
        return plan
    plan.needs_blood = True
    plan.needs_supershyft = True
    plan.requested_metrics = list(dict.fromkeys([*named, *(plan.requested_metrics or [])]))
    if not plan.topic:
        plan.topic = named[0]
    return plan


def apply_to_query_plan(plan: QueryPlan, state: ConversationState | None) -> QueryPlan:
    """Bind resolved conversation semantics onto the query plan. Does not copy lab values."""
    if state is None:
        return plan
    plan.conversation_turn = state.turn_type.value
    plan.operations_hint = list(state.operations_hint)
    plan.conversation_entities = list(state.active_entities)
    continuing = state.turn_type in {
        TurnType.answer_to_assistant,
        TurnType.follow_up_question,
        TurnType.reference_resolution,
        TurnType.confirmation,
        TurnType.clarification,
        TurnType.correction,
    }
    if not continuing:
        return plan
    if not plan.topic and state.active_entities:
        plan.topic = state.active_entities[0]
        plan.topic_name = plan.topic_name or state.active_entities[0].replace("_", " ")
    if not plan.domains and state.active_domain:
        plan.domains = [state.active_domain]
    if state.active_entities:
        extra = [item for item in state.active_entities if item not in (plan.requested_metrics or [])]
        if extra:
            plan.requested_metrics = list(plan.requested_metrics or []) + extra
    if state.prior_personal or state.turn_type == TurnType.answer_to_assistant:
        plan.knowledge_scope = KnowledgeScope.personal
        source = state.active_source or "blood_report"
        if source in {"blood_report", "blood"} or any(is_lab_key(item) for item in state.active_entities):
            plan.needs_blood = True
            plan.needs_supershyft = True
        if source in {"bio_ai_report", "bio_ai"}:
            plan.needs_bio_ai = True
            plan.needs_supershyft = True
        if not plan.needs_blood and not plan.needs_bio_ai:
            plan.needs_blood = True
            plan.needs_supershyft = True
        plan.needs_general = False
    if state.turn_type == TurnType.answer_to_assistant:
        if (state.previous_intent or "") in {"bio_ai_explanation", "bio_ai_score"}:
            plan.intent = IntentType.bio_ai_explanation
            plan.needs_bio_ai = True
        else:
            plan.intent = IntentType.blood_marker_explanation
        plan.answer_depth = AnswerDepth.focused
    if state.resolved_time_scope == "previous":
        plan.intent = IntentType.previous_result
        plan.history = True
        plan.time_scope = "previous"
        plan.time_operation = "previous_marker"
    elif state.resolved_time_scope == "latest":
        plan.history = False
        plan.time_scope = "latest"
    if "TREND" in {item.upper() for item in state.operations_hint}:
        plan.intent = IntentType.trend
        plan.history = True
        plan.time_scope = "historical"
    if state.new_context:
        extra = [item for item in state.new_context if item not in plan.reasoning_context]
        plan.reasoning_context = list(plan.reasoning_context) + extra
    return plan


_REFERENCE = re.compile(
    r"\b(it|that|this|these|those|they|them|the above|that score|that result|"
    r"the previous one|previous one|the latest one|latest one|"
    r"what about that|is that concerning|why|"
    r"another test|repeat it|test this again|"
    r"should i (?:repeat|retest)|when should i test|kyun|kyu|yeh|yah|woh|iska|uska)\b",
    re.I,
)
_PREVIOUS_REF = re.compile(
    r"\b(the previous (?:one|report|result|value)|previous (?:one|report)|last (?:one|report)|before that)\b",
    re.I,
)
_LATEST_REF = re.compile(
    r"\b(the latest (?:one|report|result)|latest (?:one|report)|most recent)\b",
    re.I,
)
_CONCERN = re.compile(r"\b(is that (?:concerning|normal|ok|okay|bad)|should i (?:worry|be concerned))\b", re.I)
_CONSISTENT = re.compile(r"\b(consistent|fit together|connected|in common|pattern)\b", re.I)
_WHY_CHANGE = re.compile(r"\bwhy (?:did|has|have) (?:that|it|they|this) chang", re.I)
_CONFIRM = re.compile(r"^\s*(yes|yeah|yep|ok|okay|sure|correct|that'?s right|please)\s*[.!]?\s*$", re.I)
_SHORT_REPLY = re.compile(
    r"^\s*(yes|yeah|yep|no|nope|not really|not yet|sometimes)(\s*,?\s+.{0,80})?\s*[.!]?\s*$",
    re.I,
)
_DAILY_HABIT = re.compile(r"\b(i take|taking|take one|once (?:a|per) day|every day|daily)\b", re.I)
_CORRECTION = re.compile(r"\b(actually|i meant|not that|correction|wait,? no)\b", re.I)
_NEW_QUESTION = re.compile(
    r"\b(what is my|what are my|show me|list |how is my|how are my|tell me my)\b",
    re.I,
)
_ANSWERISH = re.compile(
    r"\b(no symptoms?|no new symptoms?|nothing new|no changes?|"
    r"supplement|medication|started|stopped|feeling fine|"
    r"no meds?|not taking)\b",
    re.I,
)
_SUPPLEMENT = re.compile(
    r"\b(supplements?|multivitamin|started (?:taking |a )?(?:vitamin|supplement))\b",
    re.I,
)
_NO_SYMPTOMS = re.compile(r"\b(no (?:new )?symptoms?|nothing new|feeling fine|no complaints)\b", re.I)
_MEDS = re.compile(r"\b(medication|medicine|started taking|stopped taking|dose)\b", re.I)
_CLARIFY_PICK = re.compile(
    r"\b(the (?:first|second|blood|bio-ai|latest|newer|older|basic|standard|regular|normal)|"
    r"use (?:that|this|the)|advanced|basic|standard|regular|first one|second one|latest one|"
    r"bio-ai|either|both|any)\b",
    re.I,
)


def load_persisted_state(conversation: Conversation | None) -> ConversationState:
    raw = getattr(conversation, "conversation_state_json", None) if conversation else None
    if raw:
        try:
            return ConversationState.model_validate(json.loads(raw))
        except (ValueError, TypeError):
            pass
    state = ConversationState()
    if conversation is None:
        return state
    state.active_entities = [conversation.follow_up_topic] if conversation.follow_up_topic else []
    state.active_report_id = conversation.current_report_id
    if conversation.current_marker_code and conversation.current_marker_code not in state.active_entities:
        state.active_entities = [conversation.current_marker_code, *state.active_entities]
    domain = domain_for_code(conversation.follow_up_topic) if conversation.follow_up_topic else None
    if domain:
        state.active_domain = domain.code
    state.previous_assistant_summary = conversation.conversation_summary
    state.prior_personal = bool(conversation.follow_up_topic)
    messages = list(conversation.messages or [])
    for msg in reversed(messages):
        if msg.role == "user" and not state.previous_user_question:
            state.previous_user_question = msg.content
            state.previous_intent = msg.intent
        if msg.role == "assistant" and not state.previous_assistant_follow_up:
            text = msg.content or ""
            if "?" in text:
                state.previous_assistant_follow_up = text.rsplit("?", 1)[0].split("\n")[-1].strip() + "?"
    return state


_DISPLAY = {
    "hba1c": "HbA1c",
    "ldl": "LDL",
    "hdl": "HDL",
    "triglycerides": "triglycerides",
    "type_2_diabetes": "type 2 diabetes risk",
}


def discussed_entities(plan, context) -> list[str]:
    """Markers or scores this turn actually talked about. Not the whole record."""
    named = [
        item
        for item in (getattr(plan, "display_entities", None) or getattr(plan, "requested_metrics", None) or [])
        if item
    ]
    if named:
        return list(dict.fromkeys(named))
    flagged = []
    for marker in getattr(context, "markers", None) or []:
        flag = getattr(getattr(marker, "flag", None), "value", None)
        key = getattr(marker, "key", None)
        if key and flag in {"high", "low", "critical"}:
            flagged.append(key)
    for risk in getattr(context, "bio_ai_risks", None) or []:
        code = getattr(risk, "code", None)
        if code:
            flagged.append(code)
    return list(dict.fromkeys(flagged))[:4]


def ambiguous_referent_question(state: ConversationState, conversation: Conversation | None) -> str | None:
    """Ask which finding is meant when a singular follow-up matches several."""
    if "which_marker" not in (state.unresolved_references or []):
        return None
    prior = load_persisted_state(conversation)
    codes = list(dict.fromkeys(prior.active_entities))[:3]
    if len(codes) < 2:
        return None
    labels = [_DISPLAY.get(code, code.replace("_", " ")) for code in codes]
    if len(labels) == 2:
        joined = f"{labels[0]} or {labels[1]}"
    else:
        joined = ", ".join(labels[:-1]) + f", or {labels[-1]}"
    return f"Do you mean {joined}?"


class ConversationStateResolver:
    """Resolve turn type and references. Does not retrieve personal values."""

    def resolve(self, message: str, conversation: Conversation | None) -> ConversationState:
        prior = load_persisted_state(conversation)
        text = normalize_for_intent(message or "").strip()
        current_entities, current_domain = _mentioned(message)
        turn = _classify(text, prior, current_entities, current_domain)
        resolved: dict[str, str] = {}
        unresolved: list[str] = []
        time_scope = None
        if _PREVIOUS_REF.search(text) or re.search(r"\bprevious report\b", text, re.I):
            resolved["the previous one"] = "previous_report"
            time_scope = "previous"
        if _LATEST_REF.search(text):
            resolved["the latest one"] = "latest_report"
            time_scope = time_scope or "latest"
        if _REFERENCE.search(text) or _CONCERN.search(text):
            target = (current_entities or prior.active_entities or [prior.active_domain or ""])[:1]
            if target and target[0]:
                for token in ("it", "that", "this", "those", "they", "why"):
                    if re.search(rf"\b{token}\b", text, re.I):
                        resolved[token] = target[0]
            elif _REFERENCE.search(text):
                unresolved.append("anaphor")
        entities = list(current_entities)
        domain = current_domain or prior.active_domain
        if turn == TurnType.answer_to_assistant:
            entities = list(prior.active_entities) or entities
            domain = prior.active_domain or domain
        elif turn in {
            TurnType.follow_up_question,
            TurnType.reference_resolution,
            TurnType.confirmation,
            TurnType.clarification,
            TurnType.correction,
        }:
            singular = bool(
                re.search(r"\b(it|that|this|yeh|yah|woh|kyun)\b", text, re.I)
            ) and not re.search(r"\b(they|them|those|these)\b", text, re.I)
            asks_which_result = bool(
                re.search(r"\bwhy is (?:it|that|this)(?: result)? (?:high|low|elevated|up)\b", text, re.I)
            )
            if not current_entities and asks_which_result and len(prior.active_entities) > 1:
                # "Why is that high?" with several markers: ask, do not pick one.
                entities = []
                unresolved.append("which_marker")
            elif not entities:
                entities = list(prior.active_entities[:1] if singular else prior.active_entities)
            if not domain or domain == "overall_health":
                domain = prior.active_domain or domain
        new_context = _new_context(text) if turn == TurnType.answer_to_assistant else []
        ops = _operations_hint(turn, text, prior)
        return ConversationState(
            turn_type=turn,
            active_domain=domain,
            active_entities=list(dict.fromkeys(entities)),
            active_source=prior.active_source or ("blood_report" if any(is_lab_key(k) for k in entities) else None),
            active_report_id=prior.active_report_id,
            previous_user_question=prior.previous_user_question,
            previous_assistant_summary=prior.previous_assistant_summary,
            previous_assistant_follow_up=prior.previous_assistant_follow_up,
            suggested_follow_ups=list(prior.suggested_follow_ups or []),
            previous_intent=prior.previous_intent,
            expected_reply_type=prior.expected_reply_type,
            expected_handling_path=prior.expected_handling_path,
            recently_referenced=list(dict.fromkeys([*entities, *prior.recently_referenced]))[:8],
            unresolved_references=unresolved,
            resolved_references=resolved,
            new_context=new_context,
            operations_hint=ops,
            prior_personal=prior.prior_personal or turn != TurnType.new_question,
            resolved_time_scope=time_scope,
            communication_style=prior.communication_style,
            recent_context_notes=list(prior.recent_context_notes or [])[:8],
            dismissed_insight_keys=list(prior.dismissed_insight_keys or [])[:12],
            session_goal_code=prior.session_goal_code,
            current_concern=prior.current_concern,
            response_depth=prior.response_depth,
            conversation_goal=prior.conversation_goal,
            topic_turn_count=prior.topic_turn_count,
            explained_entities=list(prior.explained_entities or [])[:12],
            topic_summary=prior.topic_summary,
            last_surfaced_catalog_id=prior.last_surfaced_catalog_id,
            last_surfaced_catalog_name=prior.last_surfaced_catalog_name,
        )


def persistable_state(
    resolved: ConversationState,
    *,
    plan_topic: str | None,
    plan_domains: list[str],
    plan_entities: list[str],
    plan_intent: str | None,
    user_message: str,
    assistant_summary: str | None,
    follow_up: str | None,
    expected_reply_type: ExpectedReplyType,
    expected_handling_path: str | None,
    report_id: str | None,
    prior_personal: bool,
    last_surfaced_catalog_id: str | None = None,
    last_surfaced_catalog_name: str | None = None,
    communication_style: str | None = None,
    recent_context_notes: list[str] | None = None,
    session_goal_code: str | None = None,
    current_concern: str | None = None,
    response_depth: str | None = None,
    conversation_goal: str | None = None,
    explained_entities: list[str] | None = None,
    topic_summary: str | None = None,
    suggested: list[str] | None = None,
) -> ConversationState:
    entities = list(dict.fromkeys([*(plan_entities or []), *resolved.active_entities]))
    domain = (plan_domains[0] if plan_domains else None) or resolved.active_domain
    if plan_topic and plan_topic not in entities and is_lab_key(plan_topic):
        entities.insert(0, plan_topic)
    switched = resolved.turn_type in {TurnType.topic_switch, TurnType.new_question}
    turns = 1 if switched else (resolved.topic_turn_count or 0) + 1
    explained = list(dict.fromkeys([*(resolved.explained_entities or []), *(explained_entities or []), *entities]))[:12]
    return ConversationState(
        turn_type=resolved.turn_type,
        active_domain=domain,
        active_entities=entities[:8],
        active_source=resolved.active_source,
        active_report_id=report_id or resolved.active_report_id,
        previous_user_question=user_message,
        previous_assistant_summary=(assistant_summary or "")[:240] or None,
        previous_assistant_follow_up=follow_up,
        suggested_follow_ups=list(dict.fromkeys([*(resolved.suggested_follow_ups or []), *(suggested or [])]))[-12:],
        previous_intent=plan_intent,
        expected_reply_type=expected_reply_type,
        expected_handling_path=expected_handling_path,
        recently_referenced=entities[:8],
        unresolved_references=[],
        resolved_references=resolved.resolved_references,
        new_context=resolved.new_context,
        operations_hint=resolved.operations_hint,
        prior_personal=prior_personal,
        resolved_time_scope=resolved.resolved_time_scope,
        last_surfaced_catalog_id=last_surfaced_catalog_id or resolved.last_surfaced_catalog_id,
        last_surfaced_catalog_name=last_surfaced_catalog_name or resolved.last_surfaced_catalog_name,
        communication_style=communication_style or resolved.communication_style,
        recent_context_notes=list(recent_context_notes or resolved.recent_context_notes or [])[:8],
        dismissed_insight_keys=list(resolved.dismissed_insight_keys or [])[:12],
        session_goal_code=session_goal_code or resolved.session_goal_code,
        current_concern=current_concern or resolved.current_concern,
        response_depth=response_depth or resolved.response_depth,
        conversation_goal=conversation_goal or resolved.conversation_goal,
        topic_turn_count=turns,
        explained_entities=explained,
        topic_summary=topic_summary or resolved.topic_summary,
    )


def _mentioned(message: str) -> tuple[list[str], str | None]:
    marker, bio = extract_topics(message)
    labs = [marker] if marker else []
    if bio:
        labs.append(bio)
    expansion = HealthDomainResolver().expand(message)
    domain = expansion.domains[0] if expansion.domains else None
    if domain and domain == "overall_health" and not labs:
        domain = "overall_health"
    extra = match_bio_keys(message)
    for item in extra:
        if item not in labs:
            labs.append(item)
    return [item for item in labs if item], domain


def _classify(
    text: str,
    prior: ConversationState,
    current_entities: list[str],
    current_domain: str | None,
) -> TurnType:
    has_prior = bool(prior.active_entities or prior.active_domain or prior.previous_user_question)
    if not has_prior:
        return TurnType.new_question
    if _CORRECTION.search(text):
        return TurnType.correction
    if prior.expected_reply_type == ExpectedReplyType.clinical_context and (
        _looks_like_clinical_answer(text) or _DAILY_HABIT.search(text) or _SHORT_REPLY.match(text)
    ) and not _NEW_QUESTION.search(text):
        return TurnType.answer_to_assistant
    if prior.expected_handling_path == "CONTINUE_INTERPRETATION" and (
        _looks_like_clinical_answer(text) or _DAILY_HABIT.search(text) or _SHORT_REPLY.match(text)
    ) and not _NEW_QUESTION.search(text):
        return TurnType.answer_to_assistant
    if prior.expected_reply_type in {ExpectedReplyType.confirmation, ExpectedReplyType.yes_no} and _CONFIRM.match(text):
        return TurnType.confirmation
    if prior.expected_reply_type == ExpectedReplyType.report_choice and _CLARIFY_PICK.search(text) and not _NEW_QUESTION.search(text):
        return TurnType.clarification
    if prior.previous_assistant_follow_up and _looks_like_clinical_answer(text) and not _NEW_QUESTION.search(text):
        if "?" in (prior.previous_assistant_follow_up or "") or _clinical_question(prior.previous_assistant_follow_up or ""):
            return TurnType.answer_to_assistant
    switched = bool(current_entities) and bool(prior.active_entities) and not set(current_entities) & set(prior.active_entities)
    switched_domain = bool(current_domain and prior.active_domain and current_domain != prior.active_domain)
    if (switched or switched_domain) and not _REFERENCE.search(text) and _NEW_QUESTION.search(text):
        return TurnType.topic_switch
    if _PREVIOUS_REF.search(text) or _LATEST_REF.search(text) or _CONCERN.search(text) or _WHY_CHANGE.search(text):
        return TurnType.reference_resolution
    if is_contextual_follow_up(text) or _CONSISTENT.search(text) or re.match(r"^\s*why\b", text, re.I):
        if current_entities and prior.active_entities and not set(current_entities) & set(prior.active_entities):
            return TurnType.topic_switch
        return TurnType.follow_up_question if _CONSISTENT.search(text) or re.search(r"\b(mean|normal|chang)", text, re.I) else TurnType.reference_resolution
    if _CONFIRM.match(text) and has_prior:
        return TurnType.confirmation
    return TurnType.new_question


def _looks_like_clinical_answer(text: str) -> bool:
    if _NEW_QUESTION.search(text) and not _ANSWERISH.search(text):
        return False
    return bool(
        _ANSWERISH.search(text)
        or _SUPPLEMENT.search(text)
        or _DAILY_HABIT.search(text)
        or _NO_SYMPTOMS.search(text)
        or _MEDS.search(text)
        or _SHORT_REPLY.match(text)
    )


def _clinical_question(text: str) -> bool:
    return bool(re.search(r"\b(symptoms?|medication|supplement|changes?)\b", text, re.I))


def _new_context(text: str) -> list[str]:
    found: list[str] = []
    if _NO_SYMPTOMS.search(text):
        found.append("no_symptoms")
    if _SUPPLEMENT.search(text) or _DAILY_HABIT.search(text):
        found.append("supplement_use")
    if _MEDS.search(text):
        found.append("medication_change")
    return found


def _operations_hint(turn: TurnType, text: str, prior: ConversationState) -> list[str]:
    if turn == TurnType.answer_to_assistant:
        path = prior.expected_handling_path or "CONTINUE_INTERPRETATION"
        return ["UPDATE_CONTEXT", path]
    if _WHY_CHANGE.search(text) or re.search(
        r"\b(improved|improvement|worsened|since last|since my last|badla|sudhra)\b", text, re.I
    ):
        return ["RETRIEVE", "TREND", "INTERPRET"]
    if turn == TurnType.reference_resolution and re.search(r"\bchang", text, re.I):
        return ["RETRIEVE", "TREND", "INTERPRET"]
    if _CONSISTENT.search(text):
        return ["RETRIEVE", "CORRELATE", "INTERPRET"]
    if _PREVIOUS_REF.search(text) or re.search(r"\bprevious report\b", text, re.I):
        return ["RETRIEVE"]
    if _CONCERN.search(text) or re.match(r"^\s*why\b", text, re.I):
        return ["RETRIEVE", "EXPLAIN", "INTERPRET"]
    if turn == TurnType.follow_up_question:
        return ["RETRIEVE", "INTERPRET"]
    return []
