from app.contracts.health_context import Comparison


def compute_trend(previous: float | None, current: float | None) -> tuple[float | None, float | None, str | None]:
    if previous is None or current is None:
        return None, None, "unavailable"
    try:
        prev = float(previous)
        curr = float(current)
    except (TypeError, ValueError):
        return None, None, "unavailable"
    delta = curr - prev
    if prev == 0:
        pct = None
    else:
        pct = round((delta / prev) * 100, 2)
    if delta > 0:
        direction = "increased"
    elif delta < 0:
        direction = "decreased"
    else:
        direction = "unchanged"
    return round(delta, 4), pct, direction


def comparison(
    topic: str,
    previous_value: float | None,
    current_value: float | None,
    previous_report_id: str | None = None,
    current_report_id: str | None = None,
    previous_date=None,
    current_date=None,
) -> Comparison:
    delta, pct, direction = compute_trend(previous_value, current_value)
    return Comparison(
        topic=topic,
        previous_value=previous_value,
        current_value=current_value,
        previous_report_id=previous_report_id,
        current_report_id=current_report_id,
        previous_date=previous_date,
        current_date=current_date,
        absolute_delta=delta,
        percentage_change=pct,
        direction=direction,
    )
