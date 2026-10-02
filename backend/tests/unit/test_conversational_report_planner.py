from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.response_planner import is_report_level_request
from app.routing.mapper import plan_from_jev
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevSource, JevTimeRange

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_explicit_latest_report_is_report_level_request():
    assert is_report_level_request("Show me my latest blood report")
    assert is_report_level_request("Open my current lab report")
    assert not is_report_level_request("What is my HDL?")


def test_jev_lab_lookup_is_repaired_to_report_level_when_no_marker_was_requested():
    decision = JevDecision(
        intent=JevIntent.lab_result_lookup,
        source=JevSource.blood_reports,
        operation=JevOperation.lookup,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=[],
    )
    plan = plan_from_jev(decision, "Show me my latest blood report")
    assert plan.intent.value == "report_explanation"
    assert plan.time_operation == "latest_report"
    assert plan.needs_blood is True
    assert plan.requested_metrics == []
    assert plan.operation == "SUMMARIZE"


def test_latest_report_chat_never_returns_missing_marker_copy():
    body = client.post("/api/v1/chat", headers=H, json={"message": "Show me my latest blood report"}).json()
    answer = (body.get("answer") or "").lower()
    assert "that marker is not available" not in answer
    assert "that biomarker is not available" not in answer
    assert "i will not invent a value" not in answer
    assert "latest blood report" in answer or "blood report" in answer


def test_latest_report_has_goal_aligned_followups_and_no_ambiguous_marker_chip():
    body = client.post("/api/v1/chat", headers=H, json={"message": "Show me my latest blood report"}).json()
    texts = [item.get("text", "") for item in body.get("follow_ups") or []]
    lowered = [text.lower() for text in texts]
    assert any("show all results" in text for text in lowered)
    assert any("abnormal" in text for text in lowered)
    assert all("that marker" not in text for text in lowered)
    presentation = body.get("presentation") or {}
    assert not presentation.get("proactive_insights")
