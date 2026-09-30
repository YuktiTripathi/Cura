from fastapi.testclient import TestClient

from app.db.models import Conversation
from app.main import app
from app.memory.conversation import FollowUpMemory
from app.pipeline.intent import extract_topics
from app.pipeline.lab_parameters import retrieval_keys
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_router import _bind_metrics
from app.routing.schemas import JevDecision, JevIntent, JevSource

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_kidney_question_extracts_kidney_not_t3():
    marker, bio = extract_topics("What are my latest kidney function results?")
    assert marker == "kidney_function"
    assert bio is None
    plan = build_query_plan(
        "What are my latest kidney function results?",
        follow_up_topic="t3",
        follow_up_name="T3",
        prior_personal=True,
    )
    assert plan.topic == "kidney_function"
    assert plan.topic != "t3"
    assert "t3" not in retrieval_keys(plan.topic)
    assert "creatinine" in retrieval_keys(plan.topic)


def test_memory_does_not_reuse_t3_for_kidney_latest():
    memory = FollowUpMemory()
    conv = Conversation(
        id="c1",
        subject_id="demo-user-001",
        follow_up_topic="t3",
        follow_up_topic_name="T3",
    )
    topic, name = memory.resolve_topic(conv, "What are my latest kidney function results?")
    assert topic is None
    assert name is None
    topic, name = memory.resolve_topic(conv, "Is that high?")
    assert topic == "t3"
    assert name == "T3"


def test_jev_metrics_are_not_overwritten_with_stale_t3():
    decision = JevDecision(
        intent=JevIntent.lab_result_lookup,
        source=JevSource.blood_reports,
        requires_personal_data=True,
        requested_metrics=["kidney_function"],
    )
    bound = _bind_metrics(decision, "kidney_function", "t3", "What are my latest kidney function results?")
    assert bound.requested_metrics == ["kidney_function"]


def test_t3_then_kidney_two_turn_does_not_repeat_t3():
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest T3 & T4?"}).json()
    assert first["meta"]["intent"] == "latest_result"
    debug1 = first["meta"].get("debug") or {}
    assert debug1.get("query_plan_topic") in {"t3", "t4"}
    cid = first["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "What are my latest kidney function results?"},
    ).json()
    debug2 = second["meta"].get("debug") or {}
    assert second["meta"]["intent"] == "latest_result"
    assert debug2.get("query_plan_topic") == "kidney_function"
    assert debug2.get("query_plan_topic") not in {"t3", "t4"}
    retrieved = debug2.get("retrieved_biomarkers") or []
    assert "t3" not in retrieved
    assert "t4" not in retrieved
    assert "creatinine" in retrieved
    answer = second["answer"].lower()
    assert "t3" not in answer
    assert "t4" not in answer
    assert "creatinine" in answer or "kidney" in answer
    assert "blood report" in second["provenance"]["sources"][0]["name"].lower()


def test_is_that_high_keeps_t3():
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my T3?"}).json()
    cid = first["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "Is that high?"},
    ).json()
    debug2 = second["meta"].get("debug") or {}
    assert debug2.get("query_plan_topic") == "t3"
    assert "t3" in (second["answer"].lower() + str(debug2.get("retrieved_biomarkers") or []))
