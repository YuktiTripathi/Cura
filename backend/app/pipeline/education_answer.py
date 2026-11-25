"""A user-facing answer built directly from the Medical Knowledge Library V2.3 and the verified result.

V2.3 is a primary content source, so this is used whenever the question is about the meaning or the
possible reasons for one result and a personalised model answer is not available. It never claims a
cause, never invents a value and says plainly that the personalised connection is missing.
"""

from __future__ import annotations

import re

from app.pipeline.narrative import format_unit

_WHY = re.compile(r"\b(why|cause|causes|reason|reasons|what could|how come)\b", re.I)
_SIDE_WORD = {"low": "below", "high": "above", "normal": "within"}
_LIMIT = (
    "I can't write a personalised explanation right now, so this is the general explanation for this result. "
    "Ask again shortly and I can connect it with the rest of your information."
)


def _sentence(text: str) -> str:
    text = (text or "").strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _range_phrase(marker) -> str:
    low, high = getattr(marker, "reference_low", None), getattr(marker, "reference_high", None)
    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    if low is not None and high is not None:
        return f" ({low:g} to {high:g}{sep}{unit})"
    return ""


def _factors(marker) -> str:
    from app.biomarkers.medical_registry import canonical_key, entry_for

    row = entry_for(canonical_key(marker.key)) or {}
    items = [str(x).strip().rstrip(".") for x in row.get("possible_influencing_factors") or [] if str(x).strip()]
    items = [x[:1].lower() + x[1:] if x[:2].upper() != x[:2] else x for x in items]
    if len(items) > 1:
        return ", ".join(items[:-1]) + " and " + items[-1]
    return items[0] if items else ""


def education_answer(message: str, context) -> str | None:
    markers = [m for m in (context.markers or []) if m.value is not None]
    if not markers:
        return None
    wanted = [c for c in (context.requested_entity_codes or []) if c]
    marker = next((m for m in markers if m.key in wanted), markers[0])
    from app.biomarkers.education import education_for

    note = education_for(marker.key, marker.name)
    if note is None:
        return None
    flag = str(getattr(marker.flag, "value", marker.flag))
    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    state = _SIDE_WORD.get(flag)
    lead = f"Your {note.name} is {marker.value:g}{sep}{unit}"
    lead += f", {state} the range on your report{_range_phrase(marker)}." if state else "."
    text = (message or "").lower()
    asked_low = bool(re.search(r"\blow(er)?\b", text))
    asked_high = bool(re.search(r"\bhigh(er)?\b", text))
    parts = [lead]
    if (asked_low and flag != "low") or (asked_high and flag != "high"):
        parts.append(
            f"That means your latest result is not {'low' if asked_low else 'high'} on this report, so I will not explain it as if it were."
        )
        side_text = ""
    else:
        side_text = note.if_low if flag == "low" else note.if_high if flag == "high" else ""
    if _WHY.search(text):
        if side_text:
            parts.append(_sentence(side_text))
        factors = _factors(marker)
        if factors:
            parts.append("Things that can influence it include " + factors + ". These are possibilities, not a confirmed cause.")
    else:
        parts.append(_sentence(note.what_it_is))
        if side_text:
            parts.append(_sentence(side_text))
    if note.limitations and _sentence(note.limitations).lower() not in " ".join(parts).lower():
        parts.append(_sentence(note.limitations))
    parts.append(_LIMIT)
    return " ".join(p for p in parts if p)
