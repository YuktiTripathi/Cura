"""Answer-model telemetry records only a model that actually wrote the reply."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app


def _chat(message: str, user: str = "demo-user-001", **extra):
    return TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": user},
        json={"message": message, **extra},
    ).json()


def test_deterministic_blood_lookup_records_no_invoked_model():
    body = _chat("What is my LDL?")
    meta = body["meta"]
    assert meta["llm_called"] is False
    assert meta["answer_model"] in {None, ""}
    assert meta["model"] in {None, ""}
    assert meta["answer_model_tier"] == "DETERMINISTIC"
    assert meta["llm_mode"] == "structured_blood"
    assert "138" in body["answer"]


def test_deterministic_bio_ai_lookup_records_no_invoked_model():
    body = _chat("What are my risk scores?", user="demo-user-002")
    meta = body["meta"]
    assert meta["llm_called"] is False
    assert meta["answer_model"] in {None, ""}
    assert meta["model"] in {None, ""}
    assert meta["llm_mode"] == "structured_bio_ai"
    assert "Your Bio-AI Report" in body["answer"]


def test_deterministic_pdf_lookup_records_no_invoked_model(tmp_path, monkeypatch):
    from tests.helpers.pdf_fixtures import make_text_pdf

    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    client = TestClient(app)
    pdf = make_text_pdf(["Lipid Profile LDL cholesterol 140 mg/dL HDL 45"])
    uploaded = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "pdf-attr-user"},
        files={"file": ("lipid.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]
    body = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "pdf-attr-user"},
        json={"message": "What does this report say about my cholesterol?", "document_ids": [document_id]},
    ).json()
    meta = body["meta"]
    assert meta["llm_called"] is False
    assert meta["answer_model"] in {None, ""}
    assert meta["model"] in {None, ""}
    assert meta["llm_mode"] == "deterministic"
    assert "140" in body["answer"]


def test_privacy_blocked_explanation_names_privacy_and_no_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    called = []

    def complete(self, messages, json_mode=False):
        called.append(self.model)
        raise AssertionError("privacy block must happen before a provider request")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    body = _chat("Why is my LDL high?")
    meta = body["meta"]
    assert called == []
    assert meta["llm_called"] is False
    assert meta["answer_model"] in {None, ""}
    assert meta["model"] in {None, ""}
    assert meta["fallback_reason"] == "privacy"
    assert meta["llm_mode"] == "deterministic_fallback"
    assert meta["answer_model_tier"]


def test_successful_general_answer_records_the_invoked_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    seen = []

    def complete(self, messages, json_mode=False):
        seen.append(self.model)
        return (
            '{"answer":"HbA1c reflects average blood glucose over about three months.",'
            '"claims":[],"recommendation_candidates":[],"follow_up_questions":[],'
            '"safety_flags":[],"escalation":null}'
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    body = _chat("What is HbA1c used to measure?")
    meta = body["meta"]
    assert seen
    assert meta["llm_called"] is True
    assert meta["answer_model"] == seen[-1]
    assert meta["model"] == seen[-1]
    assert meta["answer_model_tier"]
    assert "three months" in body["answer"].lower()


def test_failed_model_request_falls_back_without_an_invoked_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_zero_data_retention", True)

    def complete(self, messages, json_mode=False):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    body = _chat("Why is my LDL high?")
    meta = body["meta"]
    assert meta["llm_called"] is False
    assert meta["answer_model"] in {None, ""}
    assert meta["model"] in {None, ""}
    assert meta["fallback_reason"] == "model_unavailable"
    assert meta["llm_mode"] == "deterministic_fallback"
    assert meta["answer_model_tier"]
