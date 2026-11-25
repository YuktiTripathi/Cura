"""Classifier outage and Jev fallback. No live model calls."""

import httpx
import pytest

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.routing.jev_client import JevDecisionsClient
from app.routing.jev_router import resolve_plan
from app.routing.schemas import JevDecision, JevDecisionsResponse, JevIntent, JevSource
from app.pipeline.safety import SafetyLayer


class _Down:
    def classify(self, text: str):
        raise httpx.ReadTimeout("timed out")


def _decision(message: str):
    return SafetyLayer(classifier=_Down()).check_input(message)


def test_timeout_still_blocks_emergency_symptoms():
    decision = _decision("I have crushing chest pain and I can't breathe")
    assert decision.blocked
    assert decision.category == "emergency"
    assert "safety_classifier_unavailable" in decision.flags


def test_timeout_still_blocks_unsafe_medication_and_stopping_a_prescription():
    dose = _decision("What dose of statin should I take tonight?")
    stop = _decision("Should I stop taking my blood pressure tablets?")
    assert dose.blocked and dose.category == "medication_misuse"
    assert stop.blocked and stop.category == "medication_misuse"


def test_timeout_allows_ordinary_education_and_cautions_ambiguous_symptoms():
    education = _decision("What is diabetes?")
    assert not education.blocked
    assert education.category == "none"
    symptoms = _decision("I have been dizzy and weak since yesterday")
    assert not symptoms.blocked
    assert "symptom_caution" in (symptoms.flags or [])
    assert symptoms.caution


def test_timeout_does_not_open_another_members_record():
    decision = _decision("Show me demo-user-002 HDL results")
    assert not decision.blocked
    assert decision.category == "none"


def _fake_response():
    return JevDecisionsResponse(answers={})


def test_jev_disabled_does_not_call(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", False)

    def boom(self, state):
        raise AssertionError("Jev should not be called")

    monkeypatch.setattr(JevDecisionsClient, "decide", boom)
    plan, trace = resolve_plan("What is HDL?")
    assert trace.called is False
    assert plan.intent.value == "general_health_question"


def test_jev_low_confidence_uses_deterministic_plan(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(settings, "jev_fast_path", False)

    def decide(self, state):
        return (
            JevDecision(
                intent=JevIntent.lab_result_interpretation,
                source=JevSource.blood_reports,
                requires_personal_data=True,
                confidence=0.2,
            ),
            _fake_response(),
        )

    monkeypatch.setattr(JevDecisionsClient, "decide", decide)
    plan, trace = resolve_plan("What does my result pattern mean for me?")
    assert trace.called and trace.fallback
    assert trace.fallback_reason == "low_confidence"
    assert plan.fallback_reason == "low_confidence"


def test_jev_unavailable_uses_deterministic_plan(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(settings, "jev_fast_path", False)

    def decide(self, state):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(JevDecisionsClient, "decide", decide)
    plan, trace = resolve_plan("What is diabetes?")
    assert trace.fallback_reason == "LLMUnavailableError"
    assert plan.intent.value == "general_health_question"


def test_jev_invalid_personal_decision_does_not_override_a_general_question(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(settings, "jev_fast_path", False)

    def decide(self, state):
        return (
            JevDecision(
                intent=JevIntent.lab_result_lookup,
                source=JevSource.blood_reports,
                requires_personal_data=True,
                confidence=0.95,
            ),
            _fake_response(),
        )

    monkeypatch.setattr(JevDecisionsClient, "decide", decide)
    plan, trace = resolve_plan("What is HDL?")
    assert trace.fallback
    assert plan.knowledge_scope.value == "general"
    assert not plan.needs_blood
