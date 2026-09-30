from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptResult(BaseModel):
    transcript: str
    detected_language: str | None = None
    confidence: float | None = None
    language_mode: str = "auto"
    provider: str = "none"


class TranscribeResponse(BaseModel):
    transcript: str
    text: str | None = None
    language: str | None = None
    detected_language: str | None = None
    confidence: float | None = Field(default=None)
    language_mode: str = "auto"
