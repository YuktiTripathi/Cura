"""Per-mode presentation policy: what an answer shows, not what happens to exist.

Runs last on the structured response. It only removes or caps optional display
elements; it never edits a measured value, unit or the answer text itself.
"""

from __future__ import annotations

from app.contracts.presentation import ResponseMode, StructuredResponse

MAX_CHIPS = 3
MAX_NEXT_STEPS = 3
_LOOKUP_MODES = {ResponseMode.single_value, ResponseMode.result_list}
_OVERVIEW_MODES = {ResponseMode.health_overview, ResponseMode.narrative_health_summary}


def _shown_keys(presentation: StructuredResponse) -> set[str]:
    keys = {f.canonical_key for f in presentation.findings if f.canonical_key}
    for theme in presentation.themes or []:
        keys.update(getattr(theme, "supporting_fact_ids", None) or [])
    return keys


def apply_presentation_policy(
    presentation: StructuredResponse, follow_up_count: int = 0
) -> tuple[StructuredResponse, dict]:
    """Cap optional elements and give each fact a single visual owner. Returns a dev trace."""
    dropped: dict[str, int] = {}

    def _note(name: str, before: int, after: int) -> None:
        if before > after:
            dropped[name] = before - after

    mode = presentation.mode
    # Single visual owner: a value already on a primary card is not repeated as a related result.
    shown = _shown_keys(presentation)
    related = [f for f in presentation.related_findings if not f.canonical_key or f.canonical_key not in shown]
    seen: set[str] = set()
    unique = []
    for f in related:
        key = f.canonical_key or f.label
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    limit = 0 if mode in _LOOKUP_MODES else 2
    _note("related_findings", len(presentation.related_findings), len(unique[:limit]))
    presentation.related_findings = unique[:limit]

    # Next steps: at most three, no duplicates.
    steps = list(dict.fromkeys(s for s in presentation.next_steps if s and s.strip()))
    _note("next_steps", len(presentation.next_steps), min(len(steps), MAX_NEXT_STEPS))
    presentation.next_steps = steps[:MAX_NEXT_STEPS]
    presentation.structured_next_steps = presentation.structured_next_steps[:MAX_NEXT_STEPS]

    # At most one proactive element per turn. A matched testing option already is that element.
    insights = presentation.proactive_insights
    keep = 0 if presentation.testing_option is not None else 1
    if mode in _LOOKUP_MODES and presentation.personal_relevance:
        keep = 0  # a lookup already carries its one "why this matters" note
    _note("proactive_insights", len(insights), min(len(insights), keep))
    presentation.proactive_insights = insights[:keep]
    proactive = (
        "testing_option" if presentation.testing_option is not None
        else "proactive_insight" if presentation.proactive_insights
        else None
    )

    chips = list(dict.fromkeys(c for c in presentation.suggestion_chips if c and c.strip()))
    # Follow-up questions and suggestion chips render as one row: three in total.
    room = max(0, MAX_CHIPS - follow_up_count)
    _note("suggestion_chips", len(presentation.suggestion_chips), min(len(chips), room))
    presentation.suggestion_chips = chips[:room]
    return presentation, {"proactive_element_selected": proactive, "display_elements_dropped": dropped}
