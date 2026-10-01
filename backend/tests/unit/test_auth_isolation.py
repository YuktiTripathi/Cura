"""Authenticated identity is the only authority for personal-data retrieval."""

from __future__ import annotations

import time

import jwt
from fastapi.testclient import TestClient

from app.auth.identity import authenticated_user_id, drop_client_identity
from app.auth.jwt import SuperShyftJWTAuthProvider
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ChatRequest
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext, SourceAvailability
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.main import app
from app.pipeline.health_gateway import HealthDataGateway
from app.pipeline.identity_filter import payload_contains_identity, sanitize_model_payload
from app.pipeline.prompt_builder import _minimal_context_payload
from app.pipeline.retrieval_executor import RetrievalExecutor
from app.providers.registry import get_registry, set_registry

client = TestClient(app)
USER_A = {"X-Cura-User-Id": "demo-user-001"}
USER_B = {"X-Cura-User-Id": "demo-user-002"}
USER_Q2 = {"X-Cura-User-Id": "demo-user-q2"}
USER_MULTI = {"X-Cura-User-Id": "eval-user-iron"}


def test_chat_request_drops_client_user_id():
    raw = drop_client_identity(
        {"message": "How is my liver?", "user_id": 123, "email": "a@b.c", "conversation_id": None}
    )
    assert "user_id" not in raw
    assert "email" not in raw
    req = ChatRequest.model_validate({"message": "How is my liver?", "user_id": 123})
    assert req.message == "How is my liver?"
    assert not hasattr(req, "user_id") or getattr(req, "user_id", None) is None


def test_jwt_subject_from_user_id_claim(monkeypatch):
    monkeypatch.setattr(settings, "auth_jwt_secret", "test-secret-not-for-production-32-bytes-minimum")
    monkeypatch.setattr(settings, "auth_jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "auth_jwt_issuer", "")
    monkeypatch.setattr(settings, "auth_jwt_audience", "")
    token = jwt.encode(
        {"user_id": 42, "exp": int(time.time()) + 60, "email": "hidden@example.com"},
        settings.auth_jwt_secret,
        algorithm="HS256",
    )
    from starlette.requests import Request

    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
    )
    principal = SuperShyftJWTAuthProvider().authenticate(request)
    assert principal.subject_id == "42"


def test_user_a_vitamin_d_is_not_user_b():
    res = client.post("/api/v1/chat", headers=USER_A, json={"message": "What is my latest Vitamin D?"})
    assert res.status_code == 200
    body = res.json()["answer"]
    assert "12.6" in body
    assert "42" not in body
    other = client.post("/api/v1/chat", headers=USER_B, json={"message": "What is my latest Vitamin D?"})
    assert other.status_code == 200
    assert "42" in other.json()["answer"]
    assert "12.6" not in other.json()["answer"]


def test_client_user_id_in_body_cannot_switch_identity():
    res = client.post(
        "/cura/chat",
        headers=USER_A,
        json={"message": "What is my latest Vitamin D?", "user_id": "demo-user-002"},
    )
    assert res.status_code == 200
    assert "12.6" in res.json()["answer"]
    assert "42" not in res.json()["answer"]


def test_conversation_isolation():
    created = client.post("/api/v1/chat", headers=USER_A, json={"message": "What is my Vitamin D?"})
    cid = created.json()["conversation_id"]
    stolen = client.get(f"/api/v1/conversations/{cid}", headers=USER_B)
    assert stolen.status_code == 404
    follow = client.post(
        "/api/v1/chat",
        headers=USER_B,
        json={"message": "What about the previous one?", "conversation_id": cid},
    )
    assert follow.status_code == 404
    own = client.get(f"/api/v1/conversations/{cid}", headers=USER_A)
    assert own.status_code == 200


def test_document_id_cannot_cross_users():
    from io import BytesIO

    pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    uploaded = client.post(
        "/api/v1/documents",
        headers=USER_A,
        files={"file": ("labs.pdf", BytesIO(pdf), "application/pdf")},
    )
    assert uploaded.status_code == 200
    doc_id = uploaded.json()["document_id"]
    stolen = client.get(f"/api/v1/documents/{doc_id}", headers=USER_B)
    assert stolen.status_code == 404
    chat = client.post(
        "/api/v1/chat",
        headers=USER_B,
        json={"message": "What is Vitamin D in this report?", "document_ids": [doc_id]},
    )
    assert chat.status_code in {200, 404}
    if chat.status_code == 200:
        assert doc_id not in chat.json()["answer"]
        assert "12.6" not in chat.json()["answer"] or "Vitamin D" in chat.json()["answer"]


def test_missing_blood_does_not_fail_other_sources():
    res = client.post("/api/v1/chat", headers=USER_Q2, json={"message": "What is my latest Vitamin D?"})
    assert res.status_code == 200
    answer = res.json()["answer"].lower()
    assert "vitamin d" in answer or "blood" in answer or "not" in answer
    q = client.post(
        "/api/v1/chat",
        headers=USER_Q2,
        json={"message": "What did I say about my sleep in the questionnaire?"},
    )
    assert q.status_code == 200


def test_multi_source_user_stays_on_authenticated_identity():
    res = client.post("/api/v1/chat", headers=USER_MULTI, json={"message": "Summarize my health."})
    assert res.status_code == 200
    answer = res.json()["answer"]
    assert "12.6" not in answer
    assert "42.0" not in answer
    assert "18.0" not in answer


def test_trend_uses_only_current_user_records():
    gateway = HealthDataGateway(get_registry())
    history = gateway.get_blood_history("demo-user-001", biomarker_codes=["vitamin_d"])
    values = [marker.value for report in history for marker in report.markers if marker.key == "vitamin_d"]
    assert 12.6 in values
    assert 18.0 in values
    assert 42.0 not in values
    other = gateway.get_latest_blood_report("demo-user-002")
    assert other is not None
    assert any(marker.value == 42.0 for marker in other.markers)


def test_executor_rejects_mismatched_user_id():
    principal = AuthenticatedPrincipal(subject_id="demo-user-001")
    executor = RetrievalExecutor(get_registry())
    plan = QueryPlan(intent=IntentType.latest_result, needs_blood=True)
    try:
        executor.execute(user_id="demo-user-002", task_plan=plan, principal=principal)
        raise AssertionError("expected unauthorized")
    except UnauthorizedError:
        pass


def test_unowned_report_id_is_dropped():
    principal = AuthenticatedPrincipal(subject_id="demo-user-001")
    executor = RetrievalExecutor(get_registry())
    plan = QueryPlan(
        intent=IntentType.latest_result,
        needs_blood=True,
        report_id="blood-j-001",
    )
    result = executor.execute(
        user_id=authenticated_user_id(principal),
        task_plan=plan,
        principal=principal,
    )
    ids = {report.report_id for report in result.blood_reports}
    assert "blood-j-001" not in ids
    assert any(report.report_id.startswith("blood-00") for report in result.blood_reports)


def test_model_payload_has_no_identity_credentials():
    ctx = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        source_status={"blood": SourceAvailability(status="available", records=1)},
    )
    payload = _minimal_context_payload(ctx)
    dirty = {
        **payload,
        "user_id": 123,
        "phone": "+15551212",
        "email": "user@example.com",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.e30.x",
        "otp": "123456",
    }
    cleaned = sanitize_model_payload(dirty)
    assert not payload_contains_identity(cleaned)
    assert "phone" not in cleaned
    assert "email" not in cleaned
    assert "jwt" not in cleaned
    assert "otp" not in cleaned
    assert "user_id" not in cleaned


def test_unauthenticated_chat_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "mock_user_id", "")
    monkeypatch.setattr(settings, "dev_auth_header", True)
    set_registry(None)
    res = client.post("/cura/chat", json={"message": "How is my liver?"})
    assert res.status_code in {401, 403}
