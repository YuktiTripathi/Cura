from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.consent import CONSENT_NOTICE, latest_consent, record_consent
from app.db.session import get_db

router = APIRouter()


class ConsentRequest(BaseModel):
    version: str
    accepted: bool
    language: str | None = None


def _status(db: Session, subject_id: str) -> dict:
    record = latest_consent(db, subject_id)
    current = bool(record and record.accepted and record.version == settings.consent_version)
    return {
        "version": settings.consent_version,
        "notice": CONSENT_NOTICE,
        "required": settings.consent_enforced(),
        "accepted": current,
        "accepted_version": record.version if record and record.accepted else None,
    }


@router.get("/consent")
def get_consent(
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _status(db, principal.subject_id)


@router.post("/consent")
def post_consent(
    payload: ConsentRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    record_consent(db, principal.subject_id, accepted=payload.accepted, version=payload.version, language=payload.language)
    return _status(db, principal.subject_id)
