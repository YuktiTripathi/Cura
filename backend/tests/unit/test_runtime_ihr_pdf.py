import json
from datetime import date

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.core.errors import ProviderUnavailableError
from app.documents.llm_extract import extract_structured_with_llm
from app.documents.structured import extract_health_document, extract_structured_from_chunks
from app.pipeline.query_planner import build_query_plan
from integrations.supershyft.db import sanitize_db_error, sanitized_db_target
from integrations.supershyft.diagnose import DATABASE_CONFIG_MISSING, diagnose_supershyft
from integrations.supershyft.ihr import IhrRepository, _sorted_ihr_rows
from integrations.supershyft.mapping import bio_ai_from_row, blood_report_from_row, markers_from_digital_data


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Chunk:
    def __init__(self, text, page=1):
        self.text = text
        self.page_start = page


def test_sanitized_target_omits_password():
    target = sanitized_db_target("postgresql+asyncpg://supershyft_user:secret@localhost:5432/Supershyft_new")
    assert target["host"] == "localhost"
    assert target["port"] == 5432
    assert target["database"] == "Supershyft_new"
    assert target["username"] == "supershyft_user"
    assert "secret" not in json.dumps(target)


def test_missing_psycopg_classified():
    assert sanitize_db_error(ModuleNotFoundError("No module named 'psycopg'")) == "driver missing"


def test_diagnose_missing_url(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "supershyft_database_url", "")
    result = diagnose_supershyft()
    assert result["code"] == DATABASE_CONFIG_MISSING


def test_actual_lipid_aliases_and_digital_data():
    row = _Row(
        report_id=2,
        created_at=None,
        assessment_instance_id=19,
        engagement_id=15,
        report_url="https://example.test/report-2",
        reports={
            "created_at": "2026-09-24T14:22:32+05:30",
            "blood_parameters": [
                {
                    "group_name": "Lipid Profile",
                    "tests": [
                        {
                            "test_name": "Cholesterol Total",
                            "parameter_key": "cholesterol_total",
                            "value": None,
                            "unit": "mg/dL",
                        },
                        {
                            "test_name": "LDL Cholestrol Calculated",
                            "parameter_key": "ldl_cholestrol",
                            "value": None,
                            "unit": "mg/dL",
                        },
                    ],
                }
            ],
            "blood_report_raw": {
                "digital_data": [
                    {"test_name": "Total Cholesterol", "value": "168.6", "unit": "mg/dl", "min_range": "0", "max_range": "200"},
                    {"test_name": "LDL Cholesterol Calculated", "value": "94.92", "unit": "mg/dl"},
                    {"test_name": "Serum HDL Cholesterol", "value": "57.1", "unit": "mg/dl"},
                    {"test_name": "Serum Triglycerides", "value": "82.9", "unit": "mg/dl"},
                ]
            },
        },
    )
    report = blood_report_from_row(row)
    assert report is not None
    by_key = {m.key: m for m in report.markers}
    assert by_key["cholesterol"].value == 168.6
    assert by_key["ldl"].value == 94.92
    assert by_key["hdl"].value == 57.1
    assert by_key["triglycerides"].value == 82.9
    assert report.report_date == date(2026, 9, 24)
    assert report.assessment_instance_id == "19"
    assert report.engagement_id == "15"
    assert report.report_url == "https://example.test/report-2"


def test_latest_report_uses_reports_created_at():
    rows = _sorted_ihr_rows(
        [
            {"report_id": 1, "created_at": None, "reports": {"created_at": "2026-01-01T00:00:00+00:00"}},
            {"report_id": 2, "created_at": None, "reports": {"created_at": "2026-09-24T14:22:32+05:30"}},
        ]
    )
    assert rows[-1]["report_id"] == 2


def test_bio_ai_actual_fields():
    report = bio_ai_from_row(
        _Row(
            report_id=2,
            created_at=None,
            assessment_instance_id=19,
            engagement_id=15,
            report_url="https://example.test/report-2",
            reports={
                "created_at": "2026-09-24T14:22:32+05:30",
                "metabolic_age": 29.0,
                "metabolic_score": 15.0,
                "diseases": [
                    {
                        "code": "diabetes",
                        "name": "Diabetes",
                        "risk_score_scaled": 17,
                        "risk_status": "Healthy",
                        "disease_percentile": 40,
                    }
                ],
            },
        )
    )
    assert report is not None
    assert report.metabolic_age == 29.0
    assert report.risks[0].code == "type_2_diabetes"
    assert report.risks[0].status == "Healthy"
    assert report.report_date == date(2026, 9, 24)
    assert report.assessment_instance_id == "19"


def test_ihr_user_isolation(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [
            {
                "report_id": 99,
                "user_id": 99,
                "assessment_instance_id": 1,
                "engagement_id": 1,
                "reports": {
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "blood_report_raw": {"digital_data": [{"test_name": "Total Cholesterol", "value": "999"}]},
                    "diseases": [{"code": "dyslipidemia", "name": "Dyslipidemia", "risk_score_scaled": 99, "risk_status": "High"}],
                },
                "created_at": None,
                "report_url": None,
            }
        ],
    )
    bundle = IhrRepository().get_ihr_data_for_query(
        AuthenticatedPrincipal(subject_id="2"),
        QueryPlan(intent=IntentType.latest_result, needs_blood=True, needs_bio_ai=True),
    )
    assert bundle.blood_reports == []
    assert bundle.bio_ai_reports == []


def test_general_causes_high_ldl_after_personal_followup():
    plan = build_query_plan(
        "What causes high LDL?",
        follow_up_topic="ldl",
        follow_up_name="LDL",
        prior_personal=True,
    )
    assert plan.needs_personal_data is False


def test_personal_cholesterol_queries_ihr():
    plan = build_query_plan("What is my cholesterol level from my latest blood report?")
    assert plan.needs_personal_data is True
    assert plan.needs_user_uploaded is False


def test_llm_pdf_extraction_valid(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", True)

    class Fake:
        def complete(self, messages, json_mode=False):
            return json.dumps(
                {
                    "document_type": "blood_report",
                    "report_date": "2026-09-20",
                    "biomarkers": [
                        {
                            "name": "LDL",
                            "normalized_name": "ldl",
                            "value": 118,
                            "unit": "mg/dL",
                            "source_page": 2,
                        }
                    ],
                    "bio_ai_metrics": [],
                }
            )

    monkeypatch.setattr("app.documents.llm_extract.get_llm_client", lambda: Fake())
    doc = extract_structured_with_llm("d1", [_Chunk("LDL 118 mg/dL", 2)])
    assert doc is not None
    assert doc.extraction_method == "llm"
    assert doc.biomarkers[0].value == 118
    assert doc.biomarkers[0].source_page == 2


def test_llm_pdf_extraction_malformed(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", True)

    class Fake:
        def complete(self, messages, json_mode=False):
            return "not-json"

    monkeypatch.setattr("app.documents.llm_extract.get_llm_client", lambda: Fake())
    assert extract_structured_with_llm("d1", [_Chunk("LDL 118")]) is None
    fallback = extract_health_document("d1", [_Chunk("LDL 118 mg/dL")])
    assert fallback.extraction_method == "deterministic"
    assert any(b.normalized_name == "ldl" and b.value == 118 for b in fallback.biomarkers)


def test_missing_pdf_biomarker_not_invented():
    extracted = extract_structured_from_chunks("d2", [_Chunk("Diet notes only")])
    assert not any(b.normalized_name == "ldl" and b.value is not None for b in extracted.biomarkers)


def test_blood_pressure_from_raw_header_fields():
    markers = markers_from_digital_data(
        {"systolic_value": "128", "diastolic_value": "82", "digital_data": []}
    )
    by_key = {m.key: m.value for m in markers}
    assert by_key["systolic"] == 128
    assert by_key["diastolic"] == 82


def test_digital_data_does_not_invent_missing_triglycerides():
    markers = markers_from_digital_data({"digital_data": [{"test_name": "Total Cholesterol", "value": "168.6"}]})
    assert all(m.key != "triglycerides" or m.value is None for m in markers)
    assert next(m for m in markers if m.key == "cholesterol").value == 168.6
