"""GET /api/v1/me/overview: latest values with dated history for the home dashboard."""

from __future__ import annotations

import json
from datetime import date

from fastapi.testclient import TestClient

from app.contracts.blood import BloodMarker
from app.contracts.common import MarkerFlag
from app.contracts.insights import InsightCandidate
from app.contracts.snapshot import PersonalHealthSnapshot, SnapshotReport
from app.contracts.timeline import PersonalHealthTimeline, TimelineEvent
from app.main import app
from app.pipeline.health_overview import build_health_overview

client = TestClient(app)


def test_overview_endpoint_returns_latest_values_with_history_and_no_ids():
    res = client.get("/api/v1/me/overview", headers={"X-Cura-User-Id": "demo-user-001"})
    assert res.status_code == 200
    body = res.json()
    markers = {item["key"]: item for item in body["markers"]}
    ldl = markers["ldl"]
    assert ldl["value"] == 138.0 and ldl["unit"] == "mg/dL"
    assert (ldl["reference_low"], ldl["reference_high"]) == (0.0, 100.0)
    assert [point["date"] for point in ldl["history"]] == sorted(point["date"] for point in ldl["history"])
    assert ldl["history"][-1]["value"] == ldl["value"]
    assert ldl["previous_value"] == ldl["history"][-2]["value"]
    # Out-of-range markers come first.
    statuses = [item["status"] for item in body["markers"]]
    first_normal = statuses.index("normal")
    assert all(status in {"low", "high", "critical"} for status in statuses[:first_normal])
    text = json.dumps(body)
    assert "blood-00" not in text and "bioai-" not in text and "report_id" not in text


def test_overview_is_owner_scoped():
    other = client.get("/api/v1/me/overview", headers={"X-Cura-User-Id": "demo-user-002"}).json()
    mine = client.get("/api/v1/me/overview", headers={"X-Cura-User-Id": "demo-user-001"}).json()
    assert other["markers"] != mine["markers"]


def _snapshot(latest: list[BloodMarker], events: list[TimelineEvent], insights=()) -> PersonalHealthSnapshot:
    return PersonalHealthSnapshot(
        subject_id="u",
        latest_biomarkers=latest,
        timeline=PersonalHealthTimeline(subject_id="u", events=events),
        insight_candidates=list(insights),
        recent_reports=[SnapshotReport(report_id="r2", report_date="2026-08-18", source="SuperShyft", title="Latest blood report")],
    )


def _event(day: str, **values) -> TimelineEvent:
    from app.contracts.facts import FactKind, ProvenancedFact

    return TimelineEvent(
        event_type="blood_report",
        occurred_at=date.fromisoformat(day),
        source="SuperShyft",
        report_id=f"r-{day}",
        title="Blood report",
        facts=[ProvenancedFact(fact=key, value=value, source="supershyft", subject_id="u", fact_type=FactKind.measured_data) for key, value in values.items()],
    )


def test_trend_is_measured_against_the_reference_range():
    latest = [
        BloodMarker(id="1", key="ldl", name="LDL", value=138, unit="mg/dL", reference_high=100, flag=MarkerFlag.high),
        BloodMarker(id="2", key="vitamin_d", name="Vitamin D", value=12.6, unit="ng/mL", reference_low=30, reference_high=100, flag=MarkerFlag.low),
        BloodMarker(id="3", key="hdl", name="HDL", value=45, unit="mg/dL", reference_low=40, reference_high=60, flag=MarkerFlag.normal),
        BloodMarker(id="4", key="tsh", name="TSH", value=2.0, unit="µIU/mL", flag=MarkerFlag.normal),
    ]
    events = [_event("2026-07-09", ldl=142, vitamin_d=18, hdl=38), _event("2026-08-18", ldl=138, vitamin_d=12.6, hdl=45, tsh=2.0)]
    overview = build_health_overview(_snapshot(latest, events))
    by_key = {m.key: m for m in overview.markers}
    assert by_key["ldl"].trend == "toward_range"
    assert by_key["vitamin_d"].trend == "away_from_range"
    assert by_key["hdl"].trend == "in_range"
    assert by_key["tsh"].trend is None  # no reference range, no claim
    assert by_key["ldl"].previous_on == "2026-07-09" and by_key["ldl"].measured_on == "2026-08-18"
    assert [m.key for m in overview.markers][:2] == ["ldl", "vitamin_d"]
    assert overview.latest_report_date == "2026-08-18"


def test_suppressed_insights_are_left_out():
    insights = [
        InsightCandidate(insight_type="x", topic="ldl", summary="LDL improved.", title="Something changed"),
        InsightCandidate(insight_type="x", topic="iron", summary="Iron changed.", suppressed=True),
    ]
    events = [_event("2026-08-18", ldl=138)]
    latest = [BloodMarker(id="1", key="ldl", name="LDL", value=138, flag=MarkerFlag.high)]
    overview = build_health_overview(_snapshot(latest, events, insights))
    assert [(i.summary, i.marker_key) for i in overview.insights] == [("LDL improved.", "ldl")]
