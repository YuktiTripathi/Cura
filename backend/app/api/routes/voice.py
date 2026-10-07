from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.core.request_controls import request_controls
from app.voice.contracts import TranscribeResponse
from app.voice.service import VoiceService

router = APIRouter()
compat_router = APIRouter()


async def run_transcribe(
    principal: AuthenticatedPrincipal,
    audio: UploadFile,
    language: str | None,
    language_mode: str,
) -> TranscribeResponse:
    request_controls.check_rate_limit(principal.subject_id)
    request_controls.check_voice_limit(principal.subject_id)
    data = await audio.read()
    result = VoiceService().transcribe(
        audio=data,
        filename=audio.filename or "recording.webm",
        content_type=audio.content_type or "audio/webm",
        language_hint=language,
        language_mode=language_mode,
    )
    return TranscribeResponse(
        transcript=result.transcript,
        text=result.transcript,
        language=result.detected_language,
        detected_language=result.detected_language,
        confidence=result.confidence,
        language_mode=result.language_mode,
    )


@router.post("/voice/transcribe", response_model=TranscribeResponse)
@router.post("/voice", response_model=TranscribeResponse, include_in_schema=True)
async def transcribe(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    language_mode: str = Form(default="auto"),
) -> TranscribeResponse:
    return await run_transcribe(principal, audio, language, language_mode)


@compat_router.post("/cura/transcribe", response_model=TranscribeResponse)
async def transcribe_compat(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    language_mode: str = Form(default="auto"),
) -> TranscribeResponse:
    return await run_transcribe(principal, audio, language, language_mode)
