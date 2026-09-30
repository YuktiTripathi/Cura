"""Local development mock auth (user 2) without weakening production invariants."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth.mock import MockAuthProvider
from app.core.config import Settings, settings
from app.core.errors import UnauthorizedError
from app.core.invariants import (
    REFUSE_MOCK_AUTH_WITH_REAL_HEALTH,
    REFUSE_PRODUCTION_MOCK_AUTH_WITH_REAL_HEALTH,
    assert_safe_auth_health_pairing,
)
from app.main import app
from app.providers.registry import set_registry

client = TestClient(app)


def _http_request(headers: dict[str, str] | None = None) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": raw,
            "client": ("127.0.0.1", 123),
            "server": ("test", 80),
        }
    )


def test_development_mock_auth_creates_principal_user_2(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    principal = MockAuthProvider().authenticate(_http_request())
    assert principal.subject_id == "2"


def test_pinned_mock_user_ignores_header_without_override(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    principal = MockAuthProvider().authenticate(_http_request({"X-Cura-User-Id": "5"}))
    assert principal.subject_id == "2"


def test_header_override_requires_explicit_development_flag(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "allow_mock_header_override", True)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    principal = MockAuthProvider().authenticate(_http_request({"X-Cura-User-Id": "5"}))
    assert principal.subject_id == "5"


def test_empty_mock_user_id_still_uses_development_header(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    principal = MockAuthProvider().authenticate(_http_request({"X-Cura-User-Id": "demo-user-001"}))
    assert principal.subject_id == "demo-user-001"


def test_mock_auth_rejected_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    with pytest.raises(UnauthorizedError, match="development-only"):
        MockAuthProvider().authenticate(_http_request())


def test_development_mock_plus_supershyft_allowed_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "allow_mock_auth_with_real_health", True)
    assert_safe_auth_health_pairing(settings)


def test_development_mock_plus_supershyft_rejected_without_flag(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "allow_mock_auth_with_real_health", False)
    with pytest.raises(RuntimeError, match="real health provider"):
        assert_safe_auth_health_pairing(settings)
    assert "mock authentication" in REFUSE_MOCK_AUTH_WITH_REAL_HEALTH


def test_production_mock_plus_supershyft_rejected_even_with_allow(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "allow_mock_auth_with_real_health", True)
    monkeypatch.setattr(settings, "mock_user_id", "2")
    with pytest.raises(RuntimeError, match="production cannot use mock authentication"):
        assert_safe_auth_health_pairing(settings)
    assert "production cannot use mock authentication" in REFUSE_PRODUCTION_MOCK_AUTH_WITH_REAL_HEALTH


def test_production_settings_ignore_mock_user_id_and_allow_flag():
    cfg = Settings(
        _env_file=None,
        app_env="production",
        auth_provider="mock",
        health_provider="supershyft",
        allow_mock_auth_with_real_health=True,
        mock_user_id="2",
        allow_mock_header_override=True,
        database_url="sqlite:///./cura.db",
        supershyft_database_url="",
    )
    assert cfg.mock_user_id == ""
    assert cfg.allow_mock_auth_with_real_health is False
    assert cfg.allow_mock_header_override is False
    with pytest.raises(RuntimeError, match="production cannot use mock authentication"):
        assert_safe_auth_health_pairing(cfg)


def test_production_cannot_use_mock_user_id_to_bypass_auth(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "dev_auth_header", True)
    response = client.get("/api/v1/me")
    assert response.status_code == 403


def test_production_jwt_ignores_mock_user_id_and_header(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_provider", "supershyft_jwt")
    monkeypatch.setattr(settings, "auth_jwt_secret", "test-secret-not-for-production-32-bytes-minimum")
    monkeypatch.setattr(settings, "auth_jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "auth_jwt_issuer", "")
    monkeypatch.setattr(settings, "auth_jwt_audience", "")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "health_provider", "mock")
    set_registry(None)
    token = jwt.encode(
        {"sub": "demo-user-001", "exp": int(time.time()) + 60},
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    try:
        response = client.get(
            "/api/v1/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Cura-User-Id": "5",
            },
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == "demo-user-001"
    finally:
        set_registry(None)


def test_pinned_mock_user_reaches_api_without_header(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    set_registry(None)
    try:
        response = client.get("/api/v1/me")
        assert response.status_code == 200
        assert response.json()["user_id"] in {2, "2"}
        chat = client.post("/api/v1/chat", json={"message": "What is Vitamin D?"})
        assert chat.status_code == 200
    finally:
        set_registry(None)


def test_development_principal_reaches_supershyft_as_user_2(monkeypatch):
    captured: dict[str, object] = {}

    def fake_readonly(statement, params=None, fetch="all"):
        if params and "uid" in params:
            captured["uid"] = params["uid"]
        return None if fetch == "one" else []

    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "allow_mock_auth_with_real_health", True)
    monkeypatch.setattr(settings, "mock_user_id", "2")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    monkeypatch.setattr(settings, "dev_auth_header", True)
    monkeypatch.setattr(settings, "supershyft_database_url", "postgresql+psycopg://cura:cura@127.0.0.1:5432/unused")
    monkeypatch.setattr("integrations.supershyft.db.run_readonly", fake_readonly)
    monkeypatch.setattr("integrations.supershyft.ihr.run_readonly", fake_readonly)
    monkeypatch.setattr("integrations.supershyft.blood.run_readonly", fake_readonly)
    monkeypatch.setattr("integrations.supershyft.providers.run_readonly", fake_readonly)
    monkeypatch.setattr("integrations.supershyft.questionnaire.run_readonly", fake_readonly)
    from integrations.supershyft.ihr import reset_ihr_cache

    reset_ihr_cache()
    set_registry(None)
    try:
        response = client.post("/api/v1/chat", json={"message": "What is my LDL?"})
        assert response.status_code == 200
        assert captured.get("uid") == 2
        body = response.json()
        assert body["meta"]["supershyft_called"] is True
    finally:
        set_registry(None)


def test_user_isolation_still_uses_authenticated_principal(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_provider", "mock")
    monkeypatch.setattr(settings, "health_provider", "mock")
    monkeypatch.setattr(settings, "mock_user_id", "")
    monkeypatch.setattr(settings, "allow_mock_header_override", False)
    set_registry(None)
    try:
        created = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "demo-user-001"},
            json={"message": "What is Vitamin D?"},
        ).json()
        stolen = client.get(
            f"/api/v1/conversations/{created['conversation_id']}",
            headers={"X-Cura-User-Id": "demo-user-002"},
        )
        assert stolen.status_code == 404
        own = client.get(
            f"/api/v1/conversations/{created['conversation_id']}",
            headers={"X-Cura-User-Id": "demo-user-001"},
        )
        assert own.status_code == 200
    finally:
        set_registry(None)
