from typing import Protocol

from app.db.models import Conversation


class ConversationMemory(Protocol):
    def resolve_topic(self, conversation: Conversation | None, message: str) -> tuple[str | None, str | None]:
        ...
