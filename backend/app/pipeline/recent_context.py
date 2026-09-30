"""Session-level user-stated context. Never stored as laboratory history."""

from __future__ import annotations

import re

from app.contracts.conversation_state import ConversationState
from app.contracts.personalization import RecentContext

_FEVER = re.compile(r"\b(fever|feverish|infection|flu|covid|was sick|felt ill|recent illness)\b", re.I)
_SUPPLEMENT = re.compile(r"\b(started|taking|take)\b.{0,24}\b(b12|vitamin d|iron|supplement|injection)s?\b", re.I)
_MED = re.compile(r"\b(started|changed|new|stopped)\b.{0,20}\b(medication|medicine|tablet|drug)s?\b", re.I)
_TRAVEL = re.compile(r"\b(travel|flew|flight|jet lag)\b", re.I)
_PREGNANCY = re.compile(r"\b(pregnant|pregnancy)\b", re.I)
_FASTING = re.compile(r"\b(fasting|fasted)\b", re.I)
_DIET_CHANGE = re.compile(r"\b(started .{0,16}diet|went vegetarian|stopped eating|major diet)\b", re.I)
_SYMPTOM = re.compile(r"\b(fatigue|tired|dizzy|headache|pain|cough|nausea)\b", re.I)


def extract_recent_context(message: str, state: ConversationState | None = None) -> RecentContext:
    text = message or ""
    ctx = RecentContext()
    if _FEVER.search(text):
        ctx.illness.append("recent_illness")
        ctx.notes.append("User reported recent illness or fever.")
    if _SUPPLEMENT.search(text):
        ctx.supplements.append("recent_supplement")
        ctx.notes.append("User reported a recent supplement or injection change.")
    if _MED.search(text):
        ctx.medications.append("recent_medication_change")
        ctx.notes.append("User reported a medication change.")
    if _TRAVEL.search(text):
        ctx.travel.append("recent_travel")
        ctx.notes.append("User reported recent travel.")
    if _PREGNANCY.search(text):
        ctx.pregnancy = "user_stated"
        ctx.notes.append("User mentioned pregnancy.")
    if _FASTING.search(text):
        ctx.fasting_status = "user_stated_fasting"
        ctx.notes.append("User mentioned fasting around testing.")
    if _DIET_CHANGE.search(text):
        ctx.routine_changes.append("diet_change")
        ctx.notes.append("User reported a recent diet change.")
    for match in _SYMPTOM.finditer(text):
        token = match.group(1).lower()
        if token not in ctx.symptoms:
            ctx.symptoms.append(token)
    if state:
        for note in state.recent_context_notes or []:
            if note not in ctx.notes:
                ctx.notes.append(note)
    return ctx
