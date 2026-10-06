"""Readiness plan: RS256/JWKS auth (1.8), load shedding (5.3), metrics (5.6), prompt layout (6)."""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import jwt as cura_jwt
from app.core.config import settings
from app.core.errors import OverloadedError, UnauthorizedError
from app.core.request_controls import ChatCapacity
from app.main import app

client = TestClient(app)
PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Key:
    def __init__(self, key):
        self.key = key


class _FakeJWKS:
    def get_signing_key_from_jwt(self, _token):
        return _Key(PRIVATE.public_key())


class _Req:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}
        self.cookies = {}


@pytest.fixture()
def jwks(monkeypatch):
    monkeypatch.setattr(settings, "auth_jwks_url", "https://auth.supershyft.example/.well-known/jwks.json")
    monkeypatch.setattr(settings, "auth_jwt_issuer", "https://auth.supershyft.example")
    monkeypatch.setattr(settings, "auth_jwt_audience", "cura")
    monkeypatch.setattr(settings, "auth_jwt_secret", "")
    monkeypatch.setattr(cura_jwt, "_jwks_client", lambda _url: _FakeJWKS())


def _token(key=PRIVATE, alg="RS256", **claims):
    base = {"sub": "42", "iss": "https://auth.supershyft.example", "aud": "cura", "exp": int(time.time()) + 300}
    base.update(claims)
    return jwt.encode({k: v for k, v in base.items() if v is not None}, key, algorithm=alg)


def test_rs256_token_from_jwks_is_accepted(jwks):
    principal = cura_jwt.SuperShyftJWTAuthProvider().authenticate(_Req(_token()))
    assert principal.subject_id == "42"


@pytest.mark.parametrize(
    "token_kwargs",
    [{"key": OTHER}, {"aud": "other"}, {"iss": "https://evil.example"}, {"exp": None}, {"aud": None}],
)
def test_jwks_rejects_bad_signature_or_missing_claims(jwks, token_kwargs):
    with pytest.raises(UnauthorizedError):
        cura_jwt.SuperShyftJWTAuthProvider().authenticate(_Req(_token(**token_kwargs)))


def test_jwks_path_rejects_hs256_tokens(jwks):
    forged = _token(key="x" * 48, alg="HS256")
    with pytest.raises(UnauthorizedError):
        cura_jwt.SuperShyftJWTAuthProvider().authenticate(_Req(forged))


def test_capacity_sheds_load_with_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "max_in_flight_chats", 1)
    capacity = ChatCapacity()
    capacity.acquire()
    with pytest.raises(OverloadedError) as excinfo:
        capacity.acquire()
    assert excinfo.value.status_code == 429 and excinfo.value.retry_after > 0
    capacity.release()
    capacity.acquire()


def test_overloaded_response_carries_retry_after_header(monkeypatch):
    from app.core import request_controls

    def full():
        raise OverloadedError(retry_after=3)

    monkeypatch.setattr(request_controls.chat_capacity, "acquire", full)
    res = client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "what is HbA1c"})
    assert res.status_code == 429 and res.headers["Retry-After"] == "3"


def test_metrics_endpoint_reports_stages_and_chats(monkeypatch):
    client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "what is HbA1c"})
    monkeypatch.setattr(settings, "metrics_token", "")
    body = client.get("/metrics").text
    assert "cura_chat_total" in body and "cura_stage_seconds" in body and "cura_http_request_seconds" in body
    monkeypatch.setattr(settings, "metrics_token", "m-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer m-token"}).status_code == 200


def test_prompt_puts_question_last_for_caching():
    from app.contracts.common import KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.pipeline.prompt_builder import PromptBuilder

    context = HealthContext.model_construct(
        knowledge_scope=KnowledgeScope.general, resolved_topic_name="HbA1c", medical_passages=[]
    )
    user = PromptBuilder().build(context, "", "what is HbA1c?")[1]["content"]
    assert user.rstrip().splitlines()[-1] == "User question: what is HbA1c?"
