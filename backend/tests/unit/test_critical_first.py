"""Readiness plan 2.8: a critical lab value is answered with escalation first, in every language."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.contracts.common import MarkerFlag
from app.i18n import catalog
from app.main import app
from app.pipeline.context_builder import ContextBuilder

client = TestClient(app)


@pytest.fixture()
def critical_hba1c(monkeypatch):
    original = ContextBuilder.build

    def build(self, *args, **kwargs):
        context = original(self, *args, **kwargs)
        for marker in context.markers:
            if "hba1c" in (marker.name or "").lower().replace(" ", ""):
                marker.flag = MarkerFlag.critical
        return context

    monkeypatch.setattr(ContextBuilder, "build", build)


@pytest.mark.parametrize(
    "message, language",
    [
        ("What is my latest HbA1c?", "en"),
        ("मेरा HbA1c क्या है?", "hi"),
        ("mera HbA1c kya hai?", "hinglish"),
    ],
)
def test_critical_value_answer_opens_with_escalation(critical_hba1c, message, language):
    body = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": message, "language": language, "language_mode": "manual"},
    ).json()
    expected_start = catalog.t("critical_value_notice", language, markers="X", emergency="112").split("X")[0]
    assert body["answer"].startswith(expected_start), body["answer"][:160]
    assert "112" in body["answer"].split("\n\n")[0]
    assert body["meta"]["escalation"] == "urgent_clinician_review"


def test_no_notice_without_a_critical_flag():
    body = client.post(
        "/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What is my latest HbA1c?"}
    ).json()
    assert not body["answer"].startswith("Important: the lab marked")
