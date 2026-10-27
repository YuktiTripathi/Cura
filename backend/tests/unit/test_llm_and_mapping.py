import pytest
from pydantic import ValidationError

from app.core.circuit_breaker import openrouter_breaker
from app.core.config import Settings, settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import (
    OpenAICompatibleLLMClient,
    message_text,
    strip_reasoning,
    uses_reasoning_tokens,
)
from integrations.supershyft.db import normalize_sync_url
from integrations.supershyft.mapping import bio_ai_from_row, markers_from_blood_parameters


def test_strip_qwen_think_tags():
    raw = "<think>internal</think>\nYour HbA1c is in range."
    assert strip_reasoning(raw) == "Your HbA1c is in range."


def test_message_text_skips_reasoning_parts():
    assert message_text({"content": [{"type": "reasoning", "text": "hidden"}, {"type": "text", "text": "visible"}]}) == "visible"
    assert uses_reasoning_tokens("openai/gpt-5-nano")
    assert uses_reasoning_tokens("openai/gpt-5-mini")
    assert uses_reasoning_tokens("google/gemini-3.8-flash")
    assert not uses_reasoning_tokens("google/gemini-2.5-flash")
    assert not uses_reasoning_tokens("google/gemini-3.1-flash")


def test_gemini_38_flash_uses_reasoning_output_cap():
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic")
    payload = client._build_payload([{"role": "user", "content": "synthetic"}], "json_schema")
    assert payload["max_tokens"] == settings.llm_max_output_tokens + settings.llm_reasoning_output_cap
    assert payload["reasoning"] == {"effort": settings.llm_reasoning_effort or "low"}
    plain = OpenAICompatibleLLMClient(model="openai/gpt-4o-mini", api_key="synthetic")
    assert plain._build_payload([{"role": "user", "content": "synthetic"}], "plain")["max_tokens"] == settings.llm_max_output_tokens


def test_normalize_asyncpg_url():
    url = normalize_sync_url("postgresql+asyncpg://u:p@host:5432/db")
    assert url.startswith("postgresql+psycopg://")


def test_cura_conversation_store_rejects_asyncpg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/SuperShyft_new")
    with pytest.raises(ValidationError, match="SUPERSHYFT_DATABASE_URL"):
        Settings()


def test_settings_keep_sqlite_when_supershyft_url_is_separate(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./cura.db")
    monkeypatch.setenv(
        "SUPERSHYFT_DATABASE_URL",
        "postgresql+asyncpg://u:p@localhost:5432/SuperShyft_new",
    )
    loaded = Settings()
    assert loaded.cura_database_is_sqlite()
    assert loaded.supershyft_database_url.startswith("postgresql+asyncpg://")


class _R:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_flat_blood_parameters():
    markers = markers_from_blood_parameters(
        {"haemoglobin": 13.2, "haemoglobin_unit": "g/dL", "ldl": 145, "ldl_unit": "mg/dL"}
    )
    keys = {m.key for m in markers}
    assert "hemoglobin" in keys
    assert "ldl" in keys
    hb = next(m for m in markers if m.key == "hemoglobin")
    assert hb.value == 13.2
    assert hb.unit == "g/dL"


def test_grouped_blood_parameters():
    markers = markers_from_blood_parameters(
        [
            {
                "group_name": "Lipid",
                "tests": [
                    {
                        "test_name": "LDL",
                        "parameter_key": "ldl",
                        "value": 142,
                        "unit": "mg/dL",
                        "lower_range": 0,
                        "higher_range": 100,
                    }
                ],
            }
        ]
    )
    assert markers[0].flag.value == "high"


def test_bio_ai_mapping():
    report = bio_ai_from_row(
        _R(
            report_id=9,
            created_at="2026-07-09",
            reports={
                "metabolic_age": 34,
                "metabolic_score": 62,
                "diseases": [{"code": "cardiac_health", "name": "Cardiac health", "score": 30, "status": "moderate"}],
            },
        )
    )
    assert report is not None
    assert report.metabolic_age == 34
    assert report.risks[0].code == "cardiac_health"


def test_llm_retries_transient_failure(monkeypatch):
    responses = [
        _Response(503, {}),
        _Response(200, {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 1}}),
    ]

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return responses.pop(0)

    instance = Client()
    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: instance)
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    monkeypatch.setattr(settings, "llm_allowed_models", f"{settings.llm_allowed_models},qwen")
    client = OpenAICompatibleLLMClient(
        provider="openai_compatible", base_url="http://local", model="qwen", api_key="test"
    )
    assert client._real_complete([{"role": "user", "content": "hello"}]) == "ok"
    assert client.last_usage["input_tokens"] == 3
    assert client.last_usage["output_tokens"] == 1
    assert client.last_usage["usage_reported"] is True


def test_llm_invalid_json_is_typed_failure(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return _Response(200, ValueError("bad json"))

    instance = Client()
    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: instance)
    client = OpenAICompatibleLLMClient(
        provider="openai_compatible", base_url="http://local", model="qwen", api_key="test"
    )
    with pytest.raises(LLMUnavailableError):
        client._real_complete([{"role": "user", "content": "hello"}])


def test_gpt5_payload_sets_low_reasoning_effort(monkeypatch):
    captured = {}

    class Client:
        def post(self, *args, **kwargs):
            captured["payload"] = kwargs["json"]
            captured["timeout"] = kwargs.get("timeout")
            return _Response(
                200,
                {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
            )

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    monkeypatch.setattr(settings, "llm_max_output_tokens", 800)
    monkeypatch.setattr(settings, "llm_allowed_models", f"{settings.llm_allowed_models},openai/gpt-5-nano")
    client = OpenAICompatibleLLMClient(
        provider="openrouter",
        base_url="http://local",
        model="openai/gpt-5-nano",
        api_key="test",
        timeout=12,
    )
    assert client._real_complete([{"role": "user", "content": "hello"}]) == "ok"
    assert captured["payload"]["reasoning"] == {"effort": "low"}
    assert captured["payload"]["max_tokens"] == settings.llm_max_output_tokens + settings.llm_reasoning_output_cap
    assert captured["payload"]["max_tokens"] >= 1200
    assert captured["timeout"] == 12


def test_empty_content_does_not_open_circuit(monkeypatch):
    openrouter_breaker.reset()

    class Client:
        def post(self, *args, **kwargs):
            return _Response(
                200,
                {
                    "choices": [{"message": {"content": "", "reasoning": "spent the budget thinking"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 400},
                },
            )

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="openai/gpt-5-mini", api_key="test"
    )
    with pytest.raises(LLMUnavailableError, match="empty answer"):
        client._real_complete([{"role": "user", "content": "hello"}])
    openrouter_breaker.allow()
    assert openrouter_breaker._state.open is False
    assert openrouter_breaker._state.failures == 0


def test_content_parts_are_used_as_visible_text(monkeypatch):
    class Client:
        def post(self, *args, **kwargs):
            return _Response(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "reasoning", "text": "internal"},
                                    {"type": "output_text", "text": "Your LDL is in range."},
                                ]
                            }
                        }
                    ],
                    "usage": {},
                },
            )

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    monkeypatch.setattr(settings, "llm_allowed_models", f"{settings.llm_allowed_models},openai/gpt-5-nano")
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="openai/gpt-5-nano", api_key="test"
    )
    assert client._real_complete([{"role": "user", "content": "hello"}]) == "Your LDL is in range."


def test_truncated_finish_reason_is_internal_failure(monkeypatch):
    class Client:
        def post(self, *args, **kwargs):
            return _Response(
                200,
                {
                    "choices": [{"message": {"content": "partial"}, "finish_reason": "length"}],
                    "usage": {},
                },
            )

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="openai/gpt-5-mini", api_key="test"
    )
    with pytest.raises(LLMUnavailableError, match="truncated"):
        client._real_complete([{"role": "user", "content": "hello"}])


def test_json_schema_400_falls_back_without_opening_circuit(monkeypatch):
    openrouter_breaker.reset()
    posts = []

    class Client:
        def post(self, *args, **kwargs):
            payload = kwargs["json"]
            posts.append(payload)
            fmt = (payload.get("response_format") or {}).get("type")
            if fmt == "json_schema":
                return _Response(
                    400,
                    {"error": {"message": "No endpoints found that support the requested parameters"}},
                )
            return _Response(
                200,
                {"choices": [{"message": {"content": '{"answer":"Vitamin D helps the body absorb calcium."}'}}]},
            )

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    monkeypatch.setattr(settings, "llm_json_schema_output", True)
    monkeypatch.setattr(settings, "openrouter_require_parameters", False)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", OpenAICompatibleLLMClient._real_complete)
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="openai/gpt-5-mini", api_key="test"
    )
    parsed = client.complete_structured([{"role": "user", "content": "What does Vitamin D do?"}])
    assert "absorb calcium" in parsed.answer
    assert posts[0]["response_format"]["type"] == "json_object"
    assert len(posts) == 1
    assert "require_parameters" not in (posts[0].get("provider") or {})
    openrouter_breaker.allow()
    assert openrouter_breaker._state.open is False


def test_schema_capable_model_falls_back_once_on_http_400(monkeypatch):
    openrouter_breaker.reset()
    posts = []

    class Client:
        def post(self, *args, **kwargs):
            payload = kwargs["json"]
            posts.append(payload)
            fmt = (payload.get("response_format") or {}).get("type")
            if fmt == "json_schema":
                return _Response(400, {"error": {"message": "unsupported"}})
            return _Response(200, {"choices": [{"message": {"content": '{"answer":"ok"}'}}], "usage": {}})

    monkeypatch.setattr("app.llm.openai_compatible.get_http_client", lambda: Client())
    monkeypatch.setattr(settings, "llm_json_schema_output", True)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", OpenAICompatibleLLMClient._real_complete)
    client = OpenAICompatibleLLMClient(
        provider="openrouter", base_url="http://local", model="openai/gpt-4o-mini", api_key="test"
    )
    parsed = client.complete_structured([{"role": "user", "content": "What does Vitamin D do?"}])
    assert parsed.answer == "ok"
    assert posts[0]["response_format"]["type"] == "json_schema"
    assert posts[1]["response_format"]["type"] == "json_object"
    assert client.last_usage.get("usage_reported") is False
    openrouter_breaker.allow()


def test_privacy_flags_are_configured():
    loaded = Settings()
    assert hasattr(loaded, "openrouter_zero_data_retention")
    assert hasattr(loaded, "openrouter_data_collection_deny")
    assert hasattr(loaded, "require_zdr_for_personal_health")


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload
