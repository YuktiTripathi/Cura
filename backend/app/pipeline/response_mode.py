"""Plain vs rich responses: intelligence separated from presentation.

CURA_RESPONSE_MODE=plain returns the conversational answer as the whole visible response:
no finding cards, tables, chips, testing-option cards, related results or "still unclear"
blocks. Structured data stays internal (evidence for the source indicator, meta, debug).
CURA_RESPONSE_MODE=rich (default) keeps the existing presentation untouched.
"""

from __future__ import annotations

from app.core.config import settings
from app.llm.structured import looks_like_structured_json, public_answer_text
from app.pipeline.presentation import prefer_report_range, sanitize_internal_ids


def plain_mode() -> bool:
    return (settings.cura_response_mode or "rich").strip().lower() == "plain"


def _value(marker) -> str:
    unit = f" {marker.unit}" if marker.unit else ""
    return f"{marker.value}{unit}"


def _report_listing(context) -> str:
    """'Show me my report' in plain text: results outside range first, then the rest."""
    markers = [m for m in context.markers or [] if m.value is not None]
    if not markers:
        return ""
    flagged = [m for m in markers if getattr(m.flag, "value", str(m.flag)) in {"high", "low", "critical"}]
    normal = [m for m in markers if m not in flagged]
    lines = []
    if flagged:
        lines.append("Outside your report's range:")
        for m in flagged:
            ref = ""
            if m.reference_low is not None or m.reference_high is not None:
                ref = f", range {m.reference_low if m.reference_low is not None else ''}–{m.reference_high if m.reference_high is not None else ''}"
            lines.append(f"- {m.name}: {_value(m)} ({getattr(m.flag, 'value', m.flag)}{ref})")
    if normal:
        lines.append("")
        lines.append("Within range: " + ", ".join(f"{m.name} {_value(m)}" for m in normal) + ".")
    return "\n".join(lines)


def _position(marker) -> str:
    flag = getattr(marker.flag, "value", str(marker.flag or "")).lower()
    low, high = marker.reference_low, marker.reference_high
    unit = "" if not marker.unit else ("%" if marker.unit.strip() == "%" else f" {marker.unit}")
    if low is not None and high is not None:
        rng = f"{low}–{high}{unit}"
    elif high is not None:
        rng = f"up to {high}{unit}"
    elif low is not None:
        rng = f"{low}{unit} or more"
    else:
        rng = ""
    if flag in {"high", "critical"}:
        return f"which is above your report's range ({rng})" if rng else "which your report flags as high"
    if flag == "low":
        return f"which is below your report's range ({rng})" if rng else "which your report flags as low"
    if flag == "normal":
        return f"which is within your report's range ({rng})" if rng else "which your report marks as normal"
    return ""


def _natural_lookup(context) -> str:
    """'Your HbA1c is 9.1% on your report from 28 Sep 2026, which is above your report's range (4.0–5.6%).'"""
    from app.pipeline.presentation import format_user_date

    markers = [m for m in context.markers or [] if m.value is not None]
    if not markers:
        return ""
    date = context.evidence[0].report_date if context.evidence else markers[0].measured_at
    when = f" on your report from {format_user_date(date)}" if date else ""
    sentences = []
    for m in markers[:4]:
        unit = "%" if (m.unit or "").strip() == "%" else (f" {m.unit}" if m.unit else "")
        position = _position(m)
        sentences.append(f"{m.name} is {m.value}{unit}" + (f", {position}" if position else ""))
    if len(sentences) == 1:
        head, _, tail = sentences[0].partition(",")
        return f"Your {head}{when}" + (f",{tail}" if tail else "") + "."
    return f"From your report{(' ' + when.strip()[len('on your report '):]) if when else ''}: " + "; ".join(sentences) + "."


def plain_answer(answer: str, path: str | None, context) -> str:
    text = answer or ""
    if looks_like_structured_json(text):
        text = public_answer_text(text)
    text = sanitize_internal_ids(prefer_report_range(text, context)).strip()
    if path == "structured_blood" and getattr(context.intent, "value", "") == "latest_result":
        natural = _natural_lookup(context)
        if natural:
            return natural
    if path == "structured_report_overview":
        listing = _report_listing(context)
        if listing:
            text = f"{text}\n\n{listing}".strip()
    return text


def apply_response_mode(response, model_follow_ups: list[str] | None = None):
    """Strip presentation widgets in plain mode. Rich mode returns the response unchanged."""
    if response is None or getattr(response, "meta", None) is None:
        return response
    if not plain_mode():
        response.meta.response_mode = "rich"
        return response
    response.meta.response_mode = "plain"
    response.presentation = None
    response.experience = None
    response.testing_option = None
    response.recommendations = []
    # Suggestions are the model's own, specific to this conversation (0-3); nothing generic.
    from app.contracts.followup import FollowUpSuggestion

    response.follow_ups = [
        FollowUpSuggestion(text=text, category="suggested", handling_path="CONTINUE_INTERPRETATION")
        for text in (model_follow_ups or [])[:3]
    ]
    return response
