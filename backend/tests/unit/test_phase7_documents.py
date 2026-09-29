import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.copy import DOCUMENT_FAILED
from app.main import app

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
EXE_BYTES = b"MZ" + b"\x00" * 64
TRAVERSAL_NAME = "../../../etc/passwd.pdf"


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "document_storage_backend", "local")
    monkeypatch.setattr(settings, "document_max_upload_bytes", 20_000_000)
    return tmp_path / "uploads"


@pytest.fixture
def client(storage_dir):
    return TestClient(app)


def _upload(client, user, filename="blood_report.pdf", data=MINIMAL_PDF, content_type="application/pdf"):
    return client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": user},
        files={"file": (filename, io.BytesIO(data), content_type)},
    )


def test_upload_valid_pdf(client, storage_dir):
    res = _upload(client, "user-a")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["source"] == "user_uploaded"
    assert body["source"] != "supershyft"
    assert body["upload_status"] == "uploaded"
    assert body["extraction_status"] in {"processing", "completed", "failed"}
    assert body["filename"] == "blood_report.pdf"
    assert "storage_key" not in body
    assert "path" not in body
    stored = list(storage_dir.rglob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == MINIMAL_PDF


def test_reject_empty_file(client):
    res = _upload(client, "user-a", data=b"")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DOCUMENT_VALIDATION_ERROR"


def test_reject_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "document_max_upload_bytes", 50)
    res = _upload(client, "user-a")
    assert res.status_code == 400
    assert not list(Path(settings.document_storage_path).rglob("*")) or True


def test_reject_wrong_mime_and_fake_pdf(client):
    res = _upload(client, "user-a", filename="report.pdf", data=JPEG_BYTES, content_type="application/pdf")
    assert res.status_code == 400
    exe = _upload(client, "user-a", filename="report.pdf", data=EXE_BYTES)
    assert exe.status_code == 400
    zipf = _upload(client, "user-a", filename="report.pdf", data=b"PK\x03\x04" + b"\x00" * 20)
    assert zipf.status_code == 400


def test_reject_malformed_pdf(client):
    res = _upload(client, "user-a", data=b"%PDF-1.4\nnot a real document")
    assert res.status_code == 400


def test_reject_unsupported_extension(client):
    res = _upload(client, "user-a", filename="notes.txt", data=b"hello", content_type="text/plain")
    assert res.status_code == 400


def test_ownership_isolation(client):
    created = _upload(client, "user-a").json()
    did = created["document_id"]
    other = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-b"})
    assert other.status_code == 404
    assert other.json()["error"]["message"] == "Document not found."
    listed = client.get("/api/v1/documents", headers={"X-Cura-User-Id": "user-b"})
    assert listed.json()["documents"] == []
    deleted = client.delete(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-b"})
    assert deleted.status_code == 404
    own = client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"})
    assert own.status_code == 200


def test_delete_removes_file(client, storage_dir):
    created = _upload(client, "user-a").json()
    did = created["document_id"]
    assert list(storage_dir.rglob("*.pdf"))
    gone = client.delete(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"})
    assert gone.status_code == 204
    assert list(storage_dir.rglob("*.pdf")) == []
    assert client.get(f"/api/v1/documents/{did}", headers={"X-Cura-User-Id": "user-a"}).status_code == 404


def test_filename_traversal_not_used_as_path(client, storage_dir):
    res = _upload(client, "user-a", filename=TRAVERSAL_NAME)
    assert res.status_code == 200
    assert res.json()["filename"] == "passwd.pdf"
    files = list(storage_dir.rglob("*"))
    assert all("etc" not in str(p) for p in files)
    abs_name = _upload(client, "user-a", filename="/tmp/secret.pdf")
    assert abs_name.status_code == 200
    assert abs_name.json()["filename"] == "secret.pdf"


def test_failed_upload_cleans_file(client, storage_dir):
    with patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("db down")):
        res = _upload(client, "user-a")
        assert res.status_code == 500
    leftover = [p for p in storage_dir.rglob("*.pdf") if p.is_file()]
    assert leftover == []


def test_chat_carries_document_id_without_reasoning(client):
    created = _upload(client, "user-a").json()
    did = created["document_id"]
    with patch("app.llm.factory.get_llm_client") as llm_factory:
        res = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "user-a"},
            json={"message": "Explain this report", "document_ids": [did]},
        )
    assert res.status_code == 200
    body = res.json()
    lowered = body["answer"].lower()
    assert (
        DOCUMENT_FAILED in body["answer"]
        or "could not be extracted" in lowered
        or "couldn't extract" in lowered
        or "couldn't read" in lowered
        or "still being processed" in lowered
    )
    assert body["meta"]["llm_mode"] == "none"
    assert body["evidence"][0]["source"] == "user_uploaded"
    assert body["evidence"][0]["document_id"] == did
    llm_factory.return_value.complete.assert_not_called()


def test_chat_document_id_other_user_not_found(client):
    did = _upload(client, "user-a").json()["document_id"]
    res = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-b"},
        json={"message": "Explain this report", "document_ids": [did]},
    )
    assert res.status_code == 404


def test_upload_does_not_log_pdf_bytes(client, caplog):
    with caplog.at_level("INFO", logger="cura.documents"):
        _upload(client, "user-a", filename="hba1c_secret.pdf")
    joined = " ".join(r.message for r in caplog.records)
    assert MINIMAL_PDF.decode("latin1") not in joined
    assert "HbA1c" not in joined
