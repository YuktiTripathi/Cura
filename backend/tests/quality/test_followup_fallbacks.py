"""Follow-ups when health data is missing: useful questions, nothing fabricated."""

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import MarkerFlag as F
from app.contracts.uploaded_document import DocumentHealthFact
from app.pipeline.followup_generator import (
    FALLBACK, FollowUpBrief, build_brief, document_followups, fallback_questions, select_followups, stage_of,
)

BLOOD = [
    BloodMarker(id="1", key="hba1c", name="HbA1c", value=9.1, unit="%", flag=F.high),
    BloodMarker(id="2", key="vitamin_d", name="Vitamin D", value=12.6, unit="ng/mL", flag=F.low),
]
BIO = [BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=84, status="Very High")]


def _all(brief, current=None, count=4):
    return select_followups(brief, current_question=current, count=count)


def test_no_reports_gets_general_questions():
    qs = fallback_questions(FollowUpBrief(), count=3)
    assert qs == list(FALLBACK["none"][:3])
    assert "How can I improve my overall health?" in qs


def test_blood_only_never_mentions_bio_ai_or_scores():
    qs = _all(build_brief(markers=BLOOD))
    assert qs and not any(w in q.lower() for q in qs for w in ("bio-ai", "score", "risk estimate"))


def test_bio_only_never_names_a_test_or_value():
    qs = _all(build_brief(risks=BIO))
    assert qs
    assert not any(t in q for q in qs for t in ("HbA1c", "LDL", "vitamin", "blood test", "my results"))
    assert any("Dyslipidemia" in q for q in qs)


def test_missing_biomarker_is_never_suggested():
    brief = build_brief(markers=BLOOD)
    qs = select_followups(brief, current_question=None, count=4,
                          model_questions=["Is my LDL too high?", "Why is my ferritin normal?"])
    assert not any("LDL" in q or "ferritin" in q for q in qs)


def test_no_earlier_report_means_no_trend_questions():
    qs = _all(build_brief(markers=BLOOD))
    assert not any(stage_of(q) == "trends" for q in qs)
    assert not select_followups(build_brief(markers=BLOOD), current_question=None, count=3,
                                model_questions=["Has my HbA1c changed since last time?"])[:1] == [
        "Has my HbA1c changed since last time?"]
    assert "What should I focus on improving?" in select_followups(
        build_brief(markers=BLOOD), current_question="Why is my HbA1c high?", count=4)


def test_no_lifestyle_data_means_no_assumptions():
    brief = build_brief(markers=BLOOD)
    qs = select_followups(brief, current_question=None, count=3,
                          model_questions=["Is my poor sleep raising my HbA1c?", "Does my diet explain my vitamin D?"])
    assert not any("sleep" in q or "my diet explain" in q for q in qs)
    # Asking the member to share context is allowed.
    assert "Can I tell you about my diet and activity?" in [
        c for c, *_ in __import__("app.pipeline.followup_generator", fromlist=["_candidates"])._candidates(brief)]


def test_unreadable_report_suggests_a_clearer_upload():
    fact = DocumentHealthFact(display_name="Haemoglobin", value="illegible", source_document_id="d1")
    texts = [s.text for s in document_followups([fact], message="Explain my report")]
    assert "Can I upload a clearer copy of my report?" in texts
    assert len(texts) >= 2


def test_never_fewer_than_two_suggestions():
    healthy = [BloodMarker(id="1", key="tsh", name="TSH", value=2.0, unit="uIU/mL", flag=F.normal)]
    assert len(_all(build_brief(markers=healthy), count=3)) >= 2


def test_fallback_set_is_safe_and_grounded():
    for kind, questions in FALLBACK.items():
        for q in questions:
            assert q.endswith("?") and len(q.split()) <= 12, (kind, q)
            assert not any(w in q.lower() for w in ("dose", "mg", "prescri", "stop taking"))


def test_chat_member_without_reports_still_gets_general_questions():
    from tests.quality.test_conversation_quality import ask

    body = ask("member-without-reports", "Help me understand my latest blood report")
    texts = [f["text"] for f in body["follow_ups"]]
    assert 2 <= len(texts) <= 3
    assert not any(w in t.lower() for t in texts for w in ("hba1c", "ldl", "vitamin d", "score"))


def test_chat_follow_ups_survive_a_model_failure(monkeypatch):
    from app.core.config import settings
    from app.core.errors import LLMUnavailableError
    from app.llm.openai_compatible import OpenAICompatibleLLMClient
    from tests.quality.test_conversation_quality import ask

    def down(*_a, **_k):
        raise LLMUnavailableError("timeout")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", down)
    body = ask("demo-user-001", "Help me understand my latest blood report")
    texts = [f["text"] for f in body["follow_ups"]]
    assert len(texts) >= 2
    assert all(t.endswith("?") for t in texts)
