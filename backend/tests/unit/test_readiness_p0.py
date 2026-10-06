"""Production readiness plan P0 items: config, read-only DB, consent, public meta, safe mode."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.invariants import assert_production_config, production_config_problems
from app.main import app

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def _prod(**overrides) -> Settings:
    base = dict(
        app_env="production",
        auth_provider="supershyft_jwt",
        health_provider="mock",
        auth_jwt_secret="k" * 48,
        auth_jwt_issuer="https://auth.supershyft.example",
        auth_jwt_audience="cura",
        enable_llm=True,
        openrouter_api_key="sk-or-v1-" + "a" * 40,
        openrouter_zero_data_retention=True,
        require_zdr_for_personal_health=True,
        document_encryption_key="e" * 44,
        document_storage_backend="s3",
        document_s3_bucket="cura-docs-ap-south-1",
        redis_url="redis://cache:6379/0",
        redis_required=True,
        database_url="postgresql+psycopg://cura:pw@db/cura",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_config_accepts_a_complete_setup():
    assert production_config_problems(_prod()) == []


@pytest.mark.parametrize(
    "overrides, fragment",
    [
        ({"auth_jwt_secret": "change-me"}, "AUTH_JWT_SECRET"),
        ({"openrouter_api_key": ""}, "OPENROUTER_API_KEY"),
        ({"openrouter_zero_data_retention": False}, "OPENROUTER_ZERO_DATA_RETENTION"),
        ({"require_zdr_for_personal_health": False}, "REQUIRE_ZDR_FOR_PERSONAL_HEALTH"),
        ({"health_provider": "supershyft", "supershyft_database_url": "postgresql://u:password@localhost/db"}, "SUPERSHYFT_DATABASE_URL"),
        ({"document_storage_backend": "local"}, "DOCUMENT_STORAGE_BACKEND"),
        ({"redis_required": False}, "REDIS_REQUIRED"),
        ({"database_url": "sqlite:///./cura.db"}, "DATABASE_URL"),
    ],
)
def test_production_refuses_dev_or_placeholder_values(overrides, fragment):
    with pytest.raises(RuntimeError, match=fragment):
        assert_production_config(_prod(**overrides))


def test_development_skips_production_checks():
    assert production_config_problems(Settings(app_env="development")) == []


def test_supershyft_sessions_are_read_only_with_statement_timeout():
    from integrations.supershyft.db import readonly_session_options

    options = readonly_session_options()
    assert "default_transaction_read_only=on" in options
    assert "statement_timeout=" in options


def test_chat_requires_consent_when_enforced(monkeypatch):
    monkeypatch.setattr(settings, "consent_required", True)
    headers = {"X-Cura-User-Id": f"consent-user-{uuid.uuid4().hex[:8]}"}
    blocked = client.post("/api/v1/chat", headers=headers, json={"message": "what is HbA1c"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CONSENT_REQUIRED"

    notice = client.get("/api/v1/consent", headers=headers).json()
    assert notice["accepted"] is False and notice["notice"]
    stale = client.post("/api/v1/consent", headers=headers, json={"version": "old", "accepted": True})
    assert stale.status_code == 409
    accepted = client.post(
        "/api/v1/consent", headers=headers, json={"version": notice["version"], "accepted": True}
    ).json()
    assert accepted["accepted"] is True
    assert client.post("/api/v1/chat", headers=headers, json={"message": "what is HbA1c"}).status_code == 200


def test_public_meta_hides_model_cost_and_routing(monkeypatch):
    monkeypatch.setattr(settings, "public_meta_only", True)
    meta = client.post("/api/v1/chat", headers=H, json={"message": "what is HbA1c"}).json()["meta"]
    for hidden in ("model", "provider", "estimated_cost_usd", "input_tokens", "jev_intent", "answer_model_tier", "debug"):
        assert meta.get(hidden) in (None, False, [], 0), hidden
    assert meta["request_id"]


def test_emergency_reply_carries_call_buttons_and_conversation_stays_in_safe_mode():
    first = client.post("/api/v1/chat", headers=H, json={"message": "my father collapsed and is not waking up"}).json()
    assert first["meta"]["status"] == "safety_block"
    numbers = {c["number"] for c in first["meta"]["emergency_contacts"]}
    assert {"112", "14416"} <= numbers
    follow = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "what is HbA1c", "conversation_id": first["conversation_id"]},
    ).json()
    assert "safe_mode" in follow["meta"]["safety_flags"]
    assert follow.get("testing_option") in (None, {}) or not follow["testing_option"].get("packages")


def test_high_risk_topic_without_evidence_is_redirected_in_prompt():
    from app.pipeline.prompt_builder import _medical_block

    class Ctx:
        medical_passages: list = []

    assert "HIGH RISK TOPIC" in _medical_block(Ctx(), "is this antibiotic safe in pregnancy")
    assert "General information:" in _medical_block(Ctx(), "how much sleep do adults need")
