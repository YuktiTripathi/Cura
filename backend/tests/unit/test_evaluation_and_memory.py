from datetime import date

from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.core.errors import NotFoundError, ProviderUnavailableError
from app.core.copy import PERSONAL_DATA_NOT_FOUND, PERSONAL_DATA_UNAVAILABLE
from app.db.models import Conversation, Feedback, HealthFactRef, Interaction
from app.db.repositories import ConversationRepository
from app.db.session import SessionLocal
from app.documents.structured import extract_structured_from_chunks
from app.main import app
from app.memory.conversation import FollowUpMemory
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.grounding import GroundingChecker
from app.pipeline.query_planner import build_query_plan
from app.pipeline.renderer import DeterministicRenderer
from app.providers.registry import build_registry
from app.retrieval.result import HealthRetrievalResult
from app.retrieval.router import HealthRetrievalRouter
from app.retrieval.status import (
    EXTRACTION_FAILED,
    NO_DATA,
    NOT_REQUIRED,
    PROVIDER_UNAVAILABLE,
    SUCCESS,
    UNAUTHORIZED,
    infer_retrieval_status,
)
from integrations.supershyft.db import DB_CONNECTION_FAILED, DB_NO_RECORDS
from integrations.supershyft.ihr import IhrRepository

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


class _Chunk:
    def __init__(self, text, page=2):
        self.text = text
        self.page_start = page


def test_routing_general_ldl_no_personal():
    plan = build_query_plan("What is LDL?")
    assert plan.needs_personal_data is False
    result = HealthRetrievalRouter(build_registry()).retrieve(AuthenticatedPrincipal(subject_id="5"), plan)
    assert result.status == NOT_REQUIRED
    assert result.invoked is False


def test_routing_my_doctor_not_personal():
    plan = build_query_plan("My doctor told me LDL is bad. What does LDL mean?")
    assert plan.needs_personal_data is False
    assert "my" in plan.raw_message.lower()


def test_routing_personal_ldl():
    plan = build_query_plan("What is my LDL?")
    assert plan.needs_personal_data is True


def test_routing_latest_cholesterol_blood_report():
    plan = build_query_plan("Tell me my cholesterol level from latest blood report.")
    assert plan.needs_personal_data is True
    assert plan.needs_user_uploaded is False


def test_routing_historical_ldl():
    plan = build_query_plan("What was my LDL last year?")
    assert plan.needs_personal_data is True
    assert plan.history is True


def test_routing_metabolic_age():
    plan = build_query_plan("What is my metabolic age?")
    assert plan.needs_bio_ai is True
    assert plan.needs_personal_data is True


def test_ihr_successful_retrieval():
    plan = build_query_plan("What is my latest Vitamin D?")
    result = HealthRetrievalRouter(build_registry()).retrieve(
        AuthenticatedPrincipal(subject_id="demo-user-001"), plan
    )
    assert result.invoked is True
    assert result.ihr_called is True
    assert result.status == SUCCESS
    assert result.blood_reports


def test_ihr_no_matching_data():
    plan = build_query_plan("What is my latest Vitamin D?")
    router = HealthRetrievalRouter(build_registry())

    class Empty:
        def query(self, *args, **kwargs):
            return []

    router.registry.blood = Empty()
    result = router.retrieve(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert result.status == NO_DATA
    assert result.blood_reports == []


def test_ihr_postgres_unavailable(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")

    def boom(*args, **kwargs):
        raise ProviderUnavailableError("down", reason=DB_CONNECTION_FAILED)

    monkeypatch.setattr(IhrRepository, "get_ihr_data_for_query", boom)
    plan = build_query_plan("What is my LDL?")
    router = HealthRetrievalRouter(build_registry())
    try:
        router.retrieve(AuthenticatedPrincipal(subject_id="5"), plan)
        raise AssertionError("expected provider unavailable")
    except ProviderUnavailableError:
        pass


def test_unauthorized_missing_principal():
    plan = build_query_plan("What is my LDL?")
    result = HealthRetrievalRouter(build_registry()).retrieve(AuthenticatedPrincipal(subject_id=""), plan)
    assert result.status == UNAUTHORIZED


def test_ihr_user_isolation_filters_other_user_rows(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [
            {
                "report_id": "other",
                "user_id": 99,
                "assessment_instance_id": 1,
                "engagement_id": 1,
                "reports": {"blood_parameters": {"ldl": 999}, "diseases": []},
                "created_at": "2026-01-01",
                "report_url": None,
            }
        ],
    )
    plan = build_query_plan("What is my LDL?")
    bundle = IhrRepository().get_ihr_data_for_query(AuthenticatedPrincipal(subject_id="5"), plan)
    assert bundle.blood_reports == []
    assert bundle.bio_ai_reports == []


def test_pdf_extraction_preserves_units_dates_pages():
    text = "Report date 20 Sep 2026\nLDL 118 mg/dL reference 0-100"
    extracted = extract_structured_from_chunks("doc-page", [_Chunk(text, page=2)])
    ldl = next(b for b in extracted.biomarkers if b.normalized_name == "ldl")
    assert ldl.value == 118
    assert ldl.unit == "mg/dL"
    assert ldl.source_page == 2
    assert extracted.report_date == date(2026, 9, 20)


def test_pdf_missing_biomarker_is_null():
    extracted = extract_structured_from_chunks("doc-empty", [_Chunk("Diet advice only.", page=1)])
    assert not any(b.normalized_name == "ldl" and b.value is not None for b in extracted.biomarkers)


def test_follow_up_resolves_ldl_context():
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest Vitamin D?"})
    cid = first.json()["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Is that high?", "conversation_id": cid},
    )
    body = second.json()
    assert "Vitamin D" in body["answer"] or "vitamin d" in body["answer"].lower()
    assert "12.6" in body["answer"]


def test_historical_follow_up_keeps_metric():
    memory = FollowUpMemory()
    conv = Conversation(
        id="c1",
        subject_id="demo-user-001",
        follow_up_topic="hba1c",
        follow_up_topic_name="HbA1c",
        current_marker_code="hba1c",
    )
    topic, name = memory.resolve_topic(conv, "What about last year?")
    assert topic == "hba1c"
    assert name == "HbA1c"
    plan = build_query_plan(
        "What about last year?",
        follow_up_topic=topic,
        follow_up_name=name,
        prior_personal=True,
    )
    assert plan.needs_personal_data is True
    assert plan.topic == "hba1c"
    assert plan.history is True or plan.time_scope == "year"


def test_fresh_ihr_overrides_stale_conversation():
    plan = build_query_plan("What is my LDL?")
    retrieval = HealthRetrievalResult(
        invoked=True,
        ihr_called=True,
        blood_reports=[
            BloodReport(
                report_id="fresh",
                report_date=date(2026, 9, 20),
                markers=[
                    BloodMarker(
                        id="m1",
                        key="ldl",
                        name="LDL",
                        value=124,
                        unit="mg/dL",
                        flag=MarkerFlag.high,
                    )
                ],
            )
        ],
        status=SUCCESS,
    )
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        plan,
        retrieval=retrieval,
    )
    answer = DeterministicRenderer().render("What is my LDL?", ctx)
    assert "124" in answer
    assert "118" not in answer
    assert ctx.evidence[0].value == 124


def test_user_b_cannot_read_user_a_conversation():
    created = client.post("/api/v1/chat", headers=H, json={"message": "What is LDL?"}).json()
    stolen = client.get(
        f"/api/v1/conversations/{created['conversation_id']}",
        headers={"X-Cura-User-Id": "demo-user-002"},
    )
    assert stolen.status_code == 404
    db = SessionLocal()
    try:
        repo = ConversationRepository(db)
        try:
            repo.get_for_subject(created["conversation_id"], "demo-user-002")
            raise AssertionError("expected isolation")
        except NotFoundError:
            pass
    finally:
        db.close()


def test_interaction_and_feedback_persisted():
    res = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest Vitamin D?"})
    body = res.json()
    cid = body["conversation_id"]
    assert body["meta"]["retrieval_status"] == SUCCESS
    fb = client.post(
        "/api/v1/feedback",
        headers=H,
        json={"conversation_id": cid, "rating": "down", "comment": "The cholesterol value was incorrect."},
    )
    assert fb.status_code == 200
    db = SessionLocal()
    try:
        interactions = db.query(Interaction).filter(Interaction.conversation_id == cid).all()
        assert interactions
        row = interactions[-1]
        assert row.user_query == "What is my latest Vitamin D?"
        assert row.personal_data_required is True
        assert row.retrieval_status == SUCCESS
        assert row.ihr_queried is True
        assert row.detected_intent
        assert row.grounding_passed is True
        assert row.safety_passed is True
        feedback = db.query(Feedback).filter(Feedback.conversation_id == cid).all()
        assert feedback
        assert feedback[-1].helpful is False
        assert feedback[-1].comment == "The cholesterol value was incorrect."
        assert feedback[-1].interaction_id == row.id
        facts = db.query(HealthFactRef).filter(HealthFactRef.conversation_id == cid).all()
        assert facts
        assert all(f.report_id and f.metric and f.subject_id == "demo-user-001" for f in facts)
    finally:
        db.close()


def test_general_question_records_not_required_and_no_db():
    res = client.post("/api/v1/chat", headers=H, json={"message": "What is cholesterol?"})
    body = res.json()
    assert body["meta"]["retrieval_status"] == NOT_REQUIRED
    assert body["meta"]["retrieval_used"] is False
    assert body["meta"]["supershyft_called"] is False
    assert PERSONAL_DATA_UNAVAILABLE not in body["answer"]


def test_retrieval_status_distinguishes_unavailable_and_no_data():
    assert (
        infer_retrieval_status(
            personal_required=True,
            documents_required=False,
            meta_status="provider_unavailable",
            db_status=DB_CONNECTION_FAILED,
            evidence_count=0,
        )
        == PROVIDER_UNAVAILABLE
    )
    assert (
        infer_retrieval_status(
            personal_required=True,
            documents_required=False,
            meta_status="ok",
            db_status=DB_NO_RECORDS,
            evidence_count=0,
            has_missing=True,
        )
        == NO_DATA
    )
    assert (
        infer_retrieval_status(
            personal_required=False,
            documents_required=True,
            meta_status="document_failed",
            db_status=None,
            evidence_count=0,
        )
        == EXTRACTION_FAILED
    )


def test_no_data_copy_is_not_provider_unavailable():
    assert "can't access your personal SuperShyft" not in PERSONAL_DATA_NOT_FOUND.lower()


def test_grounding_personal_numbers_must_match_evidence():
    ctx = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[
            BloodMarker(id="1", key="ldl", name="LDL", value=118, unit="mg/dL", flag=MarkerFlag.high)
        ],
    )
    checker = GroundingChecker()
    assert checker.unsupported_personal_numbers("Your LDL is 118 mg/dL", ctx) == []
    assert "999" in checker.unsupported_personal_numbers("Your LDL is 999 mg/dL", ctx)


def test_grounding_missing_value_cannot_be_hallucinated():
    ctx = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
    )
    flags = GroundingChecker().unsupported_personal_numbers("Your LDL is 118 mg/dL", ctx)
    assert "118" in flags


def test_semantic_summary_includes_persisted_conversation_continuity():
    import json

    memory = FollowUpMemory()
    conv = Conversation(
        id="memory-v2",
        subject_id="demo-user-001",
        follow_up_topic="vitamin_b12",
        follow_up_topic_name="Vitamin B12",
        conversation_summary="Discussing Vitamin B12",
        conversation_state_json=json.dumps(
            {
                "previous_user_question": "Yes, I take one daily.",
                "previous_assistant_summary": "Your B12 result was low.",
                "recent_context_notes": ["User reported a recent supplement or injection change."],
                "explained_entities": ["vitamin_b12"],
                "current_concern": "understand whether supplementation changes the interpretation",
                "conversation_goal": "FOLLOW_UP",
                "communication_style": "QUICK",
                "previous_assistant_follow_up": "Are you taking a B12 supplement?",
            }
        ),
    )
    summary = memory.semantic_summary(conv)
    assert "What CURA already explained: Your B12 result was low." in summary
    assert "User recently mentioned:" in summary
    assert "Already discussed: vitamin_b12" in summary
    assert "Open conversational thread:" in summary


def test_updated_summary_preserves_user_context_from_persisted_state():
    import json

    memory = FollowUpMemory()
    conv = Conversation(
        id="memory-v2-update",
        subject_id="demo-user-001",
        last_source_mode="supershyft",
        conversation_state_json=json.dumps(
            {
                "previous_assistant_summary": "Your Vitamin D was below the reference range.",
                "recent_context_notes": ["User reported a recent supplement or injection change."],
            }
        ),
    )
    summary = memory.updated_summary(conv, "blood_marker_explanation", "Vitamin D")
    assert "Discussing Vitamin D" in summary
    assert "already explained Your Vitamin D was below the reference range." in summary
    assert "user context User reported a recent supplement or injection change." in summary
