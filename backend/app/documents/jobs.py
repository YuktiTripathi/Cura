"""Durable document jobs. FastAPI BackgroundTasks may kick work; the row is the source of truth."""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import ProcessingJob
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


def drain_pending_document_jobs(limit: int = 20) -> int:
    db = SessionLocal()
    ran = 0
    try:
        rows = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.status == "pending", ProcessingJob.kind == "document_extract")
            .limit(limit)
            .all()
        )
        jobs = [(row.document_id, row.user_id, row.id) for row in rows if row.document_id]
        for row in rows:
            row.status = "processing"
            row.attempts = (row.attempts or 0) + 1
        db.commit()
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()
    for document_id, user_id, _job_id in jobs:
        try:
            run_document_job(document_id, user_id)
            ran += 1
        except Exception:
            logger.warning("pending_document_job_failed document_id=%s", document_id)
    return ran
