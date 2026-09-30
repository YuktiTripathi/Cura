"""Personal baselines from stored reports. The LLM never calculates these."""

from __future__ import annotations

from statistics import median

from app.contracts.blood import BloodReport
from app.contracts.common import MarkerFlag
from app.contracts.personalization import LongitudinalClass, PersonalBaseline
from app.pipeline.personal_selection import measurements_for_key
from app.pipeline.trend_engine import compute_trend

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical}


def _flag(marker) -> MarkerFlag:
    raw = getattr(marker, "flag", None)
    if isinstance(raw, MarkerFlag):
        return raw
    try:
        return MarkerFlag(str(raw))
    except ValueError:
        return MarkerFlag.unknown


def _improved(previous_flag: MarkerFlag, key: str, previous: float, current: float) -> bool | None:
    if previous == current:
        return None
    if key in {"hdl", "egfr"}:
        return current > previous
    if previous_flag == MarkerFlag.low:
        return current > previous
    if previous_flag in {MarkerFlag.high, MarkerFlag.critical}:
        return current < previous
    return current < previous if current != previous else None


def classify_series(key: str, values: list[tuple[float, MarkerFlag]]) -> LongitudinalClass:
    if not values:
        return LongitudinalClass.no_longitudinal_data
    latest_value, latest_flag = values[-1]
    latest_abn = latest_flag in _ABNORMAL
    if len(values) == 1:
        return LongitudinalClass.newly_available
    prev_value, prev_flag = values[-2]
    prev_abn = prev_flag in _ABNORMAL
    improved = _improved(prev_flag, key, prev_value, latest_value)
    if latest_abn and not prev_abn:
        return LongitudinalClass.newly_abnormal
    if latest_abn and prev_abn:
        if improved is True:
            return LongitudinalClass.improved_but_still_abnormal
        return LongitudinalClass.persistently_abnormal
    if not latest_abn and prev_abn:
        return LongitudinalClass.returned_to_range
    if not latest_abn and not prev_abn:
        if prev_value:
            relative = abs(latest_value - prev_value) / abs(prev_value)
            if relative < 0.05:
                return LongitudinalClass.stable
        if improved is True:
            return LongitudinalClass.improved
        if improved is False:
            return LongitudinalClass.worsened
        return LongitudinalClass.stable
    if improved is True:
        return LongitudinalClass.improved
    if improved is False:
        return LongitudinalClass.worsened
    return LongitudinalClass.stable


def build_baselines(reports: list[BloodReport] | None, keys: list[str] | None = None) -> list[PersonalBaseline]:
    ordered = list(reports or [])
    if not ordered:
        return []
    wanted = list(keys or [])
    if not wanted:
        latest = max(ordered, key=lambda r: (r.report_date, r.report_id))
        wanted = [m.key for m in latest.markers if m.key and m.value is not None]
    out: list[PersonalBaseline] = []
    seen: set[str] = set()
    for key in wanted:
        if key in seen:
            continue
        seen.add(key)
        hits = measurements_for_key(ordered, key)
        if not hits:
            continue
        series = [(float(m.value), _flag(m)) for _, m in hits if m.value is not None]
        if not series:
            continue
        latest_report, latest = hits[-1]
        previous = hits[-2][1] if len(hits) >= 2 else None
        delta, pct, direction = compute_trend(
            previous.value if previous is not None else None,
            latest.value,
        )
        numbers = [item[0] for item in series]
        hist_median = round(float(median(numbers[:-1])), 4) if len(numbers) >= 3 else None
        near = None
        if hist_median is not None and latest.value is not None and hist_median:
            near = abs(float(latest.value) - hist_median) / abs(hist_median) <= 0.08
        classification = classify_series(key, series)
        out.append(
            PersonalBaseline(
                entity=key,
                latest=float(latest.value) if latest.value is not None else None,
                previous=float(previous.value) if previous is not None and previous.value is not None else None,
                absolute_change=delta,
                percentage_change=pct,
                direction=direction if len(hits) >= 2 else None,
                historical_median=hist_median,
                observations=len(series),
                near_personal_baseline=near,
                newly_abnormal=classification == LongitudinalClass.newly_abnormal,
                persistent_abnormality=classification
                in {
                    LongitudinalClass.persistently_abnormal,
                    LongitudinalClass.improved_but_still_abnormal,
                },
                classification=classification,
                latest_flag=_flag(latest).value,
                previous_flag=_flag(previous).value if previous is not None else None,
                unit=latest.unit,
            )
        )
    return out
