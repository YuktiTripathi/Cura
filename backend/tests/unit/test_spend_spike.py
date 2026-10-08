"""Readiness plan 6.7: deep answers try the standard tier first during a spend spike."""

from __future__ import annotations

import pytest

from app.contracts.common import AnswerModelTier
from app.core import request_controls as rc
from app.core.config import settings
from app.core.request_controls import RequestControlStore
from app.llm.registry import fallback_tiers


@pytest.fixture()
def store(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "answer_model_deep_medical", "anthropic/claude-sonnet-5")
    monkeypatch.setattr(settings, "spend_spike_hourly_usd", 1.0)
    fresh = RequestControlStore()
    monkeypatch.setattr(rc, "request_controls", fresh)
    return fresh


def test_deep_stays_deep_below_the_threshold(store):
    store.record_spend(0.40)
    # Deep is tried first; a very complex question has no smaller-model fallback.
    assert fallback_tiers(AnswerModelTier.deep_medical_reasoning, 12) == [AnswerModelTier.deep_medical_reasoning]
    assert fallback_tiers(AnswerModelTier.deep_medical_reasoning, 6)[0] == AnswerModelTier.deep_medical_reasoning


def test_deep_tries_standard_first_during_a_spike(store):
    for _ in range(5):
        store.record_spend(0.30)
    assert store.spend_last_hour_usd() > 1.0
    assert fallback_tiers(AnswerModelTier.deep_medical_reasoning) == [
        AnswerModelTier.standard_medical,
        AnswerModelTier.deep_medical_reasoning,
    ]


def test_no_downgrade_when_deep_and_standard_share_a_model(store, monkeypatch):
    monkeypatch.setattr(settings, "answer_model_deep_medical", settings.answer_model_standard_medical)
    store.record_spend(50.0)
    assert fallback_tiers(AnswerModelTier.deep_medical_reasoning) == [AnswerModelTier.deep_medical_reasoning]


def test_spike_check_can_be_disabled(store, monkeypatch):
    monkeypatch.setattr(settings, "spend_spike_hourly_usd", 0)
    store.record_spend(50.0)
    assert store.spend_spike_active() is False
