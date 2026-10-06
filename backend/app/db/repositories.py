from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import AuditRecord, Conversation, Feedback, HealthFactRef, Interaction, Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_subject(self, subject_id: str) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.subject_id == subject_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get_for_subject(self, conversation_id: str, subject_id: str) -> Conversation:
        conv = self.db.get(Conversation, conversation_id)
        if conv is None or conv.subject_id != subject_id:
            raise NotFoundError("Conversation not found")
        return conv

    def create(self, subject_id: str, title: str | None = None) -> Conversation:
        conv = Conversation(id=str(uuid4()), subject_id=subject_id, title=title)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        intent: str | None = None,
    ) -> Message:
        msg = Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role=role,
            content=content,
            intent=intent,
        )
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def update_language_preference(self, conversation: Conversation, language: str | None) -> None:
        conversation.language_preference = language
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_follow_up(self, conversation: Conversation, topic: str | None, name: str | None) -> None:
        conversation.follow_up_topic = topic
        conversation.follow_up_topic_name = name
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_source_mode(
        self, conversation: Conversation, mode: str | None, document_id: str | None = None
    ) -> None:
        conversation.last_source_mode = mode
        if document_id is not None:
            conversation.last_document_id = document_id
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_context_state(
        self,
        conversation: Conversation,
        *,
        marker_code: str | None = None,
        report_id: str | None = None,
        summary: str | None = None,
    ) -> None:
        if marker_code is not None:
            conversation.current_marker_code = marker_code
        if report_id is not None:
            conversation.current_report_id = report_id
        if summary is not None:
            conversation.conversation_summary = summary[:2000]
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def update_conversation_state(self, conversation: Conversation, payload: str | None) -> None:
        conversation.conversation_state_json = payload
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def delete_for_subject(self, conversation_id: str, subject_id: str) -> None:
        from app.core.retention import delete_conversation_derived

        conv = self.get_for_subject(conversation_id, subject_id)
        delete_conversation_derived(self.db, conversation_id, subject_id)
        self.db.delete(conv)
        self.db.commit()

    def rewind_for_subject(self, conversation_id: str, subject_id: str, keep: int) -> Conversation:
        conv = self.get_for_subject(conversation_id, subject_id)
        rows = sorted(conv.messages or [], key=lambda item: (item.created_at or item.id, item.id))
        kept = max(0, int(keep))
        for row in rows[kept:]:
            self.db.delete(row)
        conv.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def add_feedback(
        self,
        subject_id: str,
        conversation_id: str,
        rating: str,
        message_id: str | None,
        comment: str | None,
    ) -> Feedback:
        self.get_for_subject(conversation_id, subject_id)
        helpful = None
        lowered = (rating or "").strip().lower()
        if lowered in {"up", "helpful", "true", "1", "yes"}:
            helpful = True
        elif lowered in {"down", "not_helpful", "false", "0", "no"}:
            helpful = False
        interaction_id = None
        latest = self.latest_interaction_for_conversation(conversation_id, subject_id)
        if latest is not None:
            interaction_id = latest.id
        row = Feedback(
            id=str(uuid4()),
            conversation_id=conversation_id,
            message_id=message_id,
            subject_id=subject_id,
            rating=rating,
            comment=comment,
            helpful=helpful,
            interaction_id=interaction_id,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def latest_interaction_for_conversation(self, conversation_id: str, subject_id: str) -> Interaction | None:
        stmt = (
            select(Interaction)
            .where(Interaction.conversation_id == conversation_id, Interaction.subject_id == subject_id)
            .order_by(Interaction.created_at.desc())
        )
        return self.db.scalars(stmt).first()

    def latest_assistant_message(self, conversation_id: str) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
        )
        return self.db.scalars(stmt).first()

    def add_interaction(self, **kwargs) -> Interaction:
        row = Interaction(id=str(uuid4()), **kwargs)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def add_health_fact_refs(self, refs: list[dict]) -> None:
        if not refs:
            return
        for item in refs:
            self.db.add(HealthFactRef(id=str(uuid4()), **item))
        self.db.commit()

    def list_interactions_for_subject(self, subject_id: str, conversation_id: str | None = None) -> list[Interaction]:
        stmt = select(Interaction).where(Interaction.subject_id == subject_id)
        if conversation_id:
            stmt = stmt.where(Interaction.conversation_id == conversation_id)
        stmt = stmt.order_by(Interaction.created_at.desc())
        return list(self.db.scalars(stmt))

    def list_feedback_for_subject(self, subject_id: str, conversation_id: str | None = None) -> list[Feedback]:
        stmt = select(Feedback).where(Feedback.subject_id == subject_id)
        if conversation_id:
            stmt = stmt.where(Feedback.conversation_id == conversation_id)
        return list(self.db.scalars(stmt))

    def add_audit(self, **kwargs) -> None:
        self.db.add(AuditRecord(id=str(uuid4()), **kwargs))
        self.db.commit()
