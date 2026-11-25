from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def _blocks(message):
    body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
    return body, [b for b in (body.get("semantic") or {}).get("blocks", [])]


def test_marker_explanation_carries_library_education_without_the_model():
    body, blocks = _blocks("What does my Vitamin D result mean?")
    edu = [b for b in blocks if b["type"] == "medical_education"]
    assert len(edu) == 1 and edu[0]["scope"] == "general" and edu[0]["lines"]
    assert all(line not in body["answer"] for line in edu[0]["lines"])  # not repeated in the answer


def test_plain_value_lookup_gets_no_education_padding():
    _body, blocks = _blocks("What is my Vitamin D?")
    assert not [b for b in blocks if b["type"] in {"medical_education", "medical_relationship"}]


def test_ambiguous_bio_ai_report_gets_no_supporting_content():
    body, blocks = client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What are my risk scores?"}).json(), []
    blocks = (body.get("semantic") or {}).get("blocks", [])
    if body["meta"]["status"] == "ambiguous":
        assert not [b for b in blocks if b["type"].endswith("education") or b["type"] == "medical_relationship"]


def test_general_question_is_answered_from_the_library_when_the_service_is_unavailable(monkeypatch):
    from app.core.config import settings
    from app.core.errors import LLMUnavailableError
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    def down(self, *a, **k):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "synthetic-not-real")
    for name in ("complete", "complete_structured", "stream_text"):
        monkeypatch.setattr(OpenAICompatibleLLMClient, name, down)
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is haemoglobin?"}).json()
    assert "can't access" not in body["answer"].lower()
    assert "oxygen" in body["answer"].lower()


def test_simplify_without_a_model_says_so_instead_of_blaming_the_knowledge_service(monkeypatch):
    from app.core.config import settings
    from app.core.errors import LLMUnavailableError
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    first = client.post("/api/v1/chat", headers=H, json={"message": "What should I eat if I follow a vegetarian diet?"}).json()

    def down(self, *a, **k):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "llm_api_key", "synthetic-not-real")
    for name in ("complete", "complete_structured", "stream_text"):
        monkeypatch.setattr(OpenAICompatibleLLMClient, name, down)
    body = client.post("/api/v1/chat", headers=H, json={"message": "Explain that more simply.", "conversation_id": first["conversation_id"]}).json()
    assert "general medical knowledge service" not in body["answer"]
    assert "simpler words" in body["answer"]
