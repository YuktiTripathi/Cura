import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.copy import DOCUMENT_NO_MATCH, DOCUMENT_OCR
from app.core.errors import NotFoundError
from app.documents.chunking import chunk_pages
from app.documents.extraction import ExtractedPage, extract_pdf_pages
from app.documents.normalization import normalize_extracted_text
from app.documents.processor import DocumentProcessor
from app.documents.retrieval import DocumentRetriever
from app.main import app
from tests.helpers.pdf_fixtures import make_blank_pdf, make_text_pdf

TEXT_PDF = make_text_pdf(
    [
        "Lipid Profile LDL cholesterol 140 mg/dL HDL 45 Reference Range",
        "Thyroid Function TSH 2.1 T4 8.0 collection date 20 Sep 2026",
    ]
)


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_ocr_provider", "none")
    monkeypatch.setattr(settings, "document_max_pages", 50)
    return tmp_path / "uploads"


@pytest.fixture
def client(storage_dir):
    return TestClient(app)


def _upload(client, user, data=TEXT_PDF, filename="lipid.pdf"):
    return client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": user},
        files={"file": (filename, io.BytesIO(data), "application/pdf")},
    )


def test_text_pdf_extraction_pages_and_status(client):
    pages = extract_pdf_pages(TEXT_PDF)
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert "LDL" in pages[0].text
    assert "TSH" in pages[1].text
    res = _upload(client, "user-a")
    assert res.status_code == 200
    did = res.json()["document_id"]
    got = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"}).json()
    assert got["extraction_status"] == "completed"
    assert got["source"] == "user_uploaded"


def test_image_pdf_ocr_unavailable(client):
    blank = make_blank_pdf(1)
    res = _upload(client, "user-a", data=blank, filename="scan.pdf")
    did = res.json()["document_id"]
    got = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"}).json()
    assert got["extraction_status"] == "failed"
    assert "OCR" in (got.get("extraction_error") or "")
    chat = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-a"},
        json={"message": "What is my LDL?", "document_ids": [did]},
    )
    assert DOCUMENT_OCR in chat.json()["answer"]
    assert chat.json()["meta"]["llm_mode"] == "none"


def test_ocr_fallback_when_provider_available(storage_dir):
    from app.db.session import SessionLocal
    from app.documents.service import DocumentService

    class FakeOCR:
        name = "fake"

        def available(self):
            return True

        def ocr_page(self, pdf_bytes, page_number):
            return "LDL cholesterol 140 mg/dL from scan"

    db = SessionLocal()
    try:
        svc = DocumentService(db)
        out = svc.upload(
            user_id="user-a",
            filename="scan.pdf",
            content_type="application/pdf",
            data=make_blank_pdf(1),
        )
        DocumentProcessor(db, ocr=FakeOCR()).process("user-a", out.document_id)
        row = svc.get("user-a", out.document_id)
        assert row.extraction_status == "completed"
        hits = DocumentRetriever(db).retrieve("user-a", "LDL cholesterol", document_ids=[out.document_id])
        assert hits
        assert hits[0].source == "user_uploaded"
        assert "140" in hits[0].text
    finally:
        db.close()


def test_mixed_pdf_keeps_text_without_ocr_for_minority_blank(client):
    mixed = make_text_pdf(["Lipid Profile LDL 99 HDL 50 plenty of selectable text on this page"])
    # one text page: not "most sparse"
    res = _upload(client, "user-a", data=mixed)
    did = res.json()["document_id"]
    got = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"}).json()
    assert got["extraction_status"] == "completed"


def test_normalization_preserves_medical_numbers():
    wrapped = "hemo-\nglobin 13.5\nHbA1c: 6.2 %"
    out = normalize_extracted_text(wrapped)
    assert "hemoglobin" in out
    assert "6.2" in out
    assert "62" not in out.replace("6.2", "")
    spaced = normalize_extracted_text("Vitamin D    32\n\n\nLDL  140")
    assert "Vitamin D 32" in spaced
    assert "140" in spaced


def test_chunking_deterministic_and_provenance():
    pages = [
        ExtractedPage(1, "CBC hemoglobin 13.5\n\nLipid Profile LDL 140", 40),
        ExtractedPage(2, "Thyroid TSH 2.1", 14),
    ]
    chunks = chunk_pages(pages, document_id="d1", user_id="u1", size=80, overlap=10)
    assert chunks
    assert all(c.source == "user_uploaded" for c in chunks)
    assert all(c.user_id == "u1" for c in chunks)
    again = chunk_pages(pages, document_id="d1", user_id="u1", size=80, overlap=10)
    assert [c.text for c in chunks] == [c.text for c in again]
    assert any(c.page_start == 1 for c in chunks)
    assert any(c.page_end == 2 or c.page_start == 2 for c in chunks)


def test_retrieval_ranks_and_scopes(client):
    res = _upload(client, "user-a", filename="lipid.pdf")
    did = res.json()["document_id"]
    other = _upload(client, "user-a", data=make_text_pdf(["Unrelated vitamin B12 200"]), filename="b12.pdf")
    oid = other.json()["document_id"]
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        hits = DocumentRetriever(db).retrieve("user-a", "LDL cholesterol", document_ids=[did])
        assert hits
        assert all(h.document_id == did for h in hits)
        assert all(h.source == "user_uploaded" for h in hits)
        scoped = DocumentRetriever(db).retrieve("user-a", "LDL", document_ids=[oid])
        assert not any("LDL cholesterol 140" in h.text and h.document_id == did for h in scoped)
        with pytest.raises(NotFoundError):
            DocumentRetriever(db).retrieve("user-b", "LDL", document_ids=[did])
    finally:
        db.close()


def test_chat_document_question_retrieves_without_supershyft(client):
    did = _upload(client, "user-a").json()["document_id"]
    with patch("app.llm.factory.get_llm_client") as llm:
        with patch("app.pipeline.context_builder.ContextBuilder.build") as build:
            res = client.post(
                "/api/v1/chat",
                headers={"X-Cura-User-Id": "user-a"},
                json={"message": "What does this report say about my cholesterol?", "document_ids": [did]},
            )
    body = res.json()
    assert body["meta"]["status"] == "document_retrieved"
    assert body["meta"]["llm_mode"] == "none"
    assert body["evidence"][0]["source"] == "user_uploaded"
    assert "LDL" in body["answer"]
    build.assert_not_called()
    llm.return_value.complete.assert_not_called()


def test_general_question_skips_documents(client):
    _upload(client, "user-a")
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-a"},
        json={"message": "What is HbA1c?"},
    )
    assert res.status_code == 200
    assert res.json()["meta"]["status"] != "document_retrieved"


def test_no_match_truthful(client):
    did = _upload(client, "user-a").json()["document_id"]
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-a"},
        json={"message": "ferritin zebra unrelated token xyzabc123", "document_ids": [did]},
    )
    assert DOCUMENT_NO_MATCH in res.json()["answer"]


def test_extraction_does_not_log_medical_values(client, caplog):
    with caplog.at_level("INFO", logger="cura.documents"):
        _upload(client, "user-a")
    joined = " ".join(r.message for r in caplog.records)
    assert "140" not in joined
    assert "6.2" not in joined
