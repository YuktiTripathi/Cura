import json

from fastapi.testclient import TestClient

from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.core.errors import ProviderUnavailableError
from app.main import app
from app.providers.registry import build_registry, set_registry

client = TestClient(app)


LEAK_TOKENS = [
    "asyncpg",
    "psycopg",
    "5432",
    "DATABASE_URL",
    "SUPERSHYFT_DATABASE_URL",
    "VPN",
    "timed out",
    "TimeoutError",
    "sqlalchemy",
    "traceback",
    "secret_user",
    "SuperSecretPass",
]


def _failing_registry():
    class Boom:
        def get_profile(self, *args, **kwargs):
            raise ProviderUnavailableError()

        def query(self, *args, **kwargs):
            raise ProviderUnavailableError()

        def available_topics(self, *args, **kwargs):
            raise ProviderUnavailableError()

    reg = build_registry()
    boom = Boom()
    reg.users = boom
    reg.blood = boom
    reg.bio_ai = boom
    reg.lifestyle = boom
    return reg


def test_health_not_configured_has_no_credentials():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    ss = body["supershyft"]
    assert ss["configured"] is False
    assert ss["reachable"] is False
    assert ss["status"] == "missing"
    blob = json.dumps(body).lower()
    for token in ("password", "secret_user", "postgresql"):
        assert token not in blob


def test_health_unreachable_sanitized(monkeypatch):
    from app.core.config import settings
    from integrations.supershyft import db as ssdb
    from integrations.supershyft.db import SuperShyftDiagnostic, STATUS_UNREACHABLE

    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+asyncpg://secret_user:SuperSecretPass@187.77.185.240:5432/Supershyft_new",
    )

    def fake_probe():
        return SuperShyftDiagnostic(
            configured=True,
            reachable=False,
            query_ok=False,
            status=STATUS_UNREACHABLE,
            error="connection timeout",
            latency_ms=12,
        )

    monkeypatch.setattr(ssdb, "probe_supershyft", fake_probe)
    body = client.get("/health").json()
    ss = body["supershyft"]
    assert ss == {
        "configured": True,
        "reachable": False,
        "query_ok": False,
        "status": "unreachable",
        "error": "connection timeout",
    }
    blob = json.dumps(body)
    assert "SuperSecretPass" not in blob
    assert "secret_user" not in blob
    assert "187.77.185.240" not in blob
    assert "asyncpg" not in blob.lower()


def test_health_reachable(monkeypatch):
    from integrations.supershyft import db as ssdb
    from integrations.supershyft.db import SuperShyftDiagnostic, STATUS_REACHABLE

    monkeypatch.setattr(
        ssdb,
        "probe_supershyft",
        lambda: SuperShyftDiagnostic(
            configured=True,
            reachable=True,
            query_ok=True,
            status=STATUS_REACHABLE,
            error=None,
            latency_ms=8,
        ),
    )
    ss = client.get("/health").json()["supershyft"]
    assert ss["configured"] is True
    assert ss["reachable"] is True
    assert ss["query_ok"] is True
    assert ss["status"] == "reachable"
    assert ss["error"] is None


def test_personal_query_reports_authentication_failure_without_leaking_url(monkeypatch):
    from app.core.config import settings
    from app.providers.registry import build_registry
    from integrations.supershyft import db as ssdb
    from integrations.supershyft.db import DB_AUTH_FAILED

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(
        settings,
        "supershyft_database_url",
        "postgresql+psycopg://secret_user:SuperSecretPass@127.0.0.1:5432/db",
    )
    ssdb.reset_engine()

    class BoomEngine:
        def connect(self):
            raise Exception("password authentication failed for user secret_user")

        def dispose(self):
            return None

    monkeypatch.setattr(ssdb, "get_supershyft_engine", lambda: BoomEngine())
    set_registry(build_registry())
    try:
        res = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "What is my LDL?"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] == PERSONAL_DATA_UNAVAILABLE
        assert body["meta"]["supershyft_called"] is True
        assert body["meta"]["db_status"] == DB_AUTH_FAILED
        assert body["meta"]["requires_personal_data"] is True
        blob = json.dumps(body)
        assert "SuperSecretPass" not in blob
        assert "secret_user" not in blob
    finally:
        set_registry(None)
        ssdb.reset_engine()


def test_personal_query_while_db_unavailable():
    set_registry(_failing_registry())
    try:
        res = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "What is my latest Vitamin D?"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] == PERSONAL_DATA_UNAVAILABLE
        assert body["meta"]["status"] == "provider_unavailable"
        assert not body["evidence"]
        blob = json.dumps(body).lower()
        for token in LEAK_TOKENS:
            assert token.lower() not in blob
    finally:
        set_registry(None)


def test_general_query_while_db_unavailable():
    set_registry(_failing_registry())
    try:
        res = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "5"},
            json={"message": "What is Vitamin D?"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["answer"] != PERSONAL_DATA_UNAVAILABLE
        assert "guess" not in body["answer"].lower()
        assert body["meta"]["intent"] == "general_health_question"
        blob = json.dumps(body).lower()
        for token in ("asyncpg", "psycopg", "database_url", "5432", "vpn"):
            assert token not in blob
    finally:
        set_registry(None)


def test_provider_unavailable_http_has_no_raw_exception():
    import asyncio

    from app.core.errors import cura_error_handler

    response = asyncio.run(
        cura_error_handler(
            None,  # type: ignore[arg-type]
            ProviderUnavailableError(
                "asyncpg.exceptions.ConnectionDoesNotExistError host=10.1.2.3 port=5432 password=SuperSecretPass"
            ),
        )
    )
    assert response.status_code == 503
    payload = json.loads(response.body)
    assert payload["error"]["message"] == PERSONAL_DATA_UNAVAILABLE
    blob = json.dumps(payload).lower()
    for token in LEAK_TOKENS:
        assert token.lower() not in blob
    assert payload["error"]["details"] == {}
