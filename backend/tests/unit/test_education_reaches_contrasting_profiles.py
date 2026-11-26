"""The same question from contrasting synthetic members must produce different, grounded model requests.

The model call is replaced at the network edge, so these are the exact messages CURA would send. They
check that each member's own result reaches the model with the education that fits that result, and
that one member's values never appear in another member's request.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app

client = TestClient(app)


def _request(monkeypatch, user: str, question: str) -> str:
    seen: list = []

    def fake(self, messages, *args, **kwargs):
        seen.append(messages)
        raise LLMUnavailableError("captured for test")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", fake)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", fake)
    client.post("/api/v1/chat", headers={"X-Cura-User-Id": user}, json={"message": question})
    assert seen, "no model request was assembled"
    return "\n".join(m.get("content", "") for m in seen[-1] if isinstance(m, dict))


def test_low_and_normal_vitamin_d_get_different_education(monkeypatch):
    low = _request(monkeypatch, "demo-user-001", "Why is my vitamin D low?")
    normal = _request(monkeypatch, "demo-user-002", "Why is my vitamin D low?")
    assert "12.6" in low and "42.0" not in low
    assert "Sunlight exposure: Skin makes vitamin D in sunlight" in low
    assert "42" in normal and "12.6" not in normal
    assert "premise check" in normal  # the question assumes a low result that this member does not have


def test_prediabetes_range_hba1c_gets_threshold_and_maintenance_is_not_skipped(monkeypatch):
    text = _request(monkeypatch, "eval-user-metabolic", "What does my HbA1c result mean?")
    assert "6.1" in text
    assert "5.7 to 6.4%" in text


def test_iron_pattern_member_gets_factor_explanations_for_haemoglobin(monkeypatch):
    text = _request(monkeypatch, "eval-user-iron", "Why is my haemoglobin low?")
    assert "10.5" in text
    assert "Blood loss including heavy periods" in text
    assert "Thalassaemia trait" in text or "Inherited haemoglobin traits" in text
