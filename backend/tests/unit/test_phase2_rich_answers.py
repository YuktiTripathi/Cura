"""Phase 2 (rich answers) backend additions: early value preview over SSE, numeric reference
bounds on presented findings, and a page endpoint for the source viewer. All are additive."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)
USER = {"X-Cura-User-Id": "demo-user-001"}


def _stream(message: str, headers=USER, **extra) -> list[tuple[str, dict]]:
    res = client.post("/api/v1/chat/stream", headers=headers, json={"message": message, **extra})
    assert res.status_code == 200
    events = []
    for frame in res.text.split("\n\n"):
        name = next((line[7:] for line in frame.splitlines() if line.startswith("event: ")), None)
        data = next((line[6:] for line in frame.splitlines() if line.startswith("data: ")), None)
        if name and data:
            events.append((name, json.loads(data)))
    return events


def test_personal_lookup_streams_a_value_preview_before_the_answer():
    events = _stream("What is my LDL?")
    names = [name for name, _ in events]
    assert "preview" in names
    assert names.index("preview") < names.index("complete")
    preview = dict(events)["preview"]
    complete = dict(events)["complete"]
    ldl = next(item for item in preview["findings"] if item["canonical_key"] == "ldl")
    assert ldl["numeric_value"] is not None
    assert ldl["reference_high"] is not None
    # The preview shows the same value the final answer reports.
    assert f"{ldl['numeric_value']:g}" in complete["answer"] or ldl["value"] in complete["answer"]


@pytest.mark.parametrize("message", ["What does HbA1c measure?", "Summarize my health"])
def test_general_and_broad_questions_get_no_preview(message):
    names = [name for name, _ in _stream(message)]
    assert "preview" not in names
    assert names[-1] in {"answer", "complete"}


def test_presented_findings_carry_numeric_reference_bounds():
    chat = client.post("/api/v1/chat", headers=USER, json={"message": "What is my LDL?"}).json()
    findings = (chat.get("presentation") or {}).get("findings") or []
    ldl = next(item for item in findings if item.get("canonical_key") == "ldl")
    assert isinstance(ldl["numeric_value"], float)
    assert ldl["reference_low"] is not None or ldl["reference_high"] is not None


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    return tmp_path / "uploads"


def _upload(lines_per_page, user="user-pages"):
    res = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": user},
        files={"file": ("labs.pdf", io.BytesIO(make_text_pdf(lines_per_page)), "application/pdf")},
    )
    assert res.status_code == 200
    return res.json()["document_id"]


def test_document_page_returns_the_text_that_evidence_excerpts_quote(storage_dir):
    did = _upload([["Lab Report", "LDL Cholesterol 142 mg/dL (ref < 100)"], ["HbA1c 5.6 % (ref 4.0-5.6)"]])
    headers = {"X-Cura-User-Id": "user-pages"}
    page2 = client.get(f"/api/v1/documents/{did}/pages/2", headers=headers)
    assert page2.status_code == 200
    body = page2.json()
    assert body["page"] == 2 and body["page_count"] == 2 and body["filename"] == "labs.pdf"
    assert body["approximate"] is False

    chat = client.post(
        "/api/v1/chat", headers=headers, json={"message": "What is my HbA1c?", "document_ids": [did]}
    ).json()
    evidence = next(item for item in chat["evidence"] if item.get("document_id") == did)
    assert evidence["page_start"] == 2
    page_lines = client.get(f"/api/v1/documents/{did}/pages/{evidence['page_start']}", headers=headers).json()["text"]
    assert evidence["excerpt"] in page_lines.splitlines()


def test_document_page_is_owner_only_and_bounded(storage_dir):
    did = _upload([["LDL Cholesterol 142 mg/dL"]])
    assert client.get(f"/api/v1/documents/{did}/pages/1", headers={"X-Cura-User-Id": "someone-else"}).status_code == 404
    assert client.get(f"/api/v1/documents/{did}/pages/2", headers={"X-Cura-User-Id": "user-pages"}).status_code == 404
    assert client.get(f"/api/v1/documents/{did}/pages/0", headers={"X-Cura-User-Id": "user-pages"}).status_code == 404
