import inspect
import json

from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.user import UserProfile
from app.core.copy import GREETING_FALLBACK, greeting_for_first_name
from app.core.errors import ProviderUnavailableError
from app.main import app
from app.pipeline import me_service
from app.providers.registry import build_registry, set_registry

client = TestClient(app)

LEAK_TOKENS = [
    "asyncpg",
    "psycopg",
    "5432",
    "DATABASE_URL",
    "VPN",
    "timed out",
    "SuperSecretPass",
    "secret_user",
]


def test_me_requires_auth():
    res = client.get("/api/v1/me")
    assert res.status_code == 401


def test_me_uses_auth_header_not_hardcoded_user():
    res = client.get("/api/v1/me", headers={"X-Cura-User-Id": "99"})
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == 99


def test_me_mock_user_first_name_and_greeting():
    res = client.get("/api/v1/me", headers={"X-Cura-User-Id": "demo-user-001"})
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == "demo-user-001"
    assert body["first_name"] == "Alex"
    assert body["greeting"] == "Hi Alex 👋"
    assert body["profile_available"] is True
    assert body["capabilities"]["has_blood_report"] is True
    assert body["capabilities"]["has_bio_ai_report"] is True
    assert body["capabilities"]["has_questionnaire"] is False
    assert body["capabilities"]["has_health_scenario"] is True


def test_me_missing_profile_fallback():
    res = client.get("/api/v1/me", headers={"X-Cura-User-Id": "5"})
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == 5
    assert body["first_name"] is None
    assert body["greeting"] == GREETING_FALLBACK
    assert "Alex" not in json.dumps(body)
    assert body["greeting"] != "Hi, User 👋"


def test_me_greeting_helper():
    assert greeting_for_first_name("Yukti") == "Hi Yukti 👋"
    assert greeting_for_first_name(None) == GREETING_FALLBACK
    assert greeting_for_first_name("  ") == GREETING_FALLBACK


def test_me_provider_unavailable_safe():
    class BoomUsers:
        def get_profile(self, principal):
            raise ProviderUnavailableError(
                "asyncpg connection timed out host=10.1.2.3 port=5432 password=SuperSecretPass"
            )

    reg = build_registry()
    reg.users = BoomUsers()
    set_registry(reg)
    try:
        res = client.get("/api/v1/me", headers={"X-Cura-User-Id": "5"})
        assert res.status_code == 200
        body = res.json()
        assert body["greeting"] == GREETING_FALLBACK
        assert body["first_name"] is None
        assert body["profile_available"] is False
        blob = json.dumps(body).lower()
        for token in LEAK_TOKENS:
            assert token.lower() not in blob
    finally:
        set_registry(None)


def test_me_profile_from_provider_not_auth_map():
    class Named:
        def get_profile(self, principal: AuthenticatedPrincipal):
            assert principal.subject_id == "5"
            return UserProfile(
                subject_id=principal.subject_id,
                display_name="Yukti",
                first_name="Yukti",
                last_name="Tripathi",
            )

        def available_topics(self, principal):
            return []

    class Empty:
        def query(self, *args, **kwargs):
            return []

    class EmptyLife:
        def query(self, *args, **kwargs):
            return None

    reg = build_registry()
    reg.users = Named()
    reg.blood = Empty()
    reg.bio_ai = Empty()
    reg.lifestyle = EmptyLife()
    set_registry(reg)
    try:
        res = client.get("/api/v1/me", headers={"X-Cura-User-Id": "5"})
        body = res.json()
        assert body["first_name"] == "Yukti"
        assert body["last_name"] == "Tripathi"
        assert body["display_name"] == "Yukti"
        assert body["greeting"] == "Hi Yukti 👋"
        assert body["user_id"] == 5
        assert body["capabilities"]["has_blood_report"] is False
    finally:
        set_registry(None)


def test_build_me_does_not_hardcode_user_five():
    source = inspect.getsource(me_service)
    assert "user_id = 5" not in source
    assert "= 5" not in source
