"""Conversation experience layer. Runs after validated medical reasoning."""

from __future__ import annotations

import re

from app.contracts.blood import BloodReport
from app.contracts.common import IntentType
from app.contracts.conversation_experience import (
    ConversationExperiencePlan,
    ConversationGoal,
    NextBestConversationAction,
    RelevantContext,
    ResponseBlock,
    ResponseBlockKind,
    ResponseDepth,
    TopicSummary,
)
from app.contracts.conversation_state import ConversationState, TurnType
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.health_narrative import HealthNarrativeService
from app.pipeline.lab_parameters import display_name_for
from app.pipeline.relevant_context import RelevantContextSelector

_REASSURE = re.compile(
    r"\b(should i (?:worry|be (?:worried|concerned))|i should be concerned|"
    r"concerned about|is (?:this|that|it) (?:bad|serious|okay|ok|normal)|"
    r"am i (?:healthy|unhealthy)|how (?:worried|concerned) should i be|"
    r"is (?:this|that) something to worry|something i should be concerned)\b",
    re.I,
)
_PRIORITIZE = re.compile(r"\b(what (?:should i focus|matters most)|biggest (?:concern|priority)|priorit)\b", re.I)
_ACTION = re.compile(r"\b(what should i do|next step|action plan|what can i (?:do|change))\b", re.I)
_DEEP = re.compile(r"\b(in detail|in more detail|deep dive|explain fully|walk me through|technical|why does)\b", re.I)
_SHORT = re.compile(
    r"\b(keep it short|be (?:brief|concise)|in short|briefly|just the headline|tl;dr|short answer)\b",
    re.I,
)
_UNDERSTAND = re.compile(
    r"\b(what does .{0,40} mean|what .{0,40} (?:mean|show|showing|indicate)|"
    r"tell me (?:what|about)|explain|interpret|why\b|should i (?:worry)|is that)\b",
    re.I,
)
_NARRATIVE = HealthNarrativeService()
_SELECTOR = RelevantContextSelector()


def infer_conversation_goal(
    message: str,
    plan: QueryPlan,
    state: ConversationState | None = None,
) -> ConversationGoal:
    text = message or ""
    turn = getattr(state, "turn_type", None)
    if _REASSURE.search(text) or (turn == TurnType.reference_resolution and re.search(r"\b(worry|bad|okay|ok)\b", text, re.I)):
        return ConversationGoal.reassurance
    if _NARRATIVE.applies(text, plan) or plan.intent in {IntentType.health_scenario, IntentType.broad_health_summary}:
        return ConversationGoal.health_review
    if _PRIORITIZE.search(text):
        return ConversationGoal.prioritize
    if _ACTION.search(text) or plan.intent == IntentType.nutrition_guidance:
        return ConversationGoal.action_plan
    if _DEEP.search(text):
        return ConversationGoal.deep_dive
    if turn in {TurnType.answer_to_assistant, TurnType.follow_up_question, TurnType.clarification, TurnType.correction}:
        return ConversationGoal.follow_up
    if (
        plan.intent in {IntentType.blood_marker_explanation, IntentType.bio_ai_explanation, IntentType.report_explanation}
        or _UNDERSTAND.search(text)
    ):
        return ConversationGoal.understand
    if _SHORT.search(text) or plan.intent in {IntentType.latest_result, IntentType.previous_result}:
        return ConversationGoal.quick_answer
    if turn == TurnType.reference_resolution:
        return ConversationGoal.follow_up
    return ConversationGoal.understand if plan.needs_personal_data else ConversationGoal.quick_answer


def infer_response_depth(
    message: str,
    plan: QueryPlan,
    goal: ConversationGoal,
    state: ConversationState | None = None,
) -> ResponseDepth:
    text = message or ""
    if _DEEP.search(text) or goal == ConversationGoal.deep_dive:
        return ResponseDepth.deep
    if _SHORT.search(text):
        return ResponseDepth.short
    if state and state.communication_style == "DEEP":
        return ResponseDepth.deep
    if state and state.communication_style in {"QUICK", "CONCISE"}:
        return ResponseDepth.short
    if state and state.response_depth == ResponseDepth.short.value:
        return ResponseDepth.short
    if goal in {ConversationGoal.health_review, ConversationGoal.prioritize}:
        return ResponseDepth.guided
    if goal in {ConversationGoal.understand, ConversationGoal.reassurance, ConversationGoal.follow_up, ConversationGoal.action_plan}:
        return ResponseDepth.guided
    if plan.intent == IntentType.latest_result:
        return ResponseDepth.short
    return ResponseDepth.standard


def infer_current_concern(message: str, plan: QueryPlan, state: ConversationState | None = None) -> str | None:
    if _REASSURE.search(message or ""):
        topic = plan.topic_name or (state.active_entities[0] if state and state.active_entities else None)
        return f"worry about {topic}" if topic else "whether this is concerning"
    if plan.topic_name:
        return plan.topic_name
    if state and state.current_concern:
        return state.current_concern
    return state.active_entities[0] if state and state.active_entities else None


def select_blocks(goal: ConversationGoal, depth: ResponseDepth, relevant: RelevantContext) -> list[ResponseBlockKind]:
    if goal == ConversationGoal.quick_answer or depth == ResponseDepth.short:
        blocks = [ResponseBlockKind.direct_answer, ResponseBlockKind.personal_result]
        if relevant.pattern_note:
            blocks.append(ResponseBlockKind.related_context)
        blocks.append(ResponseBlockKind.source)
        return blocks
    if goal == ConversationGoal.reassurance:
        return [
            ResponseBlockKind.direct_answer,
            ResponseBlockKind.personal_result,
            ResponseBlockKind.reassurance,
            ResponseBlockKind.uncertainty,
            ResponseBlockKind.source,
        ]
    if goal == ConversationGoal.health_review or goal == ConversationGoal.prioritize:
        return [
            ResponseBlockKind.direct_answer,
            ResponseBlockKind.pattern,
            ResponseBlockKind.reassurance,
            ResponseBlockKind.missing_info,
            ResponseBlockKind.source,
        ]
    if goal == ConversationGoal.action_plan:
        return [
            ResponseBlockKind.direct_answer,
            ResponseBlockKind.personal_result,
            ResponseBlockKind.source,
        ]
    if goal == ConversationGoal.deep_dive:
        return [
            ResponseBlockKind.direct_answer,
            ResponseBlockKind.personal_result,
            ResponseBlockKind.why_it_matters,
            ResponseBlockKind.pattern,
            ResponseBlockKind.related_context,
            ResponseBlockKind.uncertainty,
            ResponseBlockKind.missing_info,
            ResponseBlockKind.source,
        ]
    blocks = [
        ResponseBlockKind.direct_answer,
        ResponseBlockKind.personal_result,
        ResponseBlockKind.why_it_matters,
    ]
    if relevant.pattern_note or relevant.supporting_keys:
        blocks.append(ResponseBlockKind.pattern)
        blocks.append(ResponseBlockKind.related_context)
    if relevant.relevant_missing_keys:
        blocks.append(ResponseBlockKind.missing_info)
    blocks.append(ResponseBlockKind.source)
    return blocks


def select_next_action(
    *,
    goal: ConversationGoal,
    plan: QueryPlan,
    context: HealthContext,
    relevant: RelevantContext,
    state: ConversationState | None,
    already_asked: bool,
) -> NextBestConversationAction:
    if already_asked or (state and state.turn_type == TurnType.answer_to_assistant):
        if relevant.related_trend_keys and plan.intent != IntentType.trend:
            return NextBestConversationAction.show_trend
        if relevant.pattern_keys and len(relevant.pattern_keys) > 1:
            return NextBestConversationAction.explain_pattern
        return NextBestConversationAction.none
    if goal == ConversationGoal.quick_answer or (state and state.response_depth == ResponseDepth.short.value):
        if relevant.pattern_keys and relevant.supporting_keys:
            return NextBestConversationAction.explain_pattern
        if relevant.related_trend_keys:
            return NextBestConversationAction.show_trend
        return NextBestConversationAction.none
    if goal == ConversationGoal.reassurance:
        return NextBestConversationAction.suggest_actions if relevant.requested_keys else NextBestConversationAction.none
    if goal == ConversationGoal.health_review:
        if relevant.relevant_missing_keys:
            return NextBestConversationAction.identify_missing_data
        return NextBestConversationAction.suggest_actions
    if goal == ConversationGoal.understand and not (state and state.previous_assistant_follow_up):
        return NextBestConversationAction.ask_clarifying_question
    if relevant.pattern_keys and len(relevant.supporting_keys) >= 1 and goal in {
        ConversationGoal.quick_answer,
        ConversationGoal.understand,
    }:
        return NextBestConversationAction.explain_pattern
    if relevant.related_trend_keys and plan.intent in {IntentType.latest_result, IntentType.blood_marker_explanation}:
        return NextBestConversationAction.show_trend
    if relevant.relevant_missing_keys:
        return NextBestConversationAction.identify_missing_data
    if goal == ConversationGoal.action_plan:
        return NextBestConversationAction.suggest_actions
    return NextBestConversationAction.none


def build_topic_summary(state: ConversationState | None, plan: QueryPlan) -> TopicSummary | None:
    if state is None or (state.topic_turn_count or 0) < 3:
        return None
    if (plan.conversation_turn or "NEW_QUESTION") in {"NEW_QUESTION", "TOPIC_SWITCH"}:
        return None
    facts = [state.previous_assistant_summary] if state.previous_assistant_summary else []
    told = list(state.recent_context_notes or [])[:3]
    remaining = state.previous_assistant_follow_up
    parts = []
    if facts:
        parts.append("So far: " + facts[0])
    if told:
        parts.append("You mentioned " + "; ".join(told) + ".")
    if remaining:
        parts.append("Still open: " + remaining)
    return TopicSummary(
        main_facts=[item for item in facts if item],
        user_told_cura=told,
        remaining_question=remaining,
        text=" ".join(parts) if parts else None,
    )


def build_experience_plan(
    message: str,
    plan: QueryPlan,
    context: HealthContext,
    state: ConversationState | None = None,
    *,
    reports: list[BloodReport] | None = None,
) -> ConversationExperiencePlan:
    goal = infer_conversation_goal(message, plan, state)
    depth = infer_response_depth(message, plan, goal, state)
    relevant = _SELECTOR.select(context, plan, reports=reports, goal=goal, depth=depth)
    # General education may mention related medical entities for explanation,
    # but their absence from the patient's records is not missing information.
    if plan.knowledge_scope.value == "general":
        relevant.relevant_missing_keys = []
    _SELECTOR.apply(context, relevant, reports=reports, depth=depth)
    next_action = select_next_action(
        goal=goal,
        plan=plan,
        context=context,
        relevant=relevant,
        state=state,
        already_asked=bool(state and state.previous_assistant_follow_up and state.turn_type != TurnType.new_question),
    )
    ask = next_action == NextBestConversationAction.ask_clarifying_question
    return ConversationExperiencePlan(
        goal=goal,
        depth=depth,
        next_action=next_action,
        blocks=select_blocks(goal, depth, relevant),
        relevant=relevant,
        topic_summary=build_topic_summary(state, plan),
        ask_follow_up=ask,
        current_concern=infer_current_concern(message, plan, state),
    )


def experience_blocks_from_answer(
    answer: str,
    plan: ConversationExperiencePlan,
    context: HealthContext,
) -> list[ResponseBlock]:
    blocks: list[ResponseBlock] = []
    for kind in plan.blocks:
        if kind == ResponseBlockKind.direct_answer:
            blocks.append(ResponseBlock(kind=kind, text=_lead_sentence(answer)))
        elif kind == ResponseBlockKind.personal_result:
            continue
        elif kind == ResponseBlockKind.why_it_matters:
            blocks.append(ResponseBlock(kind=kind, title="Why this matters", text=None))
        elif kind == ResponseBlockKind.related_context:
            blocks.append(
                ResponseBlock(
                    kind=kind,
                    title="Related results",
                    text=plan.relevant.pattern_note,
                    expandable=True,
                )
            )
        elif kind == ResponseBlockKind.pattern:
            blocks.append(ResponseBlock(kind=kind, title="Related pattern", text=plan.relevant.pattern_note))
        elif kind == ResponseBlockKind.reassurance:
            blocks.append(ResponseBlock(kind=kind, title="How to read this"))
        elif kind == ResponseBlockKind.uncertainty:
            blocks.append(ResponseBlock(kind=kind, title="Still uncertain"))
        elif kind == ResponseBlockKind.missing_info:
            names = [display_name_for(key) for key in plan.relevant.relevant_missing_keys[:3]]
            text = f"I could not find {', '.join(names)} in the available records." if names else None
            blocks.append(ResponseBlock(kind=kind, title="Missing information", text=text))
        elif kind == ResponseBlockKind.next_step:
            blocks.append(ResponseBlock(kind=kind, title="Worth considering"))
        elif kind == ResponseBlockKind.source:
            blocks.append(ResponseBlock(kind=kind, title="Source"))
    return blocks


def chip_prompts(action: NextBestConversationAction, context: HealthContext, plan: QueryPlan) -> list[str]:
    topic = context.resolved_topic_name or plan.topic_name or "this result"
    mapping = {
        NextBestConversationAction.show_trend: f"Compare with previous {topic}",
        NextBestConversationAction.explain_pattern: "Explain this pattern",
        NextBestConversationAction.identify_missing_data: "What is missing?",
        NextBestConversationAction.explore_domain: f"What else is related to {topic}?",
        NextBestConversationAction.suggest_actions: "What should I do next?",
        NextBestConversationAction.offer_testing_option: None,
        NextBestConversationAction.ask_clarifying_question: None,
        NextBestConversationAction.none: None,
    }
    text = mapping.get(action)
    return [text] if text else []


def discipline_follow_ups(
    suggestions: list[FollowUpSuggestion],
    experience: ConversationExperiencePlan,
    *,
    answer_turn: bool,
    extra_chips: list[str] | None = None,
    allow_default_question: bool = False,
) -> tuple[list[FollowUpSuggestion], list[FollowUpSuggestion]]:
    """Split one optional in-answer question from 1–3 action chips."""
    if answer_turn:
        return [], []
    usable = [item for item in suggestions if item.handling_path]
    question: list[FollowUpSuggestion] = []
    chips: list[FollowUpSuggestion] = []
    if experience.ask_follow_up:
        for item in usable:
            if item.expected_reply_type:
                question = [item]
                break
        if not question and allow_default_question:
            question = [
                FollowUpSuggestion(
                    text="Could new symptoms or a medicine change affect this result?",
                    category="clinical_context",
                    handling_path="CONTINUE_INTERPRETATION",
                    expected_reply_type="CLINICAL_CONTEXT",
                )
            ]
        extra: list[FollowUpSuggestion] = []
        existing = {item.text.lower() for item in question}
        for prompt in extra_chips or []:
            if not prompt or prompt.lower() in existing:
                continue
            extra.append(
                FollowUpSuggestion(
                    text=prompt,
                    category="suggested",
                    handling_path="CONTINUE_INTERPRETATION",
                )
            )
            if len(extra) >= 2:
                break
        return question, extra
    for item in usable:
        chips.append(item)
        if len(chips) >= 3:
            break
    existing = {item.text.lower() for item in chips}
    for prompt in extra_chips or []:
        if not prompt or prompt.lower() in existing:
            continue
        chips.append(
            FollowUpSuggestion(
                text=prompt,
                category="suggested",
                handling_path="CONTINUE_INTERPRETATION",
                expected_reply_type=None,
            )
        )
        existing.add(prompt.lower())
        if len(chips) >= 3:
            break
    return question, chips[:3]


def _lead_sentence(answer: str) -> str:
    text = (answer or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    return parts[0]
