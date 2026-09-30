"""Blood bookings, Bio-AI IHR, and questionnaire status against SuperShyft table shapes."""

from datetime import date

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from integrations.supershyft.blood import _BLOOD_SELECT, fetch_blood_booking_rows, mapped_booking_reports, reset_blood_cache
from integrations.supershyft.ihr import IhrRepository, reset_ihr_cache
from integrations.supershyft.mapping import blood_report_from_booking_row, markers_from_digital_data
from integrations.supershyft.questionnaire import _completed
from tests.unit.test_ihr_live_schema import _live_row


def _booking_row(*, user_id=2, booking_id=2, ldl=94.92, hba1c=5.3, hdl=57.1):
    return {
        "id": booking_id,
        "engagement_participant_id": 15,
        "collection_date": date(2026, 8, 24),
        "collected_at": None,
        "status": 1,
        "diagnostic_report_url": "https://example.test/blood-2",
        "blood_parameters": [
            {
                "group_name": "Lipid Profile",
                "tests": [
                    {
                        "test_name": "LDL Cholestrol Calculated",
                        "parameter_key": "ldl_cholestrol",
                        "value": None,
                        "unit": "mg/dL",
                    },
                    {
                        "test_name": "LDL/HDL Cholestrol",
                        "parameter_key": "ldl/hdl_cholestrol",
                        "value": None,
                    },
                ],
            }
        ],
        "blood_report_raw": {
            "systolic_value": "120",
            "diastolic_value": "80",
            "digital_data": [
                {"test_name": "HDL / LDL Cholesterol Ratio", "value": "0.6", "unit": "Ratio"},
                {"test_name": "Hba1c (Glycosylated Hemoglobin)", "value": str(hba1c), "unit": "%"},
                {"test_name": "Serum HDL Cholesterol", "value": str(hdl), "unit": "mg/dl"},
                {"test_name": "LDL Cholesterol Calculated", "value": str(ldl), "unit": "mg/dl"},
                {"test_name": "LDL / HDL Cholesterol Ratio", "value": "1.66", "unit": "Ratio"},
            ],
        },
        "created_at": None,
        "engagement_id": 15,
        "user_id": user_id,
    }


class _Row:
    def __init__(self, mapping):
        self.__dict__.update(mapping)


def test_booking_mapper_uses_digital_values_not_ratios():
    report = blood_report_from_booking_row(_Row(_booking_row()))
    assert report is not None
    assert report.report_id == "blood-2"
    assert report.report_date == date(2026, 8, 24)
    assert report.engagement_id == "15"
    by_key = {marker.key: marker for marker in report.markers}
    assert by_key["ldl"].value == 94.92
    assert by_key["hdl"].value == 57.1
    assert by_key["hba1c"].value == 5.3
    assert by_key["ldl"].name == "LDL Cholesterol Calculated"


def test_ratio_names_do_not_overwrite_ldl_or_hdl():
    markers = markers_from_digital_data(_booking_row()["blood_report_raw"])
    by_key = {marker.key: marker.value for marker in markers}
    assert by_key["ldl"] == 94.92
    assert by_key["hdl"] == 57.1
    assert by_key["hba1c"] == 5.3


def test_empty_booking_is_skipped():
    empty = _booking_row()
    empty["blood_parameters"] = None
    empty["blood_report_raw"] = None
    assert blood_report_from_booking_row(_Row(empty)) is None


def test_blood_booking_sql_is_user_scoped(monkeypatch):
    from app.core.config import settings

    captured: dict = {}

    def fake_run(statement, params=None, *, fetch="all"):
        captured["sql"] = str(statement)
        captured["params"] = params
        return []

    monkeypatch.setattr(settings, "supershyft_database_url", "postgresql+psycopg://u:p@localhost:5432/db")
    monkeypatch.setattr("integrations.supershyft.blood.run_readonly", fake_run)
    reset_blood_cache()
    fetch_blood_booking_rows(AuthenticatedPrincipal(subject_id="2"))
    sql = captured["sql"].replace("\n", " ")
    assert captured["params"] == {"uid": 2}
    assert "participant_blood_bookings" in sql
    assert "engagement_participants" in sql
    assert "WHERE ep.user_id = :uid" in sql
    assert "blood_parameters" in sql
    assert "blood_report_raw" in sql
    assert "INSERT" not in sql.upper()
    assert "UPDATE" not in sql.upper()
    assert str(_BLOOD_SELECT)


def test_booking_rows_for_other_users_are_dropped(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.blood.fetch_blood_booking_rows",
        lambda principal: [_booking_row(user_id=99, ldl=999)],
    )
    reports = mapped_booking_reports(AuthenticatedPrincipal(subject_id="2"))
    assert reports == []


def test_repository_reads_ldl_from_bookings_not_ihr(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    monkeypatch.setattr(
        "integrations.supershyft.blood.fetch_blood_booking_rows",
        lambda principal: [_booking_row(user_id=int(principal.subject_id))],
    )
    reset_ihr_cache()
    bundle = IhrRepository().get_ihr_data_for_query(
        AuthenticatedPrincipal(subject_id="2"),
        QueryPlan(intent=IntentType.latest_result, needs_blood=True, topic="ldl", requested_metrics=["ldl"]),
    )
    assert bundle.bio_ai_reports
    assert any(risk.code == "dyslipidemia" for report in bundle.bio_ai_reports for risk in report.risks)
    ldl = next(marker for report in bundle.blood_reports for marker in report.markers if marker.key == "ldl")
    assert ldl.value == 94.92
    assert ldl.report_id == "blood-2"


def test_questionnaire_status_two_counts_as_completed():
    assert _completed({"status": 2, "completed_at": None}) is True
    assert _completed({"status": 1, "completed_at": None}) is False
    assert _completed({"status": 1, "completed_at": "2026-08-24T10:00:00+05:30"}) is True
    assert _completed({"status": "completed", "completed_at": None}) is True


def test_questionnaire_instance_accepts_numeric_status():
    from app.contracts.questionnaire import QuestionnaireInstance

    instance = QuestionnaireInstance(
        assessment_instance_id="19",
        subject_id="2",
        status="2",
        answers=[],
    )
    assert instance.status == "2"
