"""Readiness plan 5.4: token streaming for low-risk general answers only."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm import openai_compatible
from app.main import app

CHUNKS = ["Regular sleep ", "helps recovery ", "and mood."]


def _sse_body() -> bytes:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n" for c in CHUNKS]
    lines.append(f"data: {json.dumps({'choices': [], 'usage': {'prompt_tokens': 50, 'completion_tokens': 9}})}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


@pytest.fixture()
def streaming(monkeypatch):
    monkeypatch.setattr(settings, "chat_streaming_mode", "tokens_low_risk")
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", False)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if body.get("stream"):
            return httpx.Response(200, content=_sse_body(), headers={"Content-Type": "text/event-stream"})
        return httpx.Response(500)

    monkeypatch.setattr(openai_compatible, "get_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return requests


def _events(message: str) -> list[tuple[str, dict]]:
    out = []
    with TestClient(app).stream(
        "POST", "/api/v1/chat/stream", headers={"X-Cura-User-Id": "stream-user"}, json={"message": message}
    ) as res:
        event = None
        for line in res.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event:
                out.append((event, json.loads(line[6:])))
    return out


def test_low_risk_general_answer_streams_tokens_then_the_checked_answer(streaming):
    events = _events("How much sleep do adults need?")
    tokens = [data["text"] for kind, data in events if kind == "token"]
    assert tokens == CHUNKS
    complete = next(data for kind, data in events if kind == "complete")
    assert "sleep" in complete["answer"].lower()
    assert streaming and streaming[0]["stream"] is True


def test_high_risk_topic_does_not_stream(streaming):
    events = _events("Is it safe to exercise during pregnancy?")
    assert not [1 for kind, _ in events if kind == "token"]


def test_default_mode_does_not_stream(streaming, monkeypatch):
    monkeypatch.setattr(settings, "chat_streaming_mode", "complete_only")
    events = _events("How much sleep do adults need?")
    assert not [1 for kind, _ in events if kind == "token"]


def _json_sse(answer: str, size: int = 6) -> bytes:
    raw = json.dumps({"answer": answer, "claims": [], "recommendation_candidates": [], "follow_up_questions": [], "safety_flags": [], "escalation": None})
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': raw[i:i + size]}}]})}\n\n" for i in range(0, len(raw), size)]
    lines.append(f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}\n\n")
    lines.append(f"data: {json.dumps({'choices': [], 'usage': {'prompt_tokens': 50, 'completion_tokens': 9}})}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def test_structured_answer_text_streams_while_the_json_is_written(monkeypatch):
    answer = "- Sleep needs change with age.\n- Most adults do well with seven to nine hours."
    monkeypatch.setattr(openai_compatible.OpenAICompatibleLLMClient, "complete", openai_compatible.OpenAICompatibleLLMClient._real_complete)
    monkeypatch.setattr(settings, "chat_streaming_mode", "tokens_answer")
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", False)

    def handler(request):
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(200, content=_json_sse(answer), headers={"Content-Type": "text/event-stream"})
        return httpx.Response(500)

    monkeypatch.setattr(openai_compatible, "get_http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    events = _events("How much sleep do adults need?")
    streamed = "".join(data["text"] for kind, data in events if kind == "token")
    assert streamed == answer
    complete = next(data for kind, data in events if kind == "complete")
    assert "sleep" in complete["answer"].lower()
