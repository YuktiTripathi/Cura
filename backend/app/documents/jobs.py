"""Durable document jobs. FastAPI BackgroundTasks may kick work; the row is the source of truth."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, ProcessingJob
from app.db.session import SessionLocal
from app.documents.processor import process_document_job

logger = logging.getLogger("cura.documents")


def enqueue_document_job(db: Session, document_id: str, user_id: str) -> str:
    job = ProcessingJob(
        id=str(uuid4()),
        kind="document_extract",
        document_id=document_id,
        user_id=user_id,
        status="pending",
        attempts=0,
    )
    db.add(job)
    db.commit()
    return job.id


def run_document_job(document_id: str, user_id: str) -> None:
    process_document_job(document_id, user_id)
    db = SessionLocal()
    try:
        rows = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.document_id == document_id,
                ProcessingJob.user_id == user_id,
                ProcessingJob.status.in_(("pending", "processing")),
            )
            .all()
        )
        for row in rows:
            row.status = "completed"
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("document_job_status_update_failed document_id=%s", document_id)
    finally:
        db.close()


def claim_next_job(db: Session, *, now: datetime | None = None) -> ProcessingJob | None:
    """Atomically claim one runnable job. Safe with several workers on Postgres or SQLite.

    A job is runnable when it is pending, or when it has been "processing" longer than the
    lease (its worker died). The conditional UPDATE means two workers can never both win.
    """
    current = now or datetime.now(timezone.utc)
    stale_before = current - timedelta(seconds=int(settings.document_job_lease_seconds))
    max_attempts = int(settings.document_job_max_attempts)
    candidates = (
        db.query(ProcessingJob.id, ProcessingJob.status, ProcessingJob.claimed_at)
        .filter(ProcessingJob.kind == "document_extract")
        .filter(
            or_(
                ProcessingJob.status == "pending",
                (ProcessingJob.status == "processing") & (ProcessingJob.claimed_at < stale_before),
            )
        )
        .filter(ProcessingJob.attempts < max_attempts)
        .order_by(ProcessingJob.created_at)
        .limit(10)
        .all()
    )
    for job_id, status, claimed_at in candidates:
        condition = (ProcessingJob.id == job_id) & (ProcessingJob.status == status)
        condition &= ProcessingJob.claimed_at.is_(None) if claimed_at is None else (ProcessingJob.claimed_at == claimed_at)
        won = db.execute(
            update(ProcessingJob)
            .where(condition)
            .values(status="processing", claimed_at=current, attempts=ProcessingJob.attempts + 1)
        ).rowcount
        db.commit()
        if won == 1:
            return db.get(ProcessingJob, job_id)
    _fail_exhausted(db, stale_before, max_attempts)
    return None


def _fail_exhausted(db: Session, stale_before: datetime, max_attempts: int) -> None:
    """Jobs that crashed their worker on every attempt are marked failed, with the document."""
    rows = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.kind == "document_extract", ProcessingJob.attempts >= max_attempts)
        .filter(
            or_(
                ProcessingJob.status == "pending",
                (ProcessingJob.status == "processing") & (ProcessingJob.claimed_at < stale_before),
            )
        )
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.last_error = "worker_attempts_exhausted"
        doc = db.get(Document, row.document_id) if row.document_id else None
        if doc and doc.extraction_status not in {"completed", "failed"}:
            doc.extraction_status = "failed"
            doc.extraction_error = "We couldn't read this document. Please try uploading it again."
    if rows:
        db.commit()


def run_worker_once() -> bool:
    """Claim and run one job. Returns False when there was nothing to do."""
    db = SessionLocal()
    try:
        job = claim_next_job(db)
        if job is None:
            return False
        document_id, user_id = job.document_id, job.user_id
    finally:
        db.close()
    try:
        run_document_job(document_id, user_id)
    except Exception:
        logger.warning("document_worker_job_failed document_id=%s", document_id)
    return True


def drain_pending_document_jobs(limit: int = 20) -> int:
    """Inline mode only: run pending jobs in the web process at startup."""
    ran = 0
    for _ in range(limit):
        if not run_worker_once():
            break
        ran += 1
    return ran
