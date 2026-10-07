"""Readiness plan 2.7: optional model judge for medication and diagnosis claims."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.pipeline import answer_judge
from app.pipeline.safety import ANSWER_JUDGE_FALLBACK, SafetyLayer


def _client(content: str) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})))


@pytest.fixture()
def judge_on(monkeypatch):
    monkeypatch.setattr(settings, "safety_answer_judge_enabled", True)
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", False)


def _patch_verdict(monkeypatch, verdict):
    monkeypatch.setattr(answer_judge, "judge_answer", lambda answer, client=None: verdict)


def test_unsafe_verdict_replaces_the_answer(judge_on, monkeypatch):
    _patch_verdict(monkeypatch, answer_judge.JudgeVerdict(unsafe=True, reason="diagnosis"))
    out, flags = SafetyLayer().review("Given these numbers, you are suffering from thyroid disease.")
    assert out == ANSWER_JUDGE_FALLBACK and "answer_judge_blocked" in flags


def test_safe_verdict_keeps_the_answer(judge_on, monkeypatch):
    _patch_verdict(monkeypatch, answer_judge.JudgeVerdict(unsafe=False))
    text = "Your HbA1c is 6.1%, which is above the reference range. Metformin is a common diabetes medicine."
    out, flags = SafetyLayer().review(text)
    assert out == text and "answer_judge_blocked" not in flags


def test_judge_outage_keeps_rule_checks_and_flags_it(judge_on, monkeypatch):
    _patch_verdict(monkeypatch, answer_judge.JudgeVerdict(unsafe=False, available=False))
    out, flags = SafetyLayer().review("Discuss your medication with your doctor.")
    assert "answer_judge_unavailable" in flags


def test_judge_only_runs_on_medicine_or_diagnosis_text(judge_on, monkeypatch):
    calls = []
    monkeypatch.setattr(answer_judge, "judge_answer", lambda answer, client=None: calls.append(1) or answer_judge.JudgeVerdict(False))
    SafetyLayer().review("Walking 30 minutes a day helps sleep.")
    assert calls == []


def test_judge_is_off_by_default():
    assert settings.safety_answer_judge_enabled is False


def test_judge_parses_model_output(judge_on):
    verdict = answer_judge.judge_answer("Take 500 mg twice daily.", client=_client('{"unsafe": true, "reason": "dose"}'))
    assert verdict.unsafe and verdict.reason == "dose" and verdict.available
    broken = answer_judge.judge_answer("Take 500 mg.", client=_client("not json"))
    assert broken.available is False
