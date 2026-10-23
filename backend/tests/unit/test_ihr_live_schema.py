"""IHR mapping against the live individual_health_report schema (no invented columns)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from app.main import app
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.personal_selection import latest_bio_report, select_bio_risks
from app.pipeline.query_planner import build_query_plan
from app.pipeline.renderer import DeterministicRenderer
from app.providers.registry import build_registry, set_registry
from integrations.supershyft.db import reset_engine, sanitize_db_error
from integrations.supershyft.ihr import IhrRepository, _IHR_SELECT, reset_ihr_cache
from integrations.supershyft.mapping import bio_ai_from_row, blood_report_from_row

client = TestClient(app)


def _live_bio_reports(*, include_dyslipidemia=True, extra_diseases=None):
    diseases = [
        {
            "code": "hypertension",
            "name": "Hypertension",
            "risk_status": "Healthy",
            "risk_score_scaled": 10,
            "lifestyle_contribution": 0,
            "disease_percentile": 1,
            "healthy_percentile": 20,
        }
    ]
    if include_dyslipidemia:
        diseases.append(
            {
                "code": "dyslipidemia",
                "name": "Dyslipidemia",
                "risk_status": "Healthy",
                "risk_score_scaled": 3,
                "lifestyle_contribution": 0,
                "disease_percentile": 1,
                "healthy_percentile": 24,
            }
        )
    if extra_diseases:
        diseases.extend(extra_diseases)
    return {
        "id": 2,
        "record": "9A51CBC1D5A7",
        "assessment_type": "bio_ai",
        "created_at": "2026-09-24T14:22:32.590808+05:30",
        "metabolic_age": 29,
        "metabolic_score": 15,
        "diseases": diseases,
        "notes": None,
        "file": None,
    }


def _live_row(*, user_id=2, report_id=2, reports=None, ldl=None):
    payload = reports if reports is not None else _live_bio_reports()
    if ldl is not None:
        payload = {
            **payload,
            "blood_report_raw": {
                "digital_data": [
                    {"test_name": "LDL Cholesterol Calculated", "value": str(ldl), "unit": "mg/dl"},
                ]
            },
        }
    return {
        "report_id": report_id,
        "user_id": user_id,
        "assessment_instance_id": 19,
        "engagement_id": 15,
        "reports": payload,
        "created_at": None,
        "report_url": "https://example.test/ihr",
    }


def _stub_profile(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.providers.SuperShyftUserProvider.get_profile",
        lambda self, principal: UserProfile(subject_id=str(principal.subject_id), display_name=""),
    )


def test_ihr_sql_matches_live_columns_only():
    sql = str(_IHR_SELECT)
    assert "blood_parameters" not in sql
    assert "blood_report_raw" not in sql
    for column in (
        "report_id",
        "user_id",
        "assessment_instance_id",
        "engagement_id",
        "reports",
        "created_at",
        "report_url",
    ):
        assert column in sql
    assert "WHERE user_id = :uid" in sql.replace("\n", " ")


def test_live_schema_bio_ai_parses_dyslipidemia_from_reports_diseases():
    report = bio_ai_from_row(type("R", (), _live_row())())
    assert report is not None
    selected, missing = select_bio_risks(report, ["dyslipidemia"])
    assert missing == []
    assert selected[0].name == "Dyslipidemia"
    assert selected[0].score == 3
    assert selected[0].status == "Healthy"
    assert report.assessment_instance_id == "19"
    assert report.engagement_id == "15"
    assert report.report_url


def test_live_schema_ignores_legacy_blood_columns_on_the_row():
    row = type(
        "R",
        (),
        {
            **_live_row(),
            "blood_parameters": {"ldl": 999},
            "blood_report_raw": {"digital_data": [{"test_name": "LDL", "value": "999"}]},
        },
    )()
    assert blood_report_from_row(row) is None


def test_ldl_from_reports_json_not_from_invented_columns():
    report = blood_report_from_row(type("R", (), _live_row(ldl=94.92))())
    assert report is not None
    ldl = next(m for m in report.markers if m.key == "ldl")
    assert ldl.value == 94.92


def test_missing_ldl_is_not_invented():
    report = blood_report_from_row(type("R", (), _live_row())())
    assert report is None


def test_missing_bio_ai_disease_is_not_substituted():
    report = bio_ai_from_row(type("R", (), _live_row(reports=_live_bio_reports(include_dyslipidemia=False)))())
    assert report is not None
    selected, missing = select_bio_risks(report, ["dyslipidemia"])
    assert selected == []
    assert missing == ["dyslipidemia"]


def test_repository_filters_other_user_live_schema_rows(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=99, report_id=99, ldl=999)],
    )
    bundle = IhrRepository().get_ihr_data_for_query(
        AuthenticatedPrincipal(subject_id="2"),
        QueryPlan(intent=IntentType.bio_ai_score, needs_bio_ai=True, needs_supershyft=True, topic="dyslipidemia"),
    )
    assert bundle.user_id == 2
    assert bundle.bio_ai_reports == []
    assert bundle.blood_reports == []


def test_repository_returns_dyslipidemia_for_authenticated_user(monkeypatch):
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    plan = build_query_plan("What is my Dyslipidemia score?")
    assert plan.intent == IntentType.bio_ai_score
    bundle = IhrRepository().get_ihr_data_for_query(AuthenticatedPrincipal(subject_id="2"), plan)
    latest = latest_bio_report(bundle.bio_ai_reports)
    selected, missing = select_bio_risks(latest, ["dyslipidemia"])
    assert missing == []
    assert selected[0].score == 3
    assert selected[0].status == "Healthy"


def test_repository_fetches_ihr_rows_once_and_preserves_sorted_content(monkeypatch):
    calls = 0
    rows = [
        _live_row(user_id=2, report_id=2),
        _live_row(user_id=2, report_id=1),
    ]

    def fetch_once(_principal):
        nonlocal calls
        calls += 1
        return rows

    monkeypatch.setattr("integrations.supershyft.ihr.fetch_ihr_rows", fetch_once)
    bundle = IhrRepository().get_ihr_data_for_query(
        AuthenticatedPrincipal(subject_id="2"),
        QueryPlan(intent=IntentType.bio_ai_explanation, needs_bio_ai=True),
    )
    assert calls == 1
    assert bundle.report_ids == ["1", "2"]
    assert [report.report_id for report in bundle.bio_ai_reports] == ["bioai-1", "bioai-2"]
    assert bundle.bio_ai_reports[0].risks[0].score == 10


def test_chat_dyslipidemia_uses_retrieved_live_schema_score(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my Dyslipidemia score?"},
        ).json()
        assert "3" in body["answer"]
        assert "Healthy" in body["answer"]
        assert "personal SuperShyft health data" not in body["answer"]
        assert body["meta"]["intent"] == "bio_ai_score"
    finally:
        set_registry(None)


def test_chat_ldl_from_reports_json(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id), ldl=118)],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my LDL?"},
        ).json()
        assert "118" in body["answer"]
        assert "personal SuperShyft health data" not in body["answer"]
    finally:
        set_registry(None)


def test_chat_missing_ldl_does_not_invent_or_claim_unavailable(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my LDL?"},
        ).json()
        assert "118" not in body["answer"]
        assert "personal SuperShyft health data" not in body["answer"]
        assert "no matching blood result" in body["answer"].lower() or "not present" in body["answer"].lower()
        names = [item["name"] for item in (body.get("provenance") or {}).get("sources") or []]
        assert "Blood Report" not in names
    finally:
        set_registry(None)


def test_chat_missing_bio_ai_score_is_honest(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "jev_enabled", False)
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id), reports=_live_bio_reports(include_dyslipidemia=False))],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "2"},
            json={"message": "What is my Dyslipidemia score?"},
        ).json()
        assert "score not available" in body["answer"].lower()
        assert "3" not in body["answer"]
    finally:
        set_registry(None)


def test_schema_error_is_not_classified_as_not_found():
    classified = sanitize_db_error(
        Exception('(psycopg.errors.UndefinedColumn) column "blood_parameters" does not exist')
    )
    assert classified == "schema mismatch"
    assert sanitize_db_error(TimeoutError("connection timed out")) == "connection timeout"


def test_context_missing_marker_vs_provider_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_provider", "supershyft")
    _stub_profile(monkeypatch)
    monkeypatch.setattr(
        "integrations.supershyft.ihr.fetch_ihr_rows",
        lambda principal: [_live_row(user_id=int(principal.subject_id))],
    )
    reset_ihr_cache()
    set_registry(None)
    try:
        ctx = ContextBuilder(build_registry()).build(
            AuthenticatedPrincipal(subject_id="2"),
            QueryPlan(
                intent=IntentType.latest_result,
                topic="ldl",
                requested_metrics=["ldl"],
                needs_blood=True,
                needs_supershyft=True,
                knowledge_scope=KnowledgeScope.personal,
            ),
        )
        assert ctx.markers == []
        assert ctx.missing
        answer = DeterministicRenderer().render("What is my LDL?", ctx)
        assert "personal SuperShyft health data" not in answer
    finally:
        set_registry(None)


def _live_db_url() -> str:
    return (os.environ.get("SUPERSHYFT_DATABASE_URL") or "").strip()


@pytest.mark.skipif(
    os.environ.get("CURA_LIVE_SUPERSHYFT") != "1" or not _live_db_url(),
    reason="opt-in live SuperShyft integration; set CURA_LIVE_SUPERSHYFT=1 and SUPERSHYFT_DATABASE_URL",
)
def test_live_user_2_dyslipidemia_is_read_from_reports_diseases(monkeypatch):
    from app.core.config import settings
    from sqlalchemy import text
    from integrations.supershyft.db import get_supershyft_engine, run_readonly

    monkeypatch.setattr(settings, "supershyft_database_url", _live_db_url())
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    reset_engine()
    reset_ihr_cache()
    principal = AuthenticatedPrincipal(subject_id="2")
    plan = build_query_plan("What is my Dyslipidemia score?")
    bundle = IhrRepository().get_ihr_data_for_query(principal, plan)
    latest = latest_bio_report(bundle.bio_ai_reports)
    assert latest is not None
    selected, missing = select_bio_risks(latest, ["dyslipidemia"])
    assert missing == []
    raw_rows = run_readonly(
        text("SELECT reports FROM individual_health_report WHERE user_id = :uid ORDER BY report_id"),
        {"uid": 2},
    )
    stored = None
    for raw in raw_rows:
        diseases = (raw.get("reports") or {}).get("diseases") or []
        for item in diseases:
            if isinstance(item, dict) and str(item.get("code") or "").lower() == "dyslipidemia":
                stored = item
    assert stored is not None
    assert selected[0].score == float(stored["risk_score_scaled"])
    assert selected[0].status == stored["risk_status"]
    reset_engine()


@pytest.mark.skipif(
    os.environ.get("CURA_LIVE_SUPERSHYFT") != "1" or not _live_db_url(),
    reason="opt-in live SuperShyft integration; set CURA_LIVE_SUPERSHYFT=1 and SUPERSHYFT_DATABASE_URL",
)
def test_live_user_2_ldl_and_hba1c_come_from_blood_bookings(monkeypatch):
    from app.core.config import settings
    from app.pipeline.personal_selection import select_latest_markers
    from integrations.supershyft.db import reset_engine
    from integrations.supershyft.blood import reset_blood_cache

    monkeypatch.setattr(settings, "supershyft_database_url", _live_db_url())
    monkeypatch.setattr(settings, "health_provider", "supershyft")
    reset_engine()
    reset_ihr_cache()
    reset_blood_cache()
    principal = AuthenticatedPrincipal(subject_id="2")
    bundle = IhrRepository().get_ihr_data_for_query(
        principal,
        QueryPlan(
            intent=IntentType.latest_result,
            needs_blood=True,
            topic="ldl",
            requested_metrics=["ldl", "hba1c"],
            time_operation="latest_marker",
        ),
    )
    selected, missing = select_latest_markers(bundle.blood_reports, ["ldl", "hba1c"])
    assert missing == []
    by_key = {marker.key: marker for marker in selected}
    assert by_key["ldl"].value == 94.92
    assert by_key["hba1c"].value == 5.3
    assert all(str(marker.report_id or "").startswith("blood-") for marker in selected)
    reset_engine()
