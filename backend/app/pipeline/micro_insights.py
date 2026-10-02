"""Deterministic, source-bound micro-insights for simple CURA lookups.

These insights never add medical claims. They only describe facts already present in
HealthContext: report reference intervals, marker flags, and retrieved historical
comparisons. This lets deterministic answers feel useful without paying for an LLM.
"""

from __future__ import annotations

from app.contracts.common import IntentType
from app.contracts.health_context import HealthContext
from app.contracts.presentation import StructuredResponse
from app.contracts.query import QueryPlan


def _fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:g}" if isinstance(value, float) else str(value)


def _range_insight(context: HealthContext) -> str | None:
    if len(context.markers or []) != 1:
        return None
    marker = context.markers[0]
    if marker.value is None:
        return None
    unit = f" {marker.unit}" if marker.unit else ""
    low, high = marker.reference_low, marker.reference_high
    flag = getattr(marker.flag, "value", str(marker.flag or "unknown")).lower()

    if low is not None and high is not None:
        interval = f"{_fmt(low)}–{_fmt(high)}{unit}"
        if flag == "normal":
            span = high - low
            if span > 0:
                position = (marker.value - low) / span
                if position <= 0.25:
                    return f"It is within your lab's {interval} reference range, toward the lower end."
                if position >= 0.75:
                    return f"It is within your lab's {interval} reference range, toward the upper end."
            return f"It is within your lab's reported reference range of {interval}."
        if flag in {"high", "critical_high"} or marker.value > high:
            return f"It is above your lab's reported upper reference limit of {_fmt(high)}{unit}."
        if flag in {"low", "critical_low"} or marker.value < low:
            return f"It is below your lab's reported lower reference limit of {_fmt(low)}{unit}."
    elif high is not None:
        if marker.value <= high:
            return f"It is within the report's stated limit of ≤ {_fmt(high)}{unit}."
        return f"It is above the report's stated limit of {_fmt(high)}{unit}."
    elif low is not None:
        if marker.value >= low:
            return f"It is within the report's stated limit of ≥ {_fmt(low)}{unit}."
        return f"It is below the report's stated limit of {_fmt(low)}{unit}."
    return None


def _trend_insight(context: HealthContext) -> str | None:
    if not context.comparisons:
        return None
    comparison = context.comparisons[0]
    previous = getattr(comparison, "previous_value", None)
    current = getattr(comparison, "current_value", None)
    direction = str(getattr(comparison, "direction", "") or "").lower()
    if previous is None or current is None or direction in {"", "stable", "unchanged", "none"}:
        return None
    verb = "increased" if direction in {"up", "increased", "higher", "worsened"} else "decreased"
    return f"Compared with the previous retrieved result ({previous}), it has {verb} to {current}."


def compose_micro_insight(
    *,
    plan: QueryPlan,
    context: HealthContext,
    presentation: StructuredResponse | None,
    llm_called: bool,
) -> str | None:
    """Return one compact trusted insight for deterministic/common lookup turns."""

    if llm_called:
        return None
    if plan.intent not in {
        IntentType.latest_result,
        IntentType.previous_result,
        IntentType.blood_marker_explanation,
        IntentType.trend,
    }:
        return None
    # If the normal presentation already has an interpretation, do not compete with it.
    if presentation and (presentation.interpretation or presentation.personal_relevance):
        return None
    return _trend_insight(context) or _range_insight(context)
