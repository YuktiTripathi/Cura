"""V2.3 passages must reach the assembled model request, under the documented access rule.

The model call is replaced, so this checks the exact messages CURA would send, not a helper in isolation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.main import app
from app.llm.openai_compatible import OpenAICompatibleLLMClient

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}
QUESTION = "What does HbA1c measure?"


def _captured_request(monkeypatch, access: str) -> str:
    seen: list = []

    def fake(self, messages, *args, **kwargs):
        seen.append(messages)
        raise LLMUnavailableError("captured for test")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "medical_library_chat_access", access)
    # The real client is replaced at the network edge: these are the messages CURA would send.
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", fake)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", fake)
    client.post("/api/v1/chat", headers=H, json={"message": QUESTION})
    assert seen, "no model request was assembled"
    return "\n".join(m.get("content", "") for m in seen[-1] if isinstance(m, dict))


def test_evaluation_access_sends_labelled_v23_passages(monkeypatch):
    text = _captured_request(monkeypatch, "evaluation")
    assert "CURATED KNOWLEDGE (V2.3)" in text
    assert "HbA1c" in text.split("CURATED KNOWLEDGE (V2.3)", 1)[1]
    assert "pending clinical review" in text
    assert "No curated knowledge was supplied" not in text


def test_production_access_withholds_unreviewed_passages(monkeypatch):
    text = _captured_request(monkeypatch, "approved_only")
    assert "CURATED KNOWLEDGE (V2.3)" not in text


def test_rejected_and_unknown_settings_never_widen_access(monkeypatch):
    from app.biomarkers import medical_registry as lib

    monkeypatch.setattr(settings, "medical_library_chat_access", "evaluation")
    assert not lib.eligible_for_chat({"review_status": "rejected"})
    assert lib.eligible_for_chat({"review_status": "pending_clinical_review"})
    monkeypatch.setattr(settings, "medical_library_chat_access", "anything-else")
    assert not lib.eligible_for_chat({"review_status": "pending_clinical_review"})
    assert lib.eligible_for_chat({"review_status": "human_clinically_approved", "evidence_status": "verified"})


def test_default_access_depends_on_environment(monkeypatch):
    monkeypatch.setattr(settings, "medical_library_chat_access", "")
    monkeypatch.setattr(settings, "app_env", "production")
    assert settings.library_chat_access() == "approved_only"
    monkeypatch.setattr(settings, "app_env", "development")
    assert settings.library_chat_access() == "evaluation"
