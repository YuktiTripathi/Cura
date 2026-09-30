"""Detect when a question needs stored questionnaire responses (not lab data)."""

from __future__ import annotations

import re

from app.pipeline.questionnaire_topics import SUMMARY_KEYS, TOPIC_KEYS, questionnaire_topic

_EXPLICIT = re.compile(
    r"\b("
    r"questionnaire|"
    r"what did i (?:answer|report|say)|"
    r"what i (?:answered|reported|said)|"
    r"according to my questionnaire|"
    r"from my questionnaire|"
    r"in my questionnaire|"
    r"my questionnaire|"
    r"(?:lifestyle|sleep|diet(?:ary)?|nutrition) habits|"
    r"compare (?:my )?(?:previous|latest|old|new) questionnaire"
    r")\b",
    re.I,
)
_HABIT_CHANGE = re.compile(
    r"\bhave my .{0,40}(?:habit|lifestyle|sleep|diet|alcohol).{0,20}changed\b",
    re.I,
)

QUESTIONNAIRE_TOPIC_KEYS = set(TOPIC_KEYS) | set(SUMMARY_KEYS)


def explicit_questionnaire_request(message: str) -> bool:
    text = message or ""
    return bool(_EXPLICIT.search(text) or _HABIT_CHANGE.search(text))


def questionnaire_follow_up_topic(message: str, follow_up_topic: str | None) -> str | None:
    current = questionnaire_topic(message)
    if current:
        return current
    if follow_up_topic in QUESTIONNAIRE_TOPIC_KEYS:
        return follow_up_topic
    return None


def is_questionnaire_topic(topic: str | None) -> bool:
    return bool(topic) and topic in QUESTIONNAIRE_TOPIC_KEYS
