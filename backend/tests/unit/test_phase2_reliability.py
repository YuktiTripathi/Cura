"""Phase 2 cache identity, document isolation, and request-scoped document listing."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.core.config import settings
from app.documents.service import DocumentService, reset_request_document_list
from app.main import app
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)


def test_same_question_on_two_pdfs_does_not_reuse_the_other_value(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "answer_cache_ttl_seconds", 60)
    monkeypatch.setattr(settings, "enable_llm", False)
    user = {"X-Cura-User-Id": "phase2-doc-user"}
    first = make_text_pdf(["Lipid Profile LDL cholesterol 118 mg/dL"])
    second = make_text_pdf(["Lipid Profile LDL cholesterol 160 mg/dL"])

    def upload(data, name):
        return client.post(
            "/api/v1/documents",
            headers=user,
            files={"file": (name, io.BytesIO(data), "application/pdf")},
        ).json()["document_id"]

    left = upload(first, "a.pdf")
    right = upload(second, "b.pdf")
    question = "What is my LDL in this report?"
    answer_a = client.post(
        "/api/v1/chat",
        headers=user,
        json={"message": question, "document_ids": [left]},
    ).json()["answer"]
    answer_b = client.post(
        "/api/v1/chat",
        headers=user,
        json={"message": question, "document_ids": [right]},
    ).json()["answer"]
    assert "118" in answer_a
    assert "160" not in answer_a
    assert "160" in answer_b
    assert "118" not in answer_b


def test_explicit_pdf_does_not_answer_another_users_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "enable_llm", False)
    data = make_text_pdf(["Lipid Profile LDL cholesterol 118 mg/dL"])
    owner = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "pdf-owner"},
        files={"file": ("same.pdf", io.BytesIO(data), "application/pdf")},
    ).json()["document_id"]
    denied = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "pdf-other"},
        json={"message": "What is my LDL in this report?", "document_ids": [owner]},
    )
    assert denied.status_code in {403, 404}
    assert "118" not in denied.text


def test_uploaded_report_without_ldl_is_not_invented(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "enable_llm", False)
    data = make_text_pdf(["Complete blood count hemoglobin 13.2 g/dL"])
    did = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "pdf-missing"},
        files={"file": ("cbc.pdf", io.BytesIO(data), "application/pdf")},
    ).json()["document_id"]
    answer = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "pdf-missing"},
        json={"message": "What is my LDL in this report?", "document_ids": [did]},
    ).json()["answer"]
    assert "118" not in answer
    assert "160" not in answer


def test_document_list_is_request_scoped_and_user_specific(monkeypatch):
    calls = {"n": 0}
    original = DocumentService.list_for_user

    def counted(self, user_id):
        calls["n"] += 1
        return original(self, user_id)

    monkeypatch.setattr(DocumentService, "list_for_user", counted)
    reset_request_document_list()
    client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What is my HbA1c?"})
    first = calls["n"]
    client.post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-002"}, json={"message": "What is my HbA1c?"})
    assert calls["n"] > first
