from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.errors import VoiceUnavailableError
from app.voice.contracts import TranscriptResult
from app.voice.interface import SpeechToTextProvider
from app.voice.medical_stt import STT_PROMPT

logger = logging.getLogger("cura.voice")

WHISPER_LANG = {
    "en": "en",
    "hi": "hi",
    "mr": "mr",
    "pa": "pa",
    "gu": "gu",
    "bn": "bn",
}


class UnconfiguredSTTProvider:
    name = "none"

    def transcribe(self, audio: bytes, filename: str, content_type: str, language_hint: str | None = None) -> TranscriptResult:
        raise VoiceUnavailableError(
            "Voice input isn't configured yet. You can continue by typing your message."
        )


class OpenAICompatibleSTTProvider:
    """OpenAI-compatible /audio/transcriptions (local Whisper server, Groq, OpenAI, etc.)."""

    name = "openai_compatible"

    def transcribe(
        self,
        audio: bytes,
        filename: str,
        content_type: str,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        base = settings.resolved_stt_base_url()
        url = f"{base}/audio/transcriptions"
        headers = {}
        key = settings.resolved_stt_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if "openrouter.ai" in base:
            headers["HTTP-Referer"] = settings.openrouter_http_referer or "http://localhost:5173"
            headers["X-Title"] = settings.openrouter_app_title or "Cura"
        hint = WHISPER_LANG.get((language_hint or "").lower())
        try:
            with httpx.Client(timeout=settings.stt_timeout_seconds) as client:
                if "openrouter.ai" in base:
                    payload: dict[str, object] = {
                        "model": settings.resolved_stt_model(),
                        "prompt": STT_PROMPT,
                        "input_audio": {
                            "data": base64.b64encode(audio).decode("ascii"),
                            "format": _audio_format(filename, content_type),
                        },
                    }
                    if hint:
                        payload["language"] = hint
                    res = client.post(url, headers={**headers, "Content-Type": "application/json"}, json=payload)
                else:
                    data: dict[str, str] = {"model": settings.resolved_stt_model(), "prompt": STT_PROMPT}
                    if hint:
                        data["language"] = hint
                    files = {"file": (filename or "audio.webm", audio, content_type or "application/octet-stream")}
                    res = client.post(url, headers=headers, data=data, files=files)
        except httpx.TimeoutException as exc:
            logger.warning("stt_timeout provider=%s", self.name)
            raise VoiceUnavailableError("Voice transcription timed out. Please try again or type your message.") from exc
        except httpx.HTTPError as exc:
            logger.warning("stt_http_error provider=%s", self.name)
            raise VoiceUnavailableError(
                "Voice input isn't available right now. You can continue by typing your message."
            ) from exc
        if res.status_code >= 400:
            logger.warning("stt_status=%s", res.status_code)
            raise VoiceUnavailableError(
                "Voice input isn't available right now. You can continue by typing your message."
            )
        try:
            payload = res.json()
        except Exception as exc:
            raise VoiceUnavailableError("Voice transcription returned an unexpected response.") from exc
        if not isinstance(payload, dict):
            raise VoiceUnavailableError("Voice transcription returned an unexpected response.")
        text = str(payload.get("text") or payload.get("transcript") or "").strip()
        conf = payload.get("confidence")
        if conf is not None:
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = None
        lang = payload.get("language")
        return TranscriptResult(
            transcript=text,
            detected_language=str(lang) if lang else None,
            confidence=conf,
            language_mode="manual" if hint else "auto",
            provider=self.name,
        )


def _audio_format(filename: str, content_type: str) -> str:
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    mime = (content_type or "").split(";")[0].strip().lower()
    if suffix in {"webm", "wav", "mp3", "mp4", "m4a", "ogg", "flac", "aac"}:
        return "mp4" if suffix == "m4a" else suffix
    if "webm" in mime:
        return "webm"
    if "wav" in mime:
        return "wav"
    if "mpeg" in mime or mime.endswith("/mp3"):
        return "mp3"
    if "mp4" in mime or "m4a" in mime:
        return "mp4"
    if "ogg" in mime:
        return "ogg"
    if "flac" in mime:
        return "flac"
    return "webm"


class LocalSTTProvider(OpenAICompatibleSTTProvider):
    name = "local"


_override: SpeechToTextProvider | None = None


def set_stt_provider(provider: SpeechToTextProvider | None) -> None:
    global _override
    _override = provider


def get_stt_provider() -> SpeechToTextProvider:
    if _override is not None:
        return _override
    if not settings.voice_enabled:
        return UnconfiguredSTTProvider()
    name = (settings.stt_provider or "none").strip().lower()
    if name in {"none", "off", "disabled", ""}:
        return UnconfiguredSTTProvider()
    if name in {"local", "whisper", "self_hosted"}:
        return LocalSTTProvider()
    if name in {"openai_compatible", "openai", "api", "groq", "openrouter"}:
        return OpenAICompatibleSTTProvider()
    return UnconfiguredSTTProvider()


def voice_input_available() -> bool:
    """Whether a speech-to-text provider is configured, so clients can offer the microphone."""
    return not isinstance(get_stt_provider(), UnconfiguredSTTProvider)

