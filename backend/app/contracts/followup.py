from __future__ import annotations

from pydantic import BaseModel, Field


class FollowUpSuggestion(BaseModel):
    text: str
    category: str
    intent: str | None = None
    requires_personal_context: bool = False
    source: str | None = "supershyft"
    knowledge_scope: str = "personal"
