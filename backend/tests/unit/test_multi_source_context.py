import io
from datetime import date

from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import AnswerDepth, HealthSourceType, IntentType
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.main import app
from app.pipeline.context_merger import ContextMerger
from app.pipeline.cross_source import CrossSourceComparator, SourceValue
from app.pipeline.document_context import resolve_attached_documents
from app.pipeline.health_sources import is_lab_source_compare, sync_plan_sources
from app.pipeline.query_planner import build_query_plan
from app.pipeline.renderer import DeterministicRenderer
from app.providers.registry import build_registry
from app.retrieval.medical import CuratedMedicalKnowledgeProvider
from app.retrieval.router import HealthRetrievalRouter
from app.routing.jev_client import JevDecisionsClient
from app.routing.jev_router import resolve_plan
from app.routing.mapper import plan_from_jev
from app.routing.schemas import (
    JevDecision,
    JevDecisionsResponse,
    JevIntent,
    JevOperation,
    JevSource,
    JevTimeRange,
)
from tests.helpers.pdf_fixtures import make_text_pdf

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}

LDL_PDF = make_text_pdf(
    ["Lipid Profile LDL cholesterol 118 mg/dL Collection date: 28 Sep 2026 HbA1c 6.1 %"]
)
ALT_PDF = make_text_pdf(
    ["Lipid Profile LDL cholesterol 160 mg/dL Collection date: 01 Jan 2026"]
)


def _upload(user="demo-user-001", data=LDL_PDF, filename="Max_Lab_Report.pdf"):
    return client.post(
        "/api/v1/documents",
        headers={"X-Cura-User-Id": user},
        files={"file": (filename, io.BytesIO(data), "application/pdf")},
    ).json()["document_id"]


def test_pdf_only_ldl_in_this_report(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = _upload()
    plan = build_query_plan("What is my LDL in this report?", document_ids=[did])
    assert plan.sources == [HealthSourceType.uploaded_document]
    assert plan.needs_user_uploaded
    assert not plan.needs_bio_ai
    assert "ldl" in (plan.requested_metrics or [plan.topic])
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my LDL in this report?", "document_ids": [did]},
    ).json()
    assert "118" in body["answer"]
    assert body["meta"]["supershyft_called"] is False
    assert "user_uploaded" in body["meta"]["sources_used"]


def test_supershyft_only_metabolic_age_ignores_last_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = _upload()
    first = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my LDL in this report?", "document_ids": [did]},
    ).json()
    cid = first["conversation_id"]
    plan = build_query_plan("What is my metabolic age?")
    assert HealthSourceType.supershyft_bio_ai in plan.sources
    assert HealthSourceType.uploaded_document not in plan.sources
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my metabolic age?", "conversation_id": cid},
    ).json()
    assert "118" not in body["answer"]
    assert body["meta"].get("documents_queried") in {False, None}
    assert body["provenance"]["sources"]
    assert any("Bio-AI" in s["name"] for s in body["provenance"]["sources"])


def test_pdf_plus_supershyft_blood_compare(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = _upload()
    plan = build_query_plan(
        "Compare my LDL in this report with my previous SuperShyft report.",
        document_ids=[did],
    )
    assert HealthSourceType.uploaded_document in plan.sources
    assert HealthSourceType.supershyft_blood in plan.sources
    assert is_lab_source_compare(plan)
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={
            "message": "Compare my LDL in this report with my previous SuperShyft report.",
            "document_ids": [did],
        },
    ).json()
    assert "118" in body["answer"]
    assert "142" in body["answer"] or "138" in body["answer"]
    assert "user_uploaded" in body["meta"]["sources_used"]
    assert "supershyft" in body["meta"]["sources_used"]


def test_pdf_plus_bio_ai_uses_both_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    # demo-user-002 has one Bio-AI report; demo-user-001 has two on the same date, which
    # correctly triggers a "which report?" clarification instead of a combined answer.
    did = _upload(user="demo-user-002")
    plan = build_query_plan(
        "Considering this report and my Bio-AI results, what should I improve?",
        document_ids=[did],
    )
    assert HealthSourceType.uploaded_document in plan.sources
    assert HealthSourceType.supershyft_bio_ai in plan.sources
    assert not is_lab_source_compare(plan)
    body = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={
            "message": "Considering this report and my Bio-AI results, what should I improve?",
            "document_ids": [did],
        },
    ).json()
    answer = body["answer"].lower()
    assert "uploaded_document" in answer or "118" in body["answer"]
    assert "bio" in answer or "metabolic" in answer or "supershyft_bio_ai" in answer


def test_pdf_plus_questionnaire_and_lifestyle(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = _upload()
    plan = build_query_plan(
        "Considering this report, my questionnaire and lifestyle, what should I focus on?",
        document_ids=[did],
    )
    assert HealthSourceType.uploaded_document in plan.sources
    assert HealthSourceType.supershyft_questionnaire in plan.sources
    assert HealthSourceType.supershyft_lifestyle in plan.sources
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={
            "message": "Considering this report, my questionnaire and lifestyle, what should I focus on?",
            "document_ids": [did],
        },
    ).json()
    assert body["meta"].get("documents_queried") is True
    assert "questionnaire" in (plan.data_sources or [])
    assert "lifestyle" in (plan.data_sources or [])


def test_medical_knowledge_only_hba1c_meaning():
    plan = build_query_plan("What does HbA1c mean?")
    assert plan.sources == [HealthSourceType.medical_knowledge]
    assert not plan.needs_personal_data
    docs = CuratedMedicalKnowledgeProvider().query("What does HbA1c mean?", plan.topic, limit=1)
    assert docs
    body = client.post("/api/v1/chat", headers=H, json={"message": "What does HbA1c mean?"}).json()
    assert body["meta"]["supershyft_called"] is False
    assert body["meta"].get("documents_queried") in {False, None}
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert names
    assert set(names) <= {"MedlinePlus", "CDC", "NIDDK", "NICE", "WHO"}


def test_personal_value_plus_medical_knowledge():
    plan = build_query_plan("What is my HbA1c and what does that mean?")
    assert plan.needs_blood or plan.needs_personal_data
    assert plan.needs_medical_knowledge or plan.medical_evidence_required
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my HbA1c and what does that mean?"},
    ).json()
    assert "5.5" in body["answer"] or "5.4" in body["answer"]
    kinds = {s["source_type"] for s in body["provenance"]["sources"]}
    assert "personal_record" in kinds


def test_conflicting_ldl_values_are_not_collapsed():
    ctx = HealthContext(intent=IntentType.latest_result, answer_depth=AnswerDepth.simple)
    ctx.facts = [
        ProvenancedFact(
            fact="ldl",
            value=142,
            unit="mg/dL",
            source="user_uploaded",
            document_id="abc123",
            measured_at=date(2026, 9, 28),
            fact_type=FactKind.measured_data,
            source_type="uploaded_document",
            page=3,
        ),
        ProvenancedFact(
            fact="ldl",
            value=130,
            unit="mg/dL",
            source="SuperShyft",
            report_id="83921",
            measured_at=date(2026, 8, 14),
            fact_type=FactKind.measured_data,
            source_type="supershyft_blood",
        ),
    ]
    merged = ContextMerger().merge_into(ctx, QueryPlan(intent=IntentType.latest_result), "demo-user-001")
    assert merged.source_conflicts
    conflict = merged.source_conflicts[0]
    values = {item.value for item in conflict.values}
    assert values == {142, 130}
    text = DeterministicRenderer().render("What is my LDL?", merged)
    assert "142" in text and "130" in text
    assert "136" not in text
    assert "one number" in text.lower() or "different values" in text.lower()


def test_compare_many_keeps_both_sources():
    results = CrossSourceComparator().compare_many(
        "ldl",
        "LDL",
        [
            SourceValue(source="user_uploaded", value=142, unit="mg/dL", date=date(2026, 9, 28), page=3),
            SourceValue(source="supershyft", value=130, unit="mg/dL", date=date(2026, 8, 14)),
        ],
    )
    assert len(results) == 1
    assert results[0].source_a.value == 142
    assert results[0].source_b.value == 130
    assert results[0].difference == -12


def test_multiple_uploaded_pdfs_do_not_guess(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    _upload(filename="a.pdf")
    _upload(data=ALT_PDF, filename="b.pdf")
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my LDL in this report?"},
    ).json()
    assert body["meta"]["status"] == "document_ambiguous"
    assert "which" in body["answer"].lower()


def test_explicit_document_id_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    first = _upload(filename="a.pdf")
    second = _upload(data=ALT_PDF, filename="b.pdf")
    attached = resolve_attached_documents(
        explicit_ids=[first],
        last_document_id=second,
        completed_docs=[type("D", (), {"document_id": first})(), type("D", (), {"document_id": second})()],
    )
    assert attached.document_ids == [first]
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my LDL in this report?", "document_ids": [first]},
    ).json()
    assert "118" in body["answer"]
    assert "160" not in body["answer"]


def test_this_report_without_uploads_means_the_supershyft_report():
    # Nothing uploaded: "this report" is the member's SuperShyft report, so CURA answers
    # from structured data instead of "I don't have an uploaded report".
    body = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "eval-user-metabolic"},  # no uploads
        json={"message": "What is my LDL in this report?"},
    ).json()
    assert body["meta"]["status"] not in {"document_missing", "document_ambiguous"}
    assert "uploaded report" not in body["answer"].lower()
    assert "96" in body["answer"]  # latest LDL on the SuperShyft report


def test_no_document_selected_uses_personal_records():
    plan = build_query_plan("What is my LDL in this report?")
    assert plan.needs_user_uploaded is False
    assert plan.needs_blood is True


def test_jev_unavailable_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_ for _ in ()).throw(LLMUnavailableError("down")),
    )
    plan, trace = resolve_plan("What is my metabolic age?")
    assert trace.fallback is True
    assert HealthSourceType.supershyft_bio_ai in plan.sources
    assert HealthSourceType.uploaded_document not in plan.sources


def test_malformed_and_low_confidence_jev_fallback(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (
            JevDecision(
                intent=JevIntent.lab_result_lookup,
                source=JevSource.lab_results,
                operation=JevOperation.lookup,
                requires_personal_data=True,
                requested_metrics=["ldl"],
                time_range=JevTimeRange.latest,
                confidence=0.41,
            ),
            JevDecisionsResponse(answers={}, model="jev-test"),
        ),
    )
    plan, trace = resolve_plan("What is my LDL?")
    assert trace.fallback is True
    assert plan.fallback_reason == "low_confidence"
    assert plan.needs_blood


def test_provenance_retained_on_merged_facts():
    ctx = HealthContext(intent=IntentType.latest_result, answer_depth=AnswerDepth.simple)
    ctx.facts = [
        ProvenancedFact(
            fact="ldl",
            value=118,
            unit="mg/dL",
            source="user_uploaded",
            document_id="doc-1",
            fact_type=FactKind.measured_data,
            page=1,
        )
    ]
    merged = ContextMerger().merge_into(ctx, QueryPlan(intent=IntentType.latest_result))
    fact = merged.facts[0]
    assert fact.source_type == "uploaded_document"
    assert fact.source_id == "doc-1"
    assert fact.page == 1
    assert fact.value == 118


def test_user_cannot_retrieve_another_users_uploaded_document(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_path", str(tmp_path / "uploads"))
    did = _upload(user="user-a")
    other = AuthenticatedPrincipal(subject_id="user-b")
    plan = QueryPlan(intent=IntentType.latest_result, needs_user_uploaded=True, topic="ldl")
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = HealthRetrievalRouter(build_registry()).retrieve(
            other, plan, db=db, document_ids=[did]
        )
        assert not result.document_evidence
    finally:
        db.close()
    denied = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "user-b"},
        json={"message": "What is my LDL in this report?", "document_ids": [did]},
    )
    assert denied.status_code in {404, 200}
    if denied.status_code == 200:
        assert "118" not in denied.json()["answer"]


def test_queryplan_supports_multiple_sources_and_active_document():
    plan = QueryPlan(
        intent=IntentType.health_scenario,
        needs_user_uploaded=True,
        needs_bio_ai=True,
        needs_questionnaire=True,
        needs_lifestyle=True,
        needs_general=True,
        document_ids=["abc"],
        active_document_id="abc",
        requested_metrics=["ldl"],
    )
    plan = sync_plan_sources(plan)
    assert plan.sources == [
        HealthSourceType.supershyft_bio_ai,
        HealthSourceType.supershyft_questionnaire,
        HealthSourceType.supershyft_lifestyle,
        HealthSourceType.uploaded_document,
        HealthSourceType.medical_knowledge,
    ]
    assert plan.needs_document_data
    assert plan.needs_medical_knowledge
    assert plan.active_document_id == "abc"


def test_jev_valid_blood_route_does_not_become_pdf_only():
    decision = JevDecision(
        intent=JevIntent.lab_result_lookup,
        source=JevSource.lab_results,
        operation=JevOperation.lookup,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=["ldl"],
        confidence=0.93,
    )
    plan = plan_from_jev(decision, "What is my LDL?", document_ids=["doc-1"])
    assert plan.needs_blood is True
    assert plan.needs_user_uploaded is False
    assert plan.document_ids == ["doc-1"]
    assert HealthSourceType.uploaded_document not in plan.sources
