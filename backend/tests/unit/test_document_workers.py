"""Document extraction workers (readiness plan 5.2): atomic claims, lease recovery, exhaustion."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.db.models import Document, ProcessingJob
from app.db.session import SessionLocal, init_db
from app.documents import jobs


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    session.query(ProcessingJob).filter(ProcessingJob.status.in_(("pending", "processing"))).update(
        {"status": "completed"}, synchronize_session=False
    )
    session.commit()
    yield session
    session.close()


def _job(db, **kw) -> ProcessingJob:
    doc = Document(
        id=str(uuid.uuid4()), user_id="w-user", original_filename="r.pdf", content_type="application/pdf",
        file_size=1, storage_key="k", extraction_status="queued",
    )
    db.add(doc)
    job = ProcessingJob(id=str(uuid.uuid4()), document_id=doc.id, user_id="w-user", status="pending", attempts=0, **kw)
    db.add(job)
    db.commit()
    return job


def test_two_workers_never_claim_the_same_job(db):
    job = _job(db)
    first, second = SessionLocal(), SessionLocal()
    try:
        a = jobs.claim_next_job(first)
        b = jobs.claim_next_job(second)
        assert a is not None and a.id == job.id
        assert b is None
    finally:
        first.close()
        second.close()


def test_stale_processing_job_is_reclaimed_after_the_lease(db, monkeypatch):
    monkeypatch.setattr(settings, "document_job_lease_seconds", 60)
    now = datetime.now(timezone.utc)
    job = _job(db)
    claimed = jobs.claim_next_job(db, now=now)
    assert claimed.id == job.id
    assert jobs.claim_next_job(db, now=now + timedelta(seconds=30)) is None
    again = jobs.claim_next_job(db, now=now + timedelta(seconds=120))
    assert again is not None and again.id == job.id and again.attempts == 2


def test_job_failing_every_attempt_is_marked_failed(db, monkeypatch):
    monkeypatch.setattr(settings, "document_job_lease_seconds", 60)
    monkeypatch.setattr(settings, "document_job_max_attempts", 2)
    now = datetime.now(timezone.utc)
    job = _job(db)
    jobs.claim_next_job(db, now=now)
    jobs.claim_next_job(db, now=now + timedelta(seconds=120))
    assert jobs.claim_next_job(db, now=now + timedelta(seconds=300)) is None
    db.expire_all()
    row = db.get(ProcessingJob, job.id)
    assert row.status == "failed" and row.last_error == "worker_attempts_exhausted"
    assert db.get(Document, job.document_id).extraction_status == "failed"


def test_worker_runs_the_claimed_job(db, monkeypatch):
    job = _job(db)
    ran = []
    monkeypatch.setattr(jobs, "process_document_job", lambda doc_id, user: ran.append(doc_id))
    assert jobs.run_worker_once() is True
    assert ran == [job.document_id]
    db.expire_all()
    assert db.get(ProcessingJob, job.id).status == "completed"
    assert jobs.run_worker_once() is False


def test_external_mode_upload_only_enqueues(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "document_worker_mode", "external")
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path))
    called = []
    monkeypatch.setattr("app.api.routes.documents.run_document_job", lambda *a: called.append(a))
    from tests.unit.test_multi_source_context import LDL_PDF

    res = TestClient(app).post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": "w-user-2"},
        files={"file": ("lab.pdf", LDL_PDF, "application/pdf")},
    )
    assert res.status_code in (200, 201) and called == []
