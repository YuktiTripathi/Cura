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


def test_model_is_not_asked_for_blocks_or_library_ids(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "semantic")
    # The model is no longer asked to build blocks or pick library ids; the backend derives them.
    for mode in ("plain", "rich", "semantic"):
        monkeypatch.setattr(settings, "cura_response_mode", mode)
        system = _system_for_mode(SAFETY_INSTRUCTIONS)
        assert "SEMANTIC RESPONSE" not in system and "LIBRARY_REFS" not in system


_LIBRARY = {"medical_education", "medical_relationship", "lifestyle_education"}


def _model_blocks(body):
    """Blocks the model asked for. Backend selected library education is checked separately."""
    return [b for b in body["semantic"]["blocks"] if b["type"] not in _LIBRARY]


def test_values_come_from_the_record_not_the_model(semantic, monkeypatch):
    _model(monkeypatch, summary="Your HbA1c is high.", blocks=[
        {"type": "insight", "title": "Connected", "text": "Glucose points the same way.",
         "evidence": ["blood.glucose.latest", "blood.made_up.latest"]},
        {"type": "metric", "evidence": ["blood.hba1c.latest"], "values": [{"value": 1.0}]},  # model values ignored
    ])
    body = _chat("What does my HbA1c mean?")
    blocks = _model_blocks(body)
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
    blocks = _model_blocks(_chat("What does my HbA1c mean?"))
    assert [b["type"] for b in blocks] == ["insight"]
    # Card text is not rewritten. The metric card with no record is the part that is dropped.
    assert "999" in blocks[0]["text"]


def test_no_blocks_means_the_whole_answer_is_the_summary(semantic, monkeypatch):
    _model(monkeypatch, summary="Short.", blocks=[])
    semantic_body = _chat("Why are my triglycerides high?")["semantic"]
    assert [b for b in semantic_body["blocks"] if b["type"] not in _LIBRARY] == []
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
    assert "How can I lower it?" in body["follow_ups"]
    assert {"type": "blood_report", "date": "2026-09-28", "label": None} in body["sources"]
    assert "How can I lower it?" not in body["summary"]


def test_plain_mode_keeps_the_answer_and_validated_blocks(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    _model(monkeypatch, summary="x", blocks=[{"type": "text", "text": "y"}])
    body = _chat("What does my HbA1c mean?")
    assert body["meta"]["response_mode"] == "rich"
    assert body["answer"]
    assert body["semantic"] is not None
    assert body["semantic"]["summary"] == body["answer"]
