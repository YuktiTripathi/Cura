"""Plan 2.3: the model safety classifier runs in parallel with Jev routing."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.pipeline import safety_classifier, stages
from app.pipeline.safety_classifier import SafetyClassification

client = TestClient(app)
H = {"X-Cura-User-Id": "parallel-user"}


class SlowClassifier:
    def __init__(self, category="none", delay=0.0):
        self.category, self.delay, self.calls = category, delay, 0

    def classify(self, text):
        self.calls += 1
        time.sleep(self.delay)
        action = "urgent" if self.category == "emergency" else "allow"
        return SafetyClassification(self.category, "high", 0.9, "en", action)


@pytest.fixture()
def model_classifier(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "safety_llm_classifier_enabled", True)

    def install(classifier):
        monkeypatch.setattr(safety_classifier, "default_classifier", lambda: classifier)
        return classifier

    return install


def test_parallel_classifier_can_still_block(model_classifier):
    model_classifier(SlowClassifier("emergency", delay=0.1))
    body = client.post("/api/v1/chat", headers=H, json={"message": "something feels very wrong with my dad"}).json()
    assert body["meta"]["status"] == "safety_block"
    assert body["meta"]["escalation"] == "urgent_care"
    assert body["meta"]["supershyft_called"] is False


def test_rule_hit_blocks_without_starting_the_classifier(model_classifier):
    fake = model_classifier(SlowClassifier("none"))
    body = client.post("/api/v1/chat", headers=H, json={"message": "I have chest pain and my left arm is numb"}).json()
    assert body["meta"]["status"] == "safety_block"
    assert fake.calls == 0


def test_routing_and_classifier_overlap(model_classifier, monkeypatch):
    model_classifier(SlowClassifier("none", delay=0.5))
    original = stages.RouteStage.run

    def slow_route(self, *args, **kwargs):
        time.sleep(0.5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(stages.RouteStage, "run", slow_route)
    started = time.perf_counter()
    body = client.post("/api/v1/chat", headers=H, json={"message": "What does LDL stand for?"}).json()
    elapsed = time.perf_counter() - started
    assert body["meta"]["status"] != "safety_block"
    assert elapsed < 0.95, f"expected overlap, took {elapsed:.2f}s"
