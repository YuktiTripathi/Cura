"""Attach library text when the canonical id matches. Review status does not hide it."""

from __future__ import annotations

from app.contracts.unified_health import EducationNote
from app.medical_content.mapping import confirmed_ids
from app.medical_content.registry import load_registry


def _text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(part) for part in value if part)
    return str(value or "")


def note_for(canonical_id: str, status: str) -> EducationNote | None:
    if canonical_id not in confirmed_ids():
        return None
    entry = load_registry()["by_id"].get(canonical_id)
    if entry is None or entry.get("review_status") == "rejected":
        return None
    explanations = entry.get("result_explanations") or {}
    high = _text(explanations.get("high"))
    low = _text(explanations.get("low"))
    normal = _text(explanations.get("normal"))
    if status == "within_range":
        chosen = normal
        high = ""
        low = ""
    elif status == "below_range":
        chosen = low
        high = ""
    elif status in {"above_range", "critical"}:
        chosen = high
        low = ""
    else:
        chosen = _text(explanations.get("reference_unavailable"))
        high = low = ""
    if not chosen and not entry.get("short_description"):
        return None
    return EducationNote(
        name=entry.get("display_name") or entry.get("clinical_name") or canonical_id,
        what_it_is=entry.get("short_description") or entry.get("what_happens_inside_my_body") or "",
        if_high=high if status in {"above_range", "critical"} else "",
        if_low=low if status == "below_range" else "",
        common_factors=_text(entry.get("possible_influencing_factors"))[:500],
        next_step=chosen[:500],
    )


def passages_for(keys: list[str], limit: int = 2) -> list[str]:
    allowed = confirmed_ids()
    library = load_registry()
    lines = []
    for key in keys:
        if key not in allowed:
            continue
        entry = library["by_id"].get(key)
        if not entry:
            continue
        lines.append(f"{entry.get('display_name')}: {entry.get('short_description') or ''}".strip())
        if len(lines) >= limit:
            break
    return lines
