"""Follow-up referent and uploaded-document selection through POST /api/v1/chat."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

HEADERS = {"X-Cura-User-Id": "eval-user-metabolic"}
OTHER = {"X-Cura-User-Id": "eval-user-iron"}


def _chat(message: str, conversation_id: str | None = None, headers: dict | None = None) -> dict:
    body: dict = {"message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = TestClient(app).post("/api/v1/chat", headers=headers or HEADERS, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_single_marker_follow_up_stays_on_hba1c():
    settings.enable_llm = False
    first = _chat("What is my HbA1c?")
    assert "6.1" in first["answer"]
    second = _chat("Why is it high?", first["conversation_id"])
    answer = second["answer"].lower()
    assert "hba1c" in answer or "6.1" in second["answer"]
    assert "ldl" not in answer
    assert "triglyceride" not in answer


def test_ambiguous_follow_up_asks_which_marker():
    settings.enable_llm = False
    first = _chat("Explain my latest blood report.")
    second = _chat("Why is that high?", first["conversation_id"])
    answer = second["answer"]
    assert answer.startswith("Do you mean")
    assert "HbA1c" in answer


def test_topic_switch_then_follow_up_uses_the_new_marker():
    settings.enable_llm = False
    first = _chat("What is my HbA1c?")
    second = _chat("What is my LDL?", first["conversation_id"])
    assert "96" in second["answer"]
    third = _chat("Why is it high?", second["conversation_id"])
    assert "ldl" in third["answer"].lower() or "96" in third["answer"]
    assert "6.1" not in third["answer"]


def test_new_conversation_does_not_inherit_the_previous_topic():
    settings.enable_llm = False
    first = _chat("What is my HbA1c?")
    fresh = _chat("Why is it high?")
    assert fresh["conversation_id"] != first["conversation_id"]
    assert "Do you mean" not in fresh["answer"] or "hba1c" not in fresh["answer"].lower()


def test_hdl_follow_up_uses_hdl_history():
    settings.enable_llm = False
    first = _chat("What is my HDL?")
    second = _chat("Has it improved?", first["conversation_id"])
    assert "37" in second["answer"] and "38" in second["answer"]
    assert "6.1" not in second["answer"]


def test_bio_ai_follow_up_stays_on_diabetes_risk():
    settings.enable_llm = False
    first = _chat("Explain my latest Bio-AI report.")
    second = _chat("What does my high diabetes risk mean?", first["conversation_id"])
    assert second["meta"]["intent"] == "bio_ai_explanation"
    assert second["meta"]["knowledge_scope"] == "personal"
    metrics = (second["meta"].get("debug") or {}).get("requested_metrics") or []
    assert "type_2_diabetes" in metrics
    assert "68" in second["answer"]


def test_other_user_does_not_see_this_conversation():
    settings.enable_llm = False
    first = _chat("What is my HbA1c?")
    response = TestClient(app).post(
        "/api/v1/chat",
        headers=OTHER,
        json={"message": "Why is it high?", "conversation_id": first["conversation_id"]},
    )
    assert response.status_code in {403, 404}
