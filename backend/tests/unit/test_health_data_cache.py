"""Readiness plan 5.5: short-lived per-member cache of Supershyft reads."""

from __future__ import annotations

import pytest

from app.auth.models import AuthenticatedPrincipal
from app.core import request_controls as rc
from app.core.config import settings
from app.core.request_controls import RequestControlStore
from app.pipeline.query_planner import build_query_plan
from app.providers.cache import cached_bio_ai, cached_blood, cached_lifestyle
from integrations.mock.bio_ai_provider import MockBioAIProvider
from integrations.mock.blood_provider import MockBloodProvider
from integrations.mock.lifestyle_provider import MockLifestyleProvider

ME = AuthenticatedPrincipal(subject_id="demo-user-001")


class Counting:
    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def query(self, principal, plan):
        self.calls += 1
        return self.inner.query(principal, plan)


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "health_data_cache_seconds", 90)
    monkeypatch.setattr(rc, "request_controls", RequestControlStore())


def test_repeat_reads_hit_the_cache_and_return_identical_data():
    inner = Counting(MockBloodProvider())
    blood = cached_blood(inner)
    plan = build_query_plan("What is my latest HbA1c?")
    first = blood.query(ME, plan)
    # Same plan reached by different wording: the question text is not part of the key.
    second = blood.query(ME, plan.model_copy(update={"raw_message": "and my hba1c again?"}))
    assert inner.calls == 1
    assert [r.model_dump() for r in first] == [r.model_dump() for r in second]


def test_different_plans_and_members_are_separate():
    inner = Counting(MockBloodProvider())
    blood = cached_blood(inner)
    blood.query(ME, build_query_plan("What is my latest HbA1c?"))
    blood.query(ME, build_query_plan("How has my LDL changed over time?"))
    blood.query(AuthenticatedPrincipal(subject_id="demo-user-002"), build_query_plan("What is my latest HbA1c?"))
    assert inner.calls == 3


def test_bio_ai_and_lifestyle_round_trip():
    bio_inner, life_inner = Counting(MockBioAIProvider()), Counting(MockLifestyleProvider())
    bio, life = cached_bio_ai(bio_inner), cached_lifestyle(life_inner)
    plan = build_query_plan("What are my risk scores?")
    assert [r.model_dump() for r in bio.query(ME, plan)] == [r.model_dump() for r in bio.query(ME, plan)]
    first, second = life.query(ME, plan), life.query(ME, build_query_plan("anything else"))
    assert (first.model_dump() if first else None) == (second.model_dump() if second else None)
    assert bio_inner.calls == 1 and life_inner.calls == 1


def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "health_data_cache_seconds", 0)
    inner = Counting(MockBloodProvider())
    blood = cached_blood(inner)
    plan = build_query_plan("What is my latest HbA1c?")
    blood.query(ME, plan)
    blood.query(ME, plan)
    assert inner.calls == 2
