from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import FeedbackRequest
from app.db.repositories import ConversationRepository
from app.db.session import get_db

router = APIRouter()


@router.post("/feedback")
def create_feedback(
    payload: FeedbackRequest,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    ConversationRepository(db).add_feedback(
        principal.subject_id,
        payload.conversation_id,
        payload.rating,
        payload.message_id,
        payload.comment,
    )
    return {"ok": True}
