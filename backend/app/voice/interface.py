from __future__ import annotations

from typing import Protocol

from app.voice.contracts import TranscriptResult


class SpeechToTextProvider(Protocol):
    name: str

    def transcribe(
        self,
        audio: bytes,
        filename: str,
        content_type: str,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        ...
