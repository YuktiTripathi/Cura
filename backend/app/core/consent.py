"""Consent notice and checks (production readiness plan, 1.4).

DRAFT notice text: it must be reviewed by counsel against India's Digital Personal Data
Protection Act before the pilot. Bump CONSENT_VERSION in settings whenever it changes;
members are then asked again.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import CuraError
from app.db.models import ConsentRecord

CONSENT_NOTICE = (
    "Cura uses your Supershyft health records, the reports you upload and your messages to answer your "
    "health questions. To do this, the relevant parts of your data are sent, without your name or contact "
    "details, to AI model providers through OpenRouter under zero data retention terms, so they are not "
    "stored or used for training. Cura gives general health information, not a diagnosis or prescription. "
    "Your conversations and uploaded documents are kept for a limited time and you can delete them at any "
    "time. You can withdraw this consent at any time from your settings; Cura will then stop processing "
    "your data for new questions."
)


def notice_sha256(text: str = CONSENT_NOTICE) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def latest_consent(db: Session, subject_id: str) -> ConsentRecord | None:
    stmt = (
        select(ConsentRecord)
        .where(ConsentRecord.subject_id == subject_id)
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def has_current_consent(db: Session, subject_id: str) -> bool:
    record = latest_consent(db, subject_id)
    return bool(record and record.accepted and record.version == settings.consent_version)


def record_consent(db: Session, subject_id: str, *, accepted: bool, version: str, language: str | None) -> ConsentRecord:
    if version != settings.consent_version:
        raise CuraError("CONSENT_VERSION_MISMATCH", "Please review the latest consent notice.", 409)
    record = ConsentRecord(
        id=str(uuid.uuid4()),
        subject_id=subject_id,
        version=version,
        accepted=accepted,
        notice_sha256=notice_sha256(),
        language=language,
    )
    db.add(record)
    db.commit()
    return record


def require_consent(db: Session, subject_id: str) -> None:
    if settings.consent_enforced() and not has_current_consent(db, subject_id):
        raise CuraError(
            "CONSENT_REQUIRED",
            "Please review and accept Cura's data notice before chatting.",
            403,
            {"consent_version": settings.consent_version},
        )
