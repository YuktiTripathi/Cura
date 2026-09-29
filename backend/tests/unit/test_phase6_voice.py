import inspect
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.core.errors import VoiceUnavailableError, VoiceValidationError
from app.main import app
from app.pipeline.query_planner import build_query_plan
from app.voice.contracts import TranscriptResult
from app.voice.medical_stt import normalize_spoken_medical_terms
from app.voice.providers import UnconfiguredSTTProvider, get_stt_provider, set_stt_provider
from app.voice.service import VoiceService

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_stt():
    yield
    set_stt_provider(None)


class FakeSTT:
    name = "mock"

    def __init__(self, text="Mera vitamin D kitna hai?", language="hi", confidence=0.9, fail=None, empty=False):
        self.text = text
        self.language = language
        self.confidence = confidence
        self.fail = fail
        self.empty = empty
        self.hints: list[str | None] = []

    def transcribe(self, audio, filename, content_type, language_hint=None):
        self.hints.append(language_hint)
        if self.fail:
            raise self.fail
        if self.empty:
            return TranscriptResult(transcript="  ", provider=self.name)
        return TranscriptResult(
            transcript=self.text,
            detected_language=self.language,
            confidence=self.confidence,
            provider=self.name,
        )


def _wav_bytes() -> bytes:
    return b"RIFF" + b"\x00" * 12 + b"WAVEfmt "


def test_unconfigured_provider():
    set_stt_provider(None)
    try:
        UnconfiguredSTTProvider().transcribe(_wav_bytes(), "a.wav", "audio/wav")
        assert False
    except VoiceUnavailableError as exc:
        assert "typing" in exc.message.lower()


def test_missing_provider_api():
    set_stt_provider(None)
    res = client.post(
        "/api/v1/voice/transcribe",
        headers={"X-Cura-User-Id": "demo-user-001"},
        files={"audio": ("a.wav", BytesIO(_wav_bytes()), "audio/wav")},
    )
    assert res.status_code == 503
    body = res.json()
    assert body["error"]["code"] == "VOICE_UNAVAILABLE"
    assert "api_key" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "asyncpg" not in str(body).lower()


def test_provider_failure():
    set_stt_provider(FakeSTT(fail=VoiceUnavailableError("Voice transcription timed out. Please try again or type your message.")))
    try:
        res = client.post(
            "/api/v1/voice/transcribe",
            headers={"X-Cura-User-Id": "demo-user-001"},
            files={"audio": ("a.wav", BytesIO(_wav_bytes()), "audio/wav")},
        )
        assert res.status_code == 503
        assert "timed out" in res.json()["error"]["message"].lower()
    finally:
        set_stt_provider(None)


def test_language_hints():
    fake = FakeSTT()
    set_stt_provider(fake)
    svc = VoiceService()
    try:
        for lang in ("en", "hi", "mr", "pa", "gu", "bn"):
            fake.hints.clear()
            svc.transcribe(_wav_bytes(), "a.wav", "audio/wav", lang, "manual")
            assert fake.hints[-1] == lang
        fake.hints.clear()
        svc.transcribe(_wav_bytes(), "a.wav", "audio/wav", "auto", "auto")
        assert fake.hints[-1] is None
    finally:
        set_stt_provider(None)


def test_valid_transcript():
    set_stt_provider(FakeSTT())
    try:
        res = client.post(
            "/api/v1/voice/transcribe",
            headers={"X-Cura-User-Id": "demo-user-001"},
            files={"audio": ("a.wav", BytesIO(_wav_bytes()), "audio/wav")},
            data={"language_mode": "auto"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "vitamin D" in body["transcript"] or "Vitamin D" in body["transcript"]
        assert body["detected_language"] in {"hi", "en"}
        assert "follow_ups" not in body
        assert "answer" not in body
    finally:
        set_stt_provider(None)


def test_empty_transcript_rejected():
    set_stt_provider(FakeSTT(empty=True))
    try:
        res = client.post(
            "/api/v1/voice/transcribe",
            headers={"X-Cura-User-Id": "demo-user-001"},
            files={"audio": ("a.wav", BytesIO(_wav_bytes()), "audio/wav")},
        )
        assert res.status_code == 400
    finally:
        set_stt_provider(None)


def test_malformed_provider_payload():
    class Bad:
        name = "bad"

        def transcribe(self, *a, **k):
            return TranscriptResult(transcript="", provider="bad")

    set_stt_provider(Bad())
    try:
        try:
            VoiceService().transcribe(_wav_bytes(), "a.wav", "audio/wav", None, "auto")
            assert False
        except VoiceValidationError:
            pass
    finally:
        set_stt_provider(None)


def test_medical_term_normalization():
    assert "HbA1c" in normalize_spoken_medical_terms("H B A one C is high")
    assert "LDL" in normalize_spoken_medical_terms("my L D L")
    assert "HDL" in normalize_spoken_medical_terms("H D L")
    assert "TSH" in normalize_spoken_medical_terms("T S H")
    assert "Vitamin D" in normalize_spoken_medical_terms("vitamin dee")
    assert "B12" in normalize_spoken_medical_terms("b twelve")
    assert "12.6" in normalize_spoken_medical_terms("Vitamin D is 12.6")


def test_voice_goes_to_existing_chat_plan_not_new_engine():
    plan = build_query_plan("Mera vitamin D kitna hai?")
    assert plan.needs_personal_data
    source = inspect.getsource(VoiceService.transcribe)
    assert "ChatService" not in source
    assert "build_query_plan" not in source


def test_no_audio_to_supershyft_and_temp_cleanup():
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "app" / "voice"
    blob = ""
    for p in src.glob("*.py"):
        blob += p.read_text()
    assert "insert into" not in blob.lower()
    assert "SUPERSHYFT" not in blob
    assert "unlink" in blob
    assert "user_id = 5" not in blob


def test_voice_requires_auth():
    res = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("a.wav", BytesIO(_wav_bytes()), "audio/wav")},
    )
    assert res.status_code == 401


def test_openrouter_stt_uses_json_audio(monkeypatch):
    from app.core import config as cfg
    from app.voice.providers import OpenAICompatibleSTTProvider

    monkeypatch.setattr(cfg.settings, "voice_enabled", True)
    monkeypatch.setattr(cfg.settings, "stt_provider", "openrouter")
    monkeypatch.setattr(cfg.settings, "stt_model", "openai/whisper-1")
    monkeypatch.setattr(cfg.settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(cfg.settings, "openrouter_api_key", "test-key")

    captured = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None, data=None, files=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["files"] = files

            class Res:
                status_code = 200

                def json(self):
                    return {"text": "mera cholesterol kitna hai", "language": "hi"}

            return Res()

    monkeypatch.setattr("app.voice.providers.httpx.Client", FakeClient)
    result = OpenAICompatibleSTTProvider().transcribe(b"abc", "recording.webm", "audio/webm")
    assert result.transcript == "mera cholesterol kitna hai"
    assert captured["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert captured["files"] is None
    assert captured["json"]["model"] == "openai/whisper-1"
    assert captured["json"]["input_audio"]["format"] == "webm"
    assert "Authorization" in captured["headers"]


def test_too_large_rejected(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "stt_max_audio_bytes", 8)
    try:
        res = client.post(
            "/api/v1/voice/transcribe",
            headers={"X-Cura-User-Id": "demo-user-001"},
            files={"audio": ("a.wav", BytesIO(b"0123456789"), "audio/wav")},
        )
        assert res.status_code == 400
    finally:
        monkeypatch.setattr(cfg.settings, "stt_max_audio_bytes", 10_000_000)
