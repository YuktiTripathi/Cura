"""The LangChain sequence and the native path must give the same chat response."""
import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.orchestration import chain as chain_module

client = TestClient(app)
QUESTIONS = json.load(open("tests/fixtures/plan_eval_questions.json"))
_UUID = re.compile(r"ev-[0-9a-f]{8}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_VOLATILE = {"timing", "debug", "marks", "request_id", "conversation_id", "message_id", "id", "created_at", "latency_ms", "perf", "timings", "generated_at", "timestamp", "trace_id", "total_ms", "stages_ms"}


def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if k not in _VOLATILE and k != 'latency' and not k.endswith(('_ms', '_seconds'))}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, str):
        return _UUID.sub("<id>", value)
    if isinstance(value, float):
        return round(value, 6)
    return value


def _first_diff(a, b, path=""):
    if type(a) != type(b):
        return path, a, b
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                return path + "/" + key, a.get(key), b.get(key)
            found = _first_diff(a[key], b[key], path + "/" + key)
            if found:
                return found
    elif isinstance(a, list):
        if len(a) != len(b):
            return path, len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b)):
            found = _first_diff(x, y, f"{path}[{i}]")
            if found:
                return found
    elif a != b:
        return path, a, b
    return None


def _ask(engine, monkeypatch, turns):
    monkeypatch.setattr(settings, "orchestration_engine", engine)
    out, conversation = [], None
    for text in turns:
        body = {"message": text, **({"conversation_id": conversation} if conversation else {})}
        data = client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json=body).json()
        conversation = data.get("conversation_id")
        out.append(_clean(data))
    return out


@pytest.fixture(autouse=True)
def stub_model(monkeypatch):
    monkeypatch.setattr(settings, "cura_prompt_variant", "house")
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(
        OpenAICompatibleLLMClient, "complete",
        lambda self, messages, json_mode=False: "Here is the answer.\n\n- Your result is shown below.\n- Small steady steps help.",
    )


def test_every_question_and_chain_gives_the_same_response_on_both_engines(monkeypatch):
    pytest.importorskip("langchain_core")
    # Every fourth question and every chain by default; CURA_FULL_PARITY=1 runs all 57 (about 2.5 minutes).
    singles = QUESTIONS["single"] if os.environ.get("CURA_FULL_PARITY") else QUESTIONS["single"][::4]
    turns = [[q] for q in singles] + [list(chain) for chain in QUESTIONS["chains"]]
    for conversation in turns:
        native = _ask("native", monkeypatch, conversation)
        langchain = _ask("langchain", monkeypatch, conversation)
        assert langchain == native, (conversation, _first_diff(native, langchain))


def test_langchain_engine_really_runs_the_sequence(monkeypatch):
    pytest.importorskip("langchain_core")
    calls = []
    real = chain_module.run_chat_chain
    monkeypatch.setattr("app.orchestration.chain.run_chat_chain", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    monkeypatch.setattr(settings, "orchestration_engine", "langchain")
    client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What is my LDL?"})
    assert calls


def test_errors_propagate_unchanged_and_nothing_is_retried(monkeypatch):
    pytest.importorskip("langchain_core")
    attempts = []

    def boom(self, principal, payload, request_id, eval_turn):
        attempts.append(1)
        raise RuntimeError("boom")

    from app.pipeline.service import ChatService
    monkeypatch.setattr(ChatService, "_execute_chat", boom)
    monkeypatch.setattr(settings, "orchestration_engine", "langchain")
    with pytest.raises(RuntimeError, match="boom"):
        TestClient(app, raise_server_exceptions=True).post(
            "/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What is my LDL?"}
        )
    assert len(attempts) == 1


def test_native_is_used_when_langchain_is_missing_or_switched_off(monkeypatch):
    from app.pipeline import service

    monkeypatch.setattr(settings, "orchestration_engine", "langchain")
    monkeypatch.setattr(chain_module, "langchain_available", lambda: False)
    assert service._use_langchain() is False
    monkeypatch.setattr(chain_module, "langchain_available", lambda: True)
    monkeypatch.setattr(settings, "orchestration_engine", "native")
    assert service._use_langchain() is False


def test_tracing_is_off_and_no_callbacks_see_the_state(monkeypatch):
    pytest.importorskip("langchain_core")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-secret")
    chain_module.build_chain()
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        assert os.environ[name] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ
