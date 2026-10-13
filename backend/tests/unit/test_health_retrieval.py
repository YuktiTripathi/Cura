import json
from datetime import date

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import IntentType, KnowledgeScope, MarkerFlag
from app.contracts.query import QueryPlan
from app.documents.structured import ExtractedHealthDocument, extract_structured_from_chunks
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry
from app.retrieval.router import HealthRetrievalRouter


class _Chunk:
    def __init__(self, text, page=1):
        self.text = text
        self.page_start = page


def test_general_ldl_definition_requests_related_blood_context():
    plan = build_query_plan("What is LDL?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.general_personalization is True
    assert plan.needs_blood is True


def test_my_doctor_told_me_does_not_query_ihr():
    plan = build_query_plan("My doctor told me LDL is bad. What does LDL mean?")
    router = HealthRetrievalRouter(build_registry())
    called = {"blood": False}

    class Probe:
        def query(self, *args, **kwargs):
            called["blood"] = True
            return []

    router.registry.blood = Probe()
    result = router.retrieve(AuthenticatedPrincipal(subject_id="5"), plan)
    assert result.ihr_called is False
    assert called["blood"] is False
    assert not plan.needs_personal_data


def test_personal_ldl_invokes_retrieval():
    plan = build_query_plan("What is my LDL?")
    router = HealthRetrievalRouter(build_registry())
    result = router.retrieve(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert plan.needs_personal_data
    assert result.invoked is True
    assert result.ihr_called is True
    assert result.blood_reports


def test_cholesterol_latest_blood_report_routes_to_ihr():
    plan = build_query_plan("Tell me my cholesterol level from latest blood report.")
    assert plan.needs_personal_data
    assert plan.needs_blood or plan.needs_supershyft
    assert plan.needs_user_uploaded is False


def test_causes_high_ldl_is_general():
    plan = build_query_plan("What causes high LDL?")
    assert plan.needs_personal_data is False
    assert plan.needs_supershyft is False


def test_historical_ldl_requests_history():
    plan = build_query_plan("What was my LDL last year?")
    assert plan.needs_personal_data
    assert plan.history is True
    assert plan.time_scope in {"year", "previous"}


def test_metabolic_age_retrieves_bio_ai():
    plan = build_query_plan("What is my metabolic age?")
    router = HealthRetrievalRouter(build_registry())
    result = router.retrieve(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert plan.needs_bio_ai
    assert result.ihr_called is True
    assert result.bio_ai_reports or result.invoked


def test_pdf_extraction_captures_lipids_and_does_not_invent():
    text = (
        "Lipid profile\nLDL 118 mg/dL reference 0-100\nHDL 52 mg/dL\n"
        "Triglycerides 140 mg/dL\nHbA1c 5.4 %"
    )
    extracted = extract_structured_from_chunks("doc-1", [_Chunk(text)])
    keys = {b.normalized_name for b in extracted.biomarkers}
    assert {"ldl", "hdl", "triglycerides", "hba1c"} <= keys
    ldl = next(b for b in extracted.biomarkers if b.normalized_name == "ldl")
    assert ldl.value == 118
    assert ldl.unit == "mg/dL"
    assert ldl.source_page == 1
    assert extracted.extracted_once is True
    missing = extract_structured_from_chunks("doc-2", [_Chunk("This report discusses diet only.")])
    assert all(b.normalized_name != "ldl" or b.value is None for b in missing.biomarkers)
    assert not any(b.normalized_name == "ldl" and b.value is not None for b in missing.biomarkers)


def test_pdf_question_uses_stored_extraction(monkeypatch):
    from app.retrieval import documents as docmod

    stored = ExtractedHealthDocument(
        document_id="d1",
        biomarkers=[
            {
                "name": "LDL",
                "normalized_name": "ldl",
                "value": 121,
                "unit": "mg/dL",
                "source_page": 2,
            }
        ],
    )
    calls = {"extract": 0}

    class Row:
        id = "d1"
        user_id = "user-a"
        original_filename = "blood.pdf"
        metadata_json = json.dumps({"structured_health": stored.model_dump(mode="json")})

    class Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [Row()]

    class DB:
        def query(self, model):
            return Q()

        def commit(self):
            return None

    def boom(*args, **kwargs):
        calls["extract"] += 1
        raise AssertionError("must not re-extract")

    monkeypatch.setattr(docmod, "extract_health_document", boom)
    plan = QueryPlan(
        intent=IntentType.latest_result,
        knowledge_scope=KnowledgeScope.personal,
        topic="ldl",
        needs_user_uploaded=True,
    )
    docs, evidence, used = docmod.retrieve_structured_documents(
        DB(), AuthenticatedPrincipal(subject_id="user-a"), plan, ["d1"]
    )
    assert used is True
    assert calls["extract"] == 0
    assert evidence
    assert evidence[0].value == 121
    assert evidence[0].source == "user_uploaded"


def test_cross_source_keeps_ihr_and_pdf_distinct():
    plan = QueryPlan(
        intent=IntentType.trend,
        knowledge_scope=KnowledgeScope.personal,
        topic="ldl",
        needs_blood=True,
        needs_supershyft=True,
        needs_user_uploaded=True,
        needs_cross_source=True,
    )
    router = HealthRetrievalRouter(build_registry())
    router.registry.blood.query = lambda principal, p: [
        BloodReport(
            report_id="ihr-1",
            report_date=date(2026, 1, 1),
            markers=[
                BloodMarker(id="1", key="ldl", name="LDL", value=118, unit="mg/dL", flag=MarkerFlag.high)
            ],
        )
    ]
    result = router.retrieve(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert result.ihr_called is True
    assert result.documents_called is False  # no db session
    assert result.blood_reports[0].markers[0].value == 118


def test_user_b_cannot_read_user_a_structured_document():
    from app.retrieval import documents as docmod

    class Row:
        id = "d1"
        user_id = "user-a"
        original_filename = "blood.pdf"
        metadata_json = None

    class Q:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class DB:
        def query(self, model):
            return Q([])

        def commit(self):
            return None

    plan = QueryPlan(intent=IntentType.latest_result, topic="ldl", needs_user_uploaded=True)
    docs, evidence, _ = docmod.retrieve_structured_documents(
        DB(), AuthenticatedPrincipal(subject_id="user-b"), plan, ["d1"]
    )
    assert docs == []
    assert evidence == []


def test_postgres_unavailable_does_not_block_general():
    plan = build_query_plan("What causes high LDL?")
    router = HealthRetrievalRouter(build_registry())

    class Boom:
        def query(self, *args, **kwargs):
            raise RuntimeError("db down")

    router.registry.blood = Boom()
    result = router.retrieve(AuthenticatedPrincipal(subject_id="5"), plan)
    assert result.invoked is False
    assert result.ihr_called is False
