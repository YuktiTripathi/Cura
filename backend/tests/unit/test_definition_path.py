"""Cost lever 4: plain definitions answered from a reviewed passage without a model call."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.retrieval import medical

client = TestClient(app)


@pytest.fixture()
def reviewed_hba1c(tmp_path, monkeypatch):
    today = date.today()
    (tmp_path / "hba1c.json").write_text(json.dumps([{
        "name": "ICMR", "title": "HbA1c", "url": "https://example.org/hba1c", "source_type": "guideline", "tier": 1,
        "topics": ["hba1c"], "keywords": ["hba1c", "glycated haemoglobin"],
        "excerpt": "HbA1c shows your average blood sugar over the past two to three months.",
        "review_status": "published", "reviewer": "Dr A", "reviewed_on": (today - timedelta(days=10)).isoformat(),
        "expires_on": (today + timedelta(days=300)).isoformat(),
    }]))
    monkeypatch.setattr(medical, "CONTENT_DIR", tmp_path)
    monkeypatch.setattr(settings, "medical_require_reviewed", True)
    monkeypatch.setattr(settings, "enable_llm", True)
    calls = []

    def complete(self, messages, json_mode=False):
        calls.append(1)
        return ('{"answer":"Model answer.","claims":[],"recommendation_candidates":[],'
                '"follow_up_questions":[],"safety_flags":[],"escalation":null}')

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    return calls


def _ask(message):
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": "def-user"}, json={"message": message}).json()


def test_definition_question_needs_no_model(reviewed_hba1c):
    body = _ask("What is HbA1c?")
    assert reviewed_hba1c == []
    assert "average blood sugar" in body["answer"].lower()
    assert body["meta"]["llm_called"] is False


def test_high_risk_question_still_uses_the_model(reviewed_hba1c):
    body = _ask("What is HbA1c in pregnancy?")
    assert body["meta"]["status"] != "safety_block"
    assert reviewed_hba1c, "high-risk topics must not take the template path"


def test_disabled_flag_uses_the_model(reviewed_hba1c, monkeypatch):
    monkeypatch.setattr(settings, "deterministic_definitions_enabled", False)
    _ask("What is HbA1c?")
    assert reviewed_hba1c
