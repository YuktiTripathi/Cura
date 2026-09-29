from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.core.config import settings
from app.core.errors import VoiceValidationError
from app.pipeline.language import get_language_detector
from app.voice.contracts import TranscriptResult
from app.voice.medical_stt import normalize_spoken_medical_terms
from app.voice.providers import get_stt_provider

logger = logging.getLogger("cura.voice")

ALLOWED_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "audio/flac",
    "video/webm",
}
ALLOWED_SUFFIX = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac"}


class VoiceService:
    def transcribe(
        self,
        audio: bytes,
        filename: str,
        content_type: str,
        language_hint: str | None,
        language_mode: str,
    ) -> TranscriptResult:
        self._validate(audio, filename, content_type)
        hint = None if (language_mode or "auto").lower() == "auto" else (language_hint or None)
        if hint in {"auto", ""}:
            hint = None
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=Path(filename or "audio.webm").suffix or ".webm", delete=False) as tmp:
                tmp.write(audio)
                tmp_path = Path(tmp.name)
            provider = get_stt_provider()
            result = provider.transcribe(audio, filename or tmp_path.name, content_type, hint)
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("stt_temp_cleanup_failed")

        text = normalize_spoken_medical_terms((result.transcript or "").strip())
        if not text:
            raise VoiceValidationError("I couldn't hear a question. Please try speaking again or type your message.")
        detected = result.detected_language
        if not detected:
            cura_lang = get_language_detector().detect(text)
            detected = cura_lang.language.value if cura_lang.confidence >= 0.4 else None
        return TranscriptResult(
            transcript=text,
            detected_language=detected,
            confidence=result.confidence,
            language_mode=language_mode or "auto",
            provider=result.provider,
        )

    def _validate(self, audio: bytes, filename: str, content_type: str) -> None:
        if not audio:
            raise VoiceValidationError("No audio was received.")
        max_bytes = settings.stt_max_audio_bytes
        if len(audio) > max_bytes:
            raise VoiceValidationError("That recording is too large. Please try a shorter message.")
        mime = (content_type or "").split(";")[0].strip().lower()
        suffix = Path(filename or "").suffix.lower()
        if mime and mime not in ALLOWED_TYPES and suffix not in ALLOWED_SUFFIX:
            if mime.startswith("audio/") or mime.startswith("video/"):
                return
            raise VoiceValidationError("That audio format isn't supported. Try recording again from the browser.")
        if not mime and suffix and suffix not in ALLOWED_SUFFIX:
            raise VoiceValidationError("That audio format isn't supported. Try recording again from the browser.")
