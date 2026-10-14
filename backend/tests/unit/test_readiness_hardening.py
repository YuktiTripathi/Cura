"""Readiness plan 1.9 hardening and the answer cache (cost lever 5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import DocumentValidationError, RateLimitedError
from app.core.log_ids import subject_ref
from app.core.request_controls import RequestControlStore
from app.documents.validation import validate_pdf_upload
from app.llm import answer_cache
from app.llm.models import LLMStructuredOutput
from app.main import app


def _pdf(body: bytes) -> bytes:
    return b"%PDF-1.4\n" + body + b"\n%%EOF\n"


@pytest.mark.parametrize(
    "body",
    [
        b"1 0 obj << /Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >> endobj",
        b"1 0 obj << /S /Launch /F (cmd.exe) >> endobj",
        b"1 0 obj << /Type /EmbeddedFile >> endobj",
        b"1 0 obj << /S /J#61vaScript >> endobj",
    ],
)
def test_pdfs_with_active_content_are_refused(body):
    with pytest.raises(DocumentValidationError, match="active content"):
        validate_pdf_upload(filename="r.pdf", content_type="application/pdf", data=_pdf(body))


def test_pdf_over_the_page_cap_is_refused(monkeypatch):
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    monkeypatch.setattr(settings, "document_max_pages", 3)
    with pytest.raises(DocumentValidationError, match="4 pages"):
        validate_pdf_upload(filename="r.pdf", content_type="application/pdf", data=buf.getvalue())


def test_malware_scanner_unreachable_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "document_clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "document_clamav_port", 1)
    with pytest.raises(DocumentValidationError, match="couldn't check"):
        validate_pdf_upload(filename="r.pdf", content_type="application/pdf", data=_pdf(b"1 0 obj << >> endobj"))


def test_upload_and_voice_limits(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "upload_rate_limit", 2)
    monkeypatch.setattr(settings, "voice_rate_limit", 1)
    store = RequestControlStore()
    store.check_upload_limit("m1")
    store.check_upload_limit("m1")
    with pytest.raises(RateLimitedError, match="uploaded"):
        store.check_upload_limit("m1")
    store.check_voice_limit("m1")
    with pytest.raises(RateLimitedError, match="voice"):
        store.check_voice_limit("m1")
    store.check_upload_limit("m2")  # limits are per member


def test_per_ip_limit_returns_429(monkeypatch):
    from app.core import request_controls as rc

    monkeypatch.setattr(settings, "ip_rate_limit", 2)
    monkeypatch.setattr(rc, "request_controls", RequestControlStore())
    import app.main as main

    monkeypatch.setattr(main, "request_controls", rc.request_controls)
    client = TestClient(app)
    codes = [client.get("/api/v1/consent", headers={"X-Cura-User-Id": "ip-user"}).status_code for _ in range(3)]
    assert codes[-1] == 429 and codes[0] != 429
    assert client.get("/health/live").status_code == 200  # probes are not limited


def test_personal_health_answers_skip_the_shared_cache(monkeypatch):
    monkeypatch.setattr(settings, "answer_cache_ttl_seconds", 60)
    monkeypatch.setattr(settings, "answer_cache_enabled", True)
    monkeypatch.setattr(settings, "redis_url", "")
    from app.core import request_controls as rc
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(rc, "request_controls", RequestControlStore())
    messages = [{"role": "user", "content": "same prompt"}]
    answer_cache.answer_cache_put(messages, "m", LLMStructuredOutput(answer="other user's answer"))

    def fresh(self, messages):
        return LLMStructuredOutput(answer="this user's answer")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "_complete_structured_uncached", fresh)
    client = OpenAICompatibleLLMClient(api_key="test", model="m", personal_health=True)
    assert client.complete_structured(messages).answer == "this user's answer"


def test_member_ids_are_hashed_in_logs():
    assert subject_ref("member-42") != "member-42" and len(subject_ref("member-42")) == 12


def test_answer_cache_round_trip_and_key_changes(monkeypatch):
    monkeypatch.setattr(settings, "answer_cache_ttl_seconds", 60)
    monkeypatch.setattr(settings, "redis_url", "")
    from app.core import request_controls as rc

    monkeypatch.setattr(rc, "request_controls", RequestControlStore())
    messages = [{"role": "user", "content": "HbA1c 6.1, question: what does it mean?"}]
    assert answer_cache.answer_cache_get(messages, "m") is None
    answer_cache.answer_cache_put(messages, "m", LLMStructuredOutput(answer="It is slightly high."))
    assert answer_cache.answer_cache_get(messages, "m").answer == "It is slightly high."
    changed = [{"role": "user", "content": "HbA1c 6.4, question: what does it mean?"}]
    assert answer_cache.answer_cache_get(changed, "m") is None  # new data, new key
    assert answer_cache.answer_cache_get(messages, "other-model") is None
    answer_cache.answer_cache_put(changed, "m", LLMStructuredOutput(answer="cut", truncated=True))
    assert answer_cache.answer_cache_get(changed, "m") is None  # truncated answers are not cached


def test_identical_question_reuses_the_cached_model_answer(monkeypatch):
    from app.core import request_controls as rc
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "answer_cache_ttl_seconds", 60)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(rc, "request_controls", RequestControlStore())
    calls = []

    def complete(self, messages, json_mode=False):
        calls.append(1)
        return (
            '{"answer":"LDL stands for low-density lipoprotein.","claims":[],"recommendation_candidates":[],'
            '"follow_up_questions":[],"safety_flags":[],"escalation":null}'
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", complete)
    client = TestClient(app)
    for _ in range(2):
        body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": "cache-e2e"}, json={"message": "What does LDL stand for?"}).json()
        assert "low-density lipoprotein" in body["answer"].lower()
    assert len(calls) == 1


def test_compact_prompt_json_is_lossless_and_keeps_measured_section():
    import json as _json

    from app.pipeline.prompt_builder import _prune, compact_json

    value = {"a": 1, "b": None, "c": [], "d": {"e": "", "f": 0, "g": [None, 2]}, "h": False}
    assert _json.loads(compact_json(value)) == {"a": 1, "d": {"f": 0, "g": [2]}, "h": False}
    assert _prune([None, "", {}]) == []
