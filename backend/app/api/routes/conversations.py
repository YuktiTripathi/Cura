from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.chat import ConversationDetail, ConversationSummary, MessageOut
from app.db.repositories import ConversationRepository
from app.db.session import get_db


class RewindRequest(BaseModel):
    keep: int = Field(ge=0)

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    rows = ConversationRepository(db).list_for_subject(principal.subject_id)
    return [
        ConversationSummary(id=r.id, title=r.title, updated_at=r.updated_at.isoformat() if r.updated_at else "")
        for r in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    conv = ConversationRepository(db).get_for_subject(conversation_id, principal.subject_id)
    messages = [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat() if m.created_at else "")
        for m in sorted(conv.messages, key=lambda x: x.created_at or x.id)
    ]
    return ConversationDetail(id=conv.id, title=conv.title, messages=messages)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    ConversationRepository(db).delete_for_subject(conversation_id, principal.subject_id)
    return {"ok": True}


@router.post("/conversations/{conversation_id}/rewind")
def rewind_conversation(
    conversation_id: str,
    payload: RewindRequest,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    ConversationRepository(db).rewind_for_subject(conversation_id, principal.subject_id, payload.keep)
    return {"ok": True}
