"""Semantic response: CURA decides meaning, the backend guarantees values, blocks are optional."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS, _system_for_mode

client = TestClient(app)
USER = "eval-user-companion"


@pytest.fixture
def semantic(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "semantic")


def _model(monkeypatch, **out):
    seen = []

    def complete(self, messages):
        seen.append(messages)
        return LLMStructuredOutput(**{"answer": "Your HbA1c is above your report's range.\n\nGlucose agrees.", **out})

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete)
    return seen


def _chat(message):
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": USER}, json={"message": message}).json()


def test_block_contract_is_only_asked_for_in_semantic_mode(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "semantic")
    assert "SEMANTIC RESPONSE" in _system_for_mode(SAFETY_INSTRUCTIONS)
    for mode in ("plain", "rich"):
        monkeypatch.setattr(settings, "cura_response_mode", mode)
        assert "SEMANTIC RESPONSE" not in _system_for_mode(SAFETY_INSTRUCTIONS)


def test_values_come_from_the_record_not_the_model(semantic, monkeypatch):
    _model(monkeypatch, summary="Your HbA1c is high.", blocks=[
        {"type": "insight", "title": "Connected", "text": "Glucose points the same way.",
         "evidence": ["blood.glucose.latest", "blood.made_up.latest"]},
        {"type": "metric", "evidence": ["blood.hba1c.latest"], "values": [{"value": 1.0}]},  # model values ignored
    ])
    body = _chat("What does my HbA1c mean?")
    blocks = body["semantic"]["blocks"]
    assert [b["type"] for b in blocks] == ["insight", "metric"]
    assert blocks[0]["evidence"] == ["blood.glucose.latest"]  # unknown key dropped
    assert blocks[0]["values"][0]["value"] == 214.47
    assert blocks[1]["values"][0]["value"] == 9.1 and blocks[1]["values"][0]["reference_high"] == 5.6
    assert body["answer"].startswith("Your HbA1c")  # the raw conversational answer is unchanged


def test_invalid_blocks_and_invented_numbers_are_removed(semantic, monkeypatch):
    _model(monkeypatch, summary="Your HbA1c is high.", blocks=[
        {"type": "carousel", "items": []},
        {"type": "metric", "evidence": ["blood.nothing.latest"]},
        {"type": "insight", "text": "Your LDL is 999 mg/dL. Glucose points the same way."},
        {"type": "nutrition", "increase": [], "reduce": []},
    ])
    blocks = _chat("What does my HbA1c mean?")["semantic"]["blocks"]
    assert [b["type"] for b in blocks] == ["insight"]
    assert "999" not in blocks[0]["text"]


def test_no_blocks_means_the_whole_answer_is_the_summary(semantic, monkeypatch):
    _model(monkeypatch, summary="Short.", blocks=[])
    semantic_body = _chat("Why are my triglycerides high?")["semantic"]
    assert semantic_body["blocks"] == []
    assert "Glucose agrees." in semantic_body["summary"]  # nothing hidden


def test_block_count_is_capped(semantic, monkeypatch):
    many = [{"type": "reassurance", "text": f"Point {i}."} for i in range(9)]
    _model(monkeypatch, summary="Several points.", blocks=many)
    assert len(_chat("What is reassuring in my health data?")["semantic"]["blocks"]) <= 4


def test_blood_report_is_summary_abnormal_and_collapsed_full_list(semantic):
    body = _chat("Show me my latest blood report.")
    blocks = body["semantic"]["blocks"]
    assert [b["type"] for b in blocks] == ["metric_group", "metric_group"]
    assert all(v["status"] in {"high", "low", "critical"} for v in blocks[0]["values"])
    assert blocks[1]["collapsed"] is True and len(blocks[1]["values"]) > len(blocks[0]["values"])


def test_follow_ups_and_sources_are_separate(semantic, monkeypatch):
    _model(monkeypatch, summary="Your HbA1c is high.", follow_up_questions=["How can I lower it?"])
    body = _chat("What does my HbA1c mean?")["semantic"]
    assert body["follow_ups"] == ["How can I lower it?"]
    assert {"type": "blood_report", "date": "2026-09-28", "label": None} in body["sources"]
    assert "How can I lower it?" not in body["summary"]


def test_plain_mode_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    _model(monkeypatch, summary="x", blocks=[{"type": "text", "text": "y"}])
    body = _chat("What does my HbA1c mean?")
    assert body["semantic"] is None and body["meta"]["response_mode"] == "plain"
