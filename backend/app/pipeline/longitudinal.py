"""Compact longitudinal summaries for the reasoner. Not full report dumps."""

from __future__ import annotations

from app.contracts.blood import BloodReport
from app.contracts.personalization import CompactLongitudinal, LongitudinalClass, PersonalBaseline
from app.pipeline.baselines import build_baselines
from app.pipeline.lab_parameters import display_name_for

_CHANGE = {
    LongitudinalClass.newly_abnormal,
    LongitudinalClass.persistently_abnormal,
    LongitudinalClass.improved_but_still_abnormal,
    LongitudinalClass.returned_to_range,
    LongitudinalClass.worsened,
    LongitudinalClass.improved,
}


def compact_longitudinal(
    reports: list[BloodReport] | None,
    *,
    keys: list[str] | None = None,
    baselines: list[PersonalBaseline] | None = None,
    cap: int = 12,
) -> CompactLongitudinal:
    rows = baselines if baselines is not None else build_baselines(reports, keys)
    ranked = sorted(
        rows,
        key=lambda item: (
            0 if item.classification in _CHANGE else 1,
            0 if item.latest_flag in {"low", "high", "critical"} else 1,
            item.entity,
        ),
    )[:cap]
    latest: dict[str, float | str] = {}
    previous: dict[str, float | str] = {}
    summary: list[str] = []
    for item in ranked:
        if item.latest is not None:
            latest[item.entity] = item.latest
        if item.previous is not None:
            previous[item.entity] = item.previous
        label = display_name_for(item.entity)
        summary.append(_line(label, item))
    return CompactLongitudinal(latest=latest, important_previous=previous, trend_summary=summary)


def _line(label: str, item: PersonalBaseline) -> str:
    cls = item.classification
    if cls == LongitudinalClass.improved_but_still_abnormal:
        return f"{label} → improved, still {item.latest_flag}"
    if cls == LongitudinalClass.persistently_abnormal:
        return f"{label} → remains {item.latest_flag}"
    if cls == LongitudinalClass.newly_abnormal:
        return f"{label} → newly {item.latest_flag}"
    if cls == LongitudinalClass.returned_to_range:
        return f"{label} → returned to range"
    if cls == LongitudinalClass.improved:
        return f"{label} → improved"
    if cls == LongitudinalClass.worsened:
        return f"{label} → worsened"
    if cls == LongitudinalClass.stable:
        flag = " and in range" if item.latest_flag == "normal" else ""
        return f"{label} → stable{flag}"
    if cls == LongitudinalClass.newly_available:
        return f"{label} → newly available"
    return f"{label} → no longitudinal data"
