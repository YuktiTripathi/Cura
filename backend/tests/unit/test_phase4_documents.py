"""Phase 4: extracted-values review endpoint and comparing a whole uploaded report with SuperShyft."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    return tmp_path / "uploads"


def _upload(user: str, pages) -> str:
    res = client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": user},
        files={"file": ("labs.pdf", io.BytesIO(make_text_pdf(pages)), "application/pdf")},
    )
    assert res.status_code == 200
    return res.json()["document_id"]


LINES = [
    "Lab Report - 12 Sep 2026",
    "LDL Cholesterol 142 mg/dL (ref < 100)",
    "HbA1c 5.6 % (ref 4.0-5.6)",
    "Vitamin D 18 ng/mL (ref 30-100)",
]


def test_document_facts_list_each_value_with_its_row(storage_dir):
    did = _upload("user-facts", [LINES])
    body = client.get(f"/api/v1/documents/{did}/facts", headers={"X-Cura-User-Id": "user-facts"}).json()
    assert body["ready"] is True and body["filename"] == "labs.pdf"
    rows = [(f["key"], f["value"], f["unit"], f["reference_low"], f["reference_high"], f["reference_text"], f["status"], f["page"], f["line"]) for f in body["facts"]]
    assert rows == [
        ("ldl", 142.0, "mg/dL", None, 100.0, "< 100", "high", 1, 2),
        ("hba1c", 5.6, "%", 4.0, 5.6, "4.0-5.6", "normal", 1, 3),
        ("vitamin_d", 18.0, "ng/mL", 30.0, 100.0, "30-100", "low", 1, 4),
    ]
    assert body["facts"][0]["excerpt"] == LINES[1]


def test_document_facts_are_owner_only(storage_dir):
    did = _upload("user-facts", [LINES])
    assert client.get(f"/api/v1/documents/{did}/facts", headers={"X-Cura-User-Id": "intruder"}).status_code == 404


def test_comparing_a_whole_report_compares_every_shared_marker(storage_dir):
    did = _upload("demo-user-001", [LINES])
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-001"},
        json={"message": "Compare my uploaded report with my SuperShyft results", "document_ids": [did]},
    ).json()
    assert chat["meta"]["status"] == "cross_source_comparison"
    answer = chat["answer"]
    for label in ("HbA1c", "LDL cholesterol", "Vitamin D"):
        assert label in answer
    assert "not found in the selected SuperShyft data" not in answer
    assert "SuperShyft 138" in answer  # demo user's latest SuperShyft LDL
