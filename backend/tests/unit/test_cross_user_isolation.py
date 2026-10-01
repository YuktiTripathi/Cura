"""One user can never read, use or delete another user's uploaded documents or conversations."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)
OWNER = {"X-Cura-User-Id": "demo-user-001"}
OTHER = {"X-Cura-User-Id": "demo-user-002"}
SECRET_ROW = "LDL Cholesterol 199 mg/dL (ref < 100)"


@pytest.fixture
def owned(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    res = client.post(
        "/api/v1/documents",
        headers=OWNER,
        files={"file": ("private.pdf", io.BytesIO(make_text_pdf([["Private Lab Report - 12 Sep 2026", "Patient: owner", SECRET_ROW, "HbA1c 5.6 % (ref 4.0-5.6)"]])), "application/pdf")},
    )
    assert res.status_code == 200
    did = res.json()["document_id"]
    chat = client.post("/api/v1/chat", headers=OWNER, json={"message": "What is the LDL in my uploaded report?", "document_ids": [did]}).json()
    assert "199" in chat["answer"]
    return did, chat["conversation_id"]


@pytest.mark.parametrize("path", ["", "/facts", "/pages/1"])
def test_document_endpoints_are_owner_only(owned, path):
    did, _ = owned
    res = client.get(f"/api/v1/documents/{did}{path}", headers=OTHER)
    assert res.status_code == 404
    assert "199" not in res.text and "private.pdf" not in res.text


def test_document_list_and_delete_are_owner_only(owned):
    did, _ = owned
    assert did not in client.get("/api/v1/documents", headers=OTHER).text
    client.delete(f"/api/v1/documents/{did}", headers=OTHER)
    assert client.get(f"/api/v1/documents/{did}", headers=OWNER).status_code == 200


@pytest.mark.parametrize("message", ["What is the LDL in my uploaded report?", "Compare my uploaded report with my SuperShyft results"])
def test_chat_cannot_use_another_users_document(owned, message):
    did, _ = owned
    res = client.post("/api/v1/chat", headers=OTHER, json={"message": message, "document_ids": [did]})
    assert "199" not in res.text
    assert SECRET_ROW not in res.text
    assert "private.pdf" not in res.text


def test_conversations_are_owner_only(owned):
    _, cid = owned
    assert client.get(f"/api/v1/conversations/{cid}", headers=OTHER).status_code == 404
    assert cid not in client.get("/api/v1/conversations", headers=OTHER).text
    hijack = client.post("/api/v1/chat", headers=OTHER, json={"message": "What did I ask before?", "conversation_id": cid})
    assert hijack.status_code == 404
    assert "199" not in hijack.text
