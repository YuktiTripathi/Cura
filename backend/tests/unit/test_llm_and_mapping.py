import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient, strip_reasoning
from integrations.supershyft.db import normalize_sync_url
from integrations.supershyft.mapping import bio_ai_from_row, markers_from_blood_parameters


def test_strip_qwen_think_tags():
    raw = "<think>internal</think>\nYour HbA1c is in range."
    assert strip_reasoning(raw) == "Your HbA1c is in range."


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

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", Client)
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    client = OpenAICompatibleLLMClient(
        provider="openai_compatible", base_url="http://local", model="qwen", api_key="test"
    )
    assert client._real_complete([{"role": "user", "content": "hello"}]) == "ok"
    assert client.last_usage == {"input_tokens": 3, "output_tokens": 1}


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

    monkeypatch.setattr("app.llm.openai_compatible.httpx.Client", Client)
    client = OpenAICompatibleLLMClient(
        provider="openai_compatible", base_url="http://local", model="qwen", api_key="test"
    )
    with pytest.raises(LLMUnavailableError):
        client._real_complete([{"role": "user", "content": "hello"}])


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload
