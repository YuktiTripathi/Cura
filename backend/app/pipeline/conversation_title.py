"""Short, useful conversation titles from the first user message."""

from __future__ import annotations

import re

_FALLBACK = "Cura conversation"
_MAX_LEN = 48

GENERIC_TITLES = {"", "Cura conversation", "New conversation"}

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"blood report|lab report", re.I), "My Blood Report"),
    (re.compile(r"bio[- ]?ai", re.I), "My Bio-AI Report"),
    (re.compile(r"\bldl\b", re.I), "Understanding LDL"),
    (re.compile(r"heart health", re.I), "My Heart Health"),
    (re.compile(r"chloride", re.I), "My Chloride Result"),
    (re.compile(r"hba1c|a1c|glycated", re.I), "Understanding my HbA1c"),
    (re.compile(r"cholesterol|hdl|triglyceride", re.I), "My cholesterol questions"),
    (re.compile(r"health scenario|going well|needs attention", re.I), "My health scenario"),
    (re.compile(r"nutrition|what should i eat|diet|food", re.I), "Nutrition guidance"),
    (re.compile(r"sugar|glucose|ppbs", re.I), "My blood sugar questions"),
    (re.compile(r"vitamin d", re.I), "Vitamin D questions"),
    (re.compile(r"thyroid|tsh", re.I), "Thyroid questions"),
]


def conversation_title(message: str) -> str:
    text = " ".join((message or "").split())
    if not text:
        return _FALLBACK
    for pattern, title in _RULES:
        if pattern.search(text):
            return title
    cleaned = re.sub(r"[?!.]+$", "", text).strip()
    if len(cleaned) > _MAX_LEN:
        cleaned = cleaned[: _MAX_LEN - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return cleaned or _FALLBACK
