"""Shape the personal health snapshot into what the home dashboard and marker panel show."""

from __future__ import annotations

from app.contracts.overview import (
    HealthOverview,
    InsightOverview,
    MarkerOverview,
    MarkerPoint,
    ReportOverview,
    ScoreOverview,
)
from app.contracts.snapshot import PersonalHealthSnapshot
from app.pipeline.lab_parameters import display_name_for

_STATUSES = {"low", "high", "critical", "normal"}
_OUT = {"low", "high", "critical"}


def _status(value) -> str:
    raw = str(getattr(value, "value", value) or "").lower()
    return raw if raw in _STATUSES else "unknown"


def _distance_to_range(value: float, low: float | None, high: float | None) -> float:
    if low is not None and value < low:
        return low - value
    if high is not None and value > high:
        return value - high
    return 0.0


def _trend(current: float, previous: float | None, low: float | None, high: float | None) -> str | None:
    if low is None and high is None:
        return None
    now = _distance_to_range(current, low, high)
    if now == 0:
        return "in_range"
    if previous is None:
        return None
    before = _distance_to_range(previous, low, high)
    if abs(now - before) < 1e-9:
        return "steady"
    return "toward_range" if now < before else "away_from_range"


def build_health_overview(snapshot: PersonalHealthSnapshot) -> HealthOverview:
    blood_events = sorted(
        (event for event in snapshot.timeline.events if event.event_type == "blood_report"),
        key=lambda event: str(event.occurred_at),
    )
    history: dict[str, list[MarkerPoint]] = {}
    for event in blood_events:
        day = str(event.occurred_at)[:10]
        for fact in event.facts:
            if not isinstance(fact.value, (int, float)) or isinstance(fact.value, bool):
                continue
            points = history.setdefault(fact.fact, [])
            points = [point for point in points if point.date != day]
            points.append(MarkerPoint(date=day, value=float(fact.value), status=_status(fact.status)))
            history[fact.fact] = points

    latest_date = str(blood_events[-1].occurred_at)[:10] if blood_events else None
    markers: list[MarkerOverview] = []
    for marker in snapshot.latest_biomarkers:
        if marker.value is None:
            continue
        points = history.get(marker.key, [])
        measured_on = str(marker.measured_at)[:10] if marker.measured_at else (points[-1].date if points else latest_date)
        earlier = [point for point in points if measured_on is None or point.date < measured_on]
        previous = earlier[-1] if earlier else None
        markers.append(
            MarkerOverview(
                key=marker.key,
                label=display_name_for(marker.key) or marker.name,
                value=float(marker.value),
                unit=marker.unit,
                reference_low=marker.reference_low,
                reference_high=marker.reference_high,
                status=_status(marker.flag),
                measured_on=measured_on,
                previous_value=previous.value if previous else None,
                previous_on=previous.date if previous else None,
                trend=_trend(float(marker.value), previous.value if previous else None, marker.reference_low, marker.reference_high),
                history=points,
            )
        )
    markers.sort(key=lambda item: (item.status not in _OUT, item.label.lower()))

    insights = [
        InsightOverview(
            title=item.title or "Worth a look",
            summary=item.summary,
            marker_key=item.topic if item.topic in history else None,
        )
        for item in snapshot.insight_candidates
        if not item.suppressed and item.summary
    ]
    scores = [
        ScoreOverview(name=risk.name or display_name_for(risk.code), score=risk.score, status=risk.status)
        for risk in snapshot.bio_ai_scores
    ]
    reports = [ReportOverview(title=report.title, date=report.report_date[:10]) for report in snapshot.recent_reports]
    return HealthOverview(
        available=snapshot.available,
        latest_report_date=latest_date,
        markers=markers,
        insights=insights[:6],
        scores=scores,
        reports=reports,
    )
