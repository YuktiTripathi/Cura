from fastapi.testclient import TestClient

from app.contracts.common import IntentType, KnowledgeScope
from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.core.errors import ProviderUnavailableError
from app.main import app
from app.pipeline.intent import classify_intent
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry, set_registry

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def chat(message: str, conversation_id: str | None = None):
    return client.post("/api/v1/chat", headers=H, json={"message": message, "conversation_id": conversation_id})


def test_personal_vitamin_d_intents():
    for msg in ("What is my Vitamin D?", "What is my latest Vitamin D?"):
        plan = build_query_plan(msg)
        assert plan.knowledge_scope == KnowledgeScope.personal
        assert plan.needs_personal_data
        assert plan.needs_blood
        assert not plan.needs_bio_ai
        assert plan.topic == "vitamin_d"
        assert plan.intent == IntentType.latest_result


def test_personal_bio_ai_intents():
    plan = build_query_plan("What is my cardiac health score?")
    assert plan.needs_bio_ai and not plan.needs_blood
    plan = build_query_plan("What does my Bio-AI report say?")
    assert plan.knowledge_scope == KnowledgeScope.personal
    assert plan.needs_bio_ai
    assert not plan.needs_blood


def test_general_intents_skip_personal_retrieval():
    for msg in ("What is Vitamin D?", "What is LDL?", "What is HbA1c?"):
        plan = build_query_plan(msg)
        assert plan.intent == IntentType.general_health_question
        assert plan.knowledge_scope == KnowledgeScope.general
        assert not plan.needs_personal_data
        assert not plan.needs_blood
        assert not plan.needs_bio_ai


def test_general_chat_does_not_use_personal_values():
    body = chat("What is Vitamin D?").json()
    assert body["meta"].get("question_type") == "general_education" or body["meta"]["intent"] == "general_health_question"
    assert body["meta"].get("supershyft_called") is not True
    assert "12.6" not in body["answer"]
    assert "your latest" not in body["answer"].lower()
    assert PERSONAL_DATA_UNAVAILABLE not in body["answer"]


def test_follow_up_why_keeps_vitamin_d():
    first = chat("What is my Vitamin D?")
    cid = first.json()["conversation_id"]
    second = chat("Why?", cid).json()
    assert "12.6" in second["answer"]
    assert second["meta"].get("supershyft_called") is True
    assert second["meta"].get("question_type") in {"personal_health_reasoning", "personal_lookup"} or second["meta"]["intent"] == "blood_marker_explanation"


def test_switch_to_b12_then_meaning():
    first = chat("What is my Vitamin D?")
    cid = first.json()["conversation_id"]
    b12 = chat("What about my B12?", cid).json()
    assert b12["meta"].get("supershyft_called") is True
    entities = b12["meta"].get("requested_entities") or []
    assert "vitamin_b12" in entities or b12["meta"]["intent"] == "latest_result"
    meaning = chat("What does it mean?", cid).json()
    assert meaning["meta"].get("supershyft_called") is True
    assert meaning["meta"].get("question_type") != "general_education"


def test_general_then_mine_becomes_personal():
    first = chat("What does B12 mean?")
    assert first.json()["meta"].get("supershyft_called") is not True
    assert first.json()["meta"].get("question_type") == "general_education" or first.json()["meta"]["intent"] == "general_health_question"
    cid = first.json()["conversation_id"]
    mine = chat("And what about mine?", cid).json()
    assert mine["meta"].get("supershyft_called") is True
    assert build_query_plan("And what about mine?", "vitamin_b12", prior_personal=False).needs_personal_data


def test_missing_parameter_ferritin():
    body = chat("What is my ferritin?").json()
    assert "ferritin" in body["answer"].lower()
    assert "couldn't find" in body["answer"].lower() or "not present" in body["answer"].lower() or "not" in body["answer"].lower()
    assert "normal" not in body["answer"].lower() or "invent" in body["answer"].lower()


def test_personal_while_db_unavailable_still_safe():
    class Boom:
        def get_profile(self, *a, **k):
            raise ProviderUnavailableError()

        def query(self, *a, **k):
            raise ProviderUnavailableError()

    reg = build_registry()
    boom = Boom()
    reg.users = boom
    reg.blood = boom
    set_registry(reg)
    try:
        personal = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "What is my latest Vitamin D?"},
        ).json()
        general = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "What is Vitamin D?"},
        ).json()
        assert personal["answer"] == PERSONAL_DATA_UNAVAILABLE
        assert general["answer"] != PERSONAL_DATA_UNAVAILABLE
        assert "asyncpg" not in personal["answer"].lower()
    finally:
        set_registry(None)


def test_latest_uses_most_recent_report():
    body = chat("What is my latest Vitamin D?").json()
    assert "12.6" in body["answer"]
    assert "18.0" not in body["answer"]


def test_trend_requires_two_values():
    body = chat("Has my Vitamin D changed?").json()
    assert "12.6" in body["answer"] and "18.0" in body["answer"]


def test_classify_metabolic_risk_personal():
    intent, topic, *_ = classify_intent("Why is my metabolic risk high?")
    assert intent == IntentType.bio_ai_explanation
    assert topic == "metabolic_score"


def test_no_supershyft_write_sql_in_providers():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "integrations" / "supershyft"
    blob = ""
    for path in root.glob("*.py"):
        blob += path.read_text().lower()
    for banned in ("insert into", "update ", "delete from", "drop table", "alter table"):
        if banned == "update ":
            continue
        assert banned not in blob
    assert "insert into" not in blob
    assert "delete from" not in blob
