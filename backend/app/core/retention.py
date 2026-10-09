"""Retention and deletion (production readiness plan, 1.7).

Deleting a conversation or document also removes its derived rows (extracted facts,
evaluation interactions, feedback, chunks, jobs) and leaves an audit record with a hashed
member id. ``purge_expired`` runs on a schedule (scripts/purge_expired.py).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    AuditRecord,
    Conversation,
    Document,
    Feedback,
    HealthFactRef,
    Interaction,
    ProcessingJob,
)

logger = logging.getLogger("cura.retention")


def _hash(subject_id: str) -> str:
    return hashlib.sha256((subject_id or "").encode("utf-8")).hexdigest()


def _audit(db: Session, subject_id: str, *, intent: str, conversation_id: str | None = None) -> None:
    db.add(
        AuditRecord(
            id=str(uuid.uuid4()),
            request_id=f"retention-{uuid.uuid4().hex[:12]}",
            subject_id_hash=_hash(subject_id),
            conversation_id=conversation_id,
            intent=intent,
            provider="cura",
        )
    )


def delete_document_derived(db: Session, document_id: str, subject_id: str, *, reason: str = "member_request") -> None:
    """Remove rows derived from a document. Chunks go with the document via cascade."""
    db.execute(delete(HealthFactRef).where(HealthFactRef.document_id == document_id))
    db.execute(delete(ProcessingJob).where(ProcessingJob.document_id == document_id))
    _audit(db, subject_id, intent=f"document_deleted:{reason}")


def delete_conversation_derived(db: Session, conversation_id: str, subject_id: str, *, reason: str = "member_request") -> None:
    """Remove rows derived from a conversation. Messages go with it via cascade."""
    db.execute(delete(HealthFactRef).where(HealthFactRef.conversation_id == conversation_id))
    db.execute(delete(Interaction).where(Interaction.conversation_id == conversation_id))
    db.execute(delete(Feedback).where(Feedback.conversation_id == conversation_id))
    _audit(db, subject_id, intent=f"conversation_deleted:{reason}", conversation_id=conversation_id)


def purge_expired(db: Session, *, now: datetime | None = None, store=None) -> dict[str, int]:
    """Delete data covered by explicitly configured retention windows."""
    current = now or datetime.now(timezone.utc)
    counts = {"documents": 0, "conversations": 0, "processing_jobs": 0, "audit_records": 0}

    doc_days = int(settings.document_retention_days or 0)
    if doc_days > 0:
        if store is None:
            from app.documents.storage import get_document_store

            store = get_document_store()
        cutoff = current - timedelta(days=doc_days)
        for doc in db.execute(select(Document).where(Document.created_at < cutoff)).scalars().all():
            key = doc.storage_key
            delete_document_derived(db, doc.id, doc.user_id, reason="retention_expired")
            db.delete(doc)
            try:
                store.delete(key)
            except Exception:  # noqa: BLE001 - row is gone; file cleanup is retried by ops
                logger.warning("retention_file_delete_failed document_id=%s", doc.id)
            counts["documents"] += 1

    conv_days = int(settings.conversation_retention_days or 0)
    if conv_days > 0:
        cutoff = current - timedelta(days=conv_days)
        for conv in db.execute(select(Conversation).where(Conversation.updated_at < cutoff)).scalars().all():
            delete_conversation_derived(db, conv.id, conv.subject_id, reason="retention_expired")
            db.delete(conv)
            counts["conversations"] += 1

    job_days = int(settings.processing_job_retention_days or 0)
    if job_days > 0:
        cutoff = current - timedelta(days=job_days)
        result = db.execute(
            delete(ProcessingJob).where(
                ProcessingJob.status.in_(("completed", "failed")),
                ProcessingJob.created_at < cutoff,
            ).execution_options(synchronize_session=False)
        )
        counts["processing_jobs"] = int(result.rowcount or 0)

    audit_days = int(settings.audit_record_retention_days or 0)
    if audit_days > 0:
        cutoff = current - timedelta(days=audit_days)
        result = db.execute(
            delete(AuditRecord)
            .where(AuditRecord.created_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        counts["audit_records"] = int(result.rowcount or 0)

    db.commit()
    logger.info(
        "retention_purge documents=%s conversations=%s processing_jobs=%s audit_records=%s",
        counts["documents"],
        counts["conversations"],
        counts["processing_jobs"],
        counts["audit_records"],
    )
    return counts
