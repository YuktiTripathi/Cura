"""Summarize existing profile/goals/lifestyle/questionnaire into PersonalizationContext."""

from __future__ import annotations

from app.contracts.conversation_state import ConversationState
from app.contracts.goals import ALLOWED_GOAL_CODES, GOAL_LABELS, GOAL_METRICS, GOAL_PHRASES, HealthGoal
from app.contracts.health_context import HealthContext
from app.contracts.personalization import (
    CommunicationStyle,
    GoalSource,
    KnownLifestyle,
    LanguageRegister,
    PersonalizationContext,
)
from app.pipeline.recent_context import extract_recent_context

_QUICK = r"\b(briefly|in short|quick|just the headline|tl;dr|keep it short|be (?:brief|concise)|short answer)\b"
_DEEP = r"\b(in detail|in more detail|deep dive|explain fully|walk me through|technical|detailed)\b"
_SIMPLE = r"\b(in simple (?:terms|language)|like i('m| am) five|plain (?:english|language))\b"
_TECHNICAL = r"\b(technical|use (?:lab|medical) terms)\b"
_ACTION = r"\b(action[- ]focused|just (?:the )?next steps?|what should i do)\b"

import re

_QUICK_RE = re.compile(_QUICK, re.I)
_DEEP_RE = re.compile(_DEEP, re.I)
_SIMPLE_RE = re.compile(_SIMPLE, re.I)
_TECHNICAL_RE = re.compile(_TECHNICAL, re.I)


def goal_code_from_message(message: str) -> str | None:
    text = (message or "").lower()
    if "goal" not in text and "focus" not in text and "want" not in text and "improving" not in text:
        if not any(token in text for token in ("energy", "metabolic", "sleep", "fitness")):
            return None
    for code, phrases in GOAL_PHRASES:
        if any(phrase in text for phrase in phrases):
            return code
    return None


_ACTION_RE = re.compile(_ACTION, re.I)


def communication_style_from_message(message: str, state: ConversationState | None = None) -> CommunicationStyle:
    if _ACTION_RE.search(message or ""):
        return CommunicationStyle.action_focused
    if _DEEP_RE.search(message or ""):
        return CommunicationStyle.deep
    if _QUICK_RE.search(message or ""):
        return CommunicationStyle.quick
    if state and state.communication_style:
        try:
            return CommunicationStyle(state.communication_style)
        except ValueError:
            if state.communication_style in {"CONCISE", "SHORT"}:
                return CommunicationStyle.quick
            if state.communication_style in {"DETAILED"}:
                return CommunicationStyle.deep
    return CommunicationStyle.standard


def language_register_from_message(message: str) -> LanguageRegister | None:
    if _TECHNICAL_RE.search(message or ""):
        return LanguageRegister.technical
    if _SIMPLE_RE.search(message or ""):
        return LanguageRegister.simple
    return None


def _lifestyle_value(answers, key: str) -> str | None:
    for answer in answers or []:
        if answer.question_key == key and answer.value not in (None, ""):
            return str(answer.value)
    return None


def _supportive(sleep: str | None, activity: str | None, lifestyle) -> list[str]:
    out: list[str] = []
    sleep_text = (sleep or "").lower()
    activity_text = (activity or "").lower()
    level = (getattr(lifestyle, "activity_level", None) or "").lower()
    quality = (getattr(lifestyle, "sleep_quality", None) or "").lower()
    if any(token in sleep_text for token in ("7-9", "7–9", "8-", "8 hours", "7 hours")) or quality in {
        "good",
        "excellent",
    }:
        out.append("sleep")
    if (
        any(token in activity_text for token in ("3-4", "4-5", "5-6", "daily", "most days"))
        or level in {"moderate", "high", "active"}
    ):
        out.append("activity")
    return out


def build_personalization_context(
    context: HealthContext,
    *,
    message: str = "",
    conversation_state: ConversationState | None = None,
) -> PersonalizationContext:
    stored = [goal.goal_code for goal in context.goals or [] if goal.status == "active"]
    stated = goal_code_from_message(message)
    if conversation_state and conversation_state.session_goal_code and not stated:
        stated = conversation_state.session_goal_code
    primary = stored[0] if stored else stated
    secondary = stored[1:]
    source = GoalSource.user_goal if stored else (GoalSource.conversation if stated else None)
    answers = context.questionnaire or []
    sleep = _lifestyle_value(answers, "sleeping_hours") or (context.lifestyle.sleep_quality if context.lifestyle else None)
    activity = _lifestyle_value(answers, "physical_activity_frequency") or (
        context.lifestyle.activity_level if context.lifestyle else None
    )
    diet = _lifestyle_value(answers, "diet_preference")
    if not diet and context.profile and context.profile.dietary_preferences:
        diet = str(context.profile.dietary_preferences[0].value)
    alcohol = _lifestyle_value(answers, "alcohol_frequency")
    smoking = _lifestyle_value(answers, "tobacco_frequency")
    dietary = [diet] if diet else []
    known = KnownLifestyle(
        sleep=sleep,
        activity=activity,
        diet=diet,
        alcohol=alcohol,
        smoking=smoking,
        already_supportive=_supportive(sleep, activity, context.lifestyle),
    )
    recent = extract_recent_context(message, conversation_state)
    return PersonalizationContext(
        primary_health_goal=primary,
        secondary_health_goals=secondary,
        goal_source=source,
        communication_preference=communication_style_from_message(message, conversation_state),
        language_register=language_register_from_message(message),
        dietary_preferences=dietary,
        activity_preferences=[activity] if activity else [],
        known_lifestyle=known,
        recent_user_context=recent,
        health_focus_areas=list(context.domains or []),
        session_only=not bool(stored),
    )


def session_goal(subject_id: str, code: str | None) -> HealthGoal | None:
    if not code or code not in ALLOWED_GOAL_CODES:
        return None
    return HealthGoal(
        subject_id=subject_id,
        goal_code=code,
        label=GOAL_LABELS.get(code, code),
        status="active",
        source="conversation",
        target_metrics=list(GOAL_METRICS.get(code, ())),
    )
