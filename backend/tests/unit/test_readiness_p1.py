"""Production readiness plan P1 items: retention, voice policy, output check, digits, budgets."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.errors import RateLimitedError, VoiceUnavailableError
from app.core.request_controls import RequestControlStore
from app.core.retention import purge_expired
from app.db.models import AuditRecord, Conversation, Document, Feedback, HealthFactRef, Interaction, Message, ProcessingJob
from app.db.repositories import ConversationRepository
from app.db.session import SessionLocal, init_db
from app.pipeline.grounding import to_ascii_digits
from app.pipeline.safety import SafetyLayer, unsafe_medication_spans


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _conversation(db, subject: str, *, updated_at: datetime | None = None) -> Conversation:
    conv = Conversation(id=str(uuid.uuid4()), subject_id=subject, title="t")
    db.add(conv)
    db.flush()
    db.add(Message(id=str(uuid.uuid4()), conversation_id=conv.id, role="user", content="hi"))
    db.add(HealthFactRef(id=str(uuid.uuid4()), subject_id=subject, conversation_id=conv.id, source="x", metric="hba1c"))
    db.add(Interaction(id=str(uuid.uuid4()), conversation_id=conv.id, subject_id=subject, user_query="q", assistant_response="a"))
    db.add(Feedback(id=str(uuid.uuid4()), conversation_id=conv.id, subject_id=subject, rating="up"))
    if updated_at:
        conv.updated_at = updated_at
    db.commit()
    return conv


def _count(db, model, **where) -> int:
    query = db.query(model)
    for key, value in where.items():
        query = query.filter(getattr(model, key) == value)
    return query.count()


def test_deleting_a_conversation_removes_derived_rows_and_audits(db):
    subject = f"ret-{uuid.uuid4().hex[:8]}"
    conv = _conversation(db, subject)
    ConversationRepository(db).delete_for_subject(conv.id, subject)
    for model in (HealthFactRef, Interaction, Feedback):
        assert _count(db, model, conversation_id=conv.id) == 0
    assert _count(db, AuditRecord, conversation_id=conv.id) == 1


def test_purge_removes_expired_documents_and_conversations(db, monkeypatch):
    monkeypatch.setattr(settings, "document_retention_days", 90)
    monkeypatch.setattr(settings, "conversation_retention_days", 365)
    subject = f"ret-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    old_conv = _conversation(db, subject, updated_at=now - timedelta(days=400))
    fresh_conv = _conversation(db, subject)
    doc = Document(
        id=str(uuid.uuid4()), user_id=subject, original_filename="r.pdf", content_type="application/pdf",
        file_size=1, storage_key="k", created_at=now - timedelta(days=120),
    )
    db.add(doc)
    db.add(ProcessingJob(id=str(uuid.uuid4()), document_id=doc.id, user_id=subject))
    db.commit()

    class Store:
        deleted: list[str] = []

        def delete(self, key):
            self.deleted.append(key)

    store = Store()
    counts = purge_expired(db, now=now, store=store)
    assert counts["documents"] >= 1 and counts["conversations"] >= 1
    assert db.get(Document, doc.id) is None and store.deleted == ["k"]
    assert _count(db, ProcessingJob, document_id=doc.id) == 0
    assert db.get(Conversation, old_conv.id) is None
    assert db.get(Conversation, fresh_conv.id) is not None


def test_voice_refuses_when_zdr_required_but_not_configured(monkeypatch):
    from app.voice.providers import OpenAICompatibleSTTProvider

    monkeypatch.setattr(settings, "stt_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", True)
    monkeypatch.setattr(settings, "openrouter_zero_data_retention", False)
    with pytest.raises(VoiceUnavailableError):
        OpenAICompatibleSTTProvider().transcribe(b"x", "a.webm", "audio/webm")


@pytest.mark.parametrize(
    "answer",
    ["Increase your metformin to 1000 mg.", "Take 500 mg twice daily.", "You should stop your thyroid tablet for a week."],
)
def test_output_check_removes_medication_instructions(answer):
    out, flags = SafetyLayer().review(answer)
    assert "medication_instruction" in flags
    assert "[medication advice removed]" in out


@pytest.mark.parametrize(
    "answer",
    ["Do not stop your medicine without your doctor.", "Metformin is commonly used for type 2 diabetes.", "Your HbA1c is 6.1%."],
)
def test_output_check_allows_education_and_negated_advice(answer):
    assert unsafe_medication_spans(answer) == []


def test_review_failure_returns_safe_fallback(monkeypatch):
    layer = SafetyLayer()
    monkeypatch.setattr(layer, "_review", lambda *a, **k: (_ for _ in ()).throw(ValueError()))
    out, flags = layer.review("anything")
    assert flags == ["safety_review_failed"] and "clinician" in out


def test_local_digits_are_normalized_for_grounding():
    assert to_ascii_digits("HbA1c ६.५ ੭੨ ૮ ৯") == "HbA1c 6.5 72 8 9"


def test_daily_token_budget(monkeypatch):
    monkeypatch.setattr(settings, "member_daily_token_budget", 100)
    monkeypatch.setattr(settings, "redis_url", "")
    store = RequestControlStore()
    store.check_token_budget("budget-user")
    store.record_token_usage("budget-user", 120)
    with pytest.raises(RateLimitedError):
        store.check_token_budget("budget-user")
