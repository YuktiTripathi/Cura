"""Regression checks for the v5 smoke failures. No network and no clinical records."""

from datetime import date

import pytest

from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.pipeline.bio_ai_selection import requested_blood_dates, requested_report_date
from app.pipeline.intent import requires_personal_record
from app.pipeline.personal_selection import select_markers_on_dates
from app.routing.jev_client import routing_state_has_personal_context
from app.routing.schemas import JevRoutingState


def _marker(key, name, value, day):
    return BloodMarker(
        id=f"{key}-{day}",
        key=key,
        name=name,
        value=value,
        unit="mg/dl",
        flag=MarkerFlag.unknown,
        measured_at=day,
    )


def test_dated_stored_question_is_personal_and_fails_closed(monkeypatch):
    message = "On 2026-09-02 and 2026-09-07, what glucose-related result name and value are stored on each date?"
    assert requires_personal_record(message) is True
    assert routing_state_has_personal_context(JevRoutingState(current_message=message)) is True
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", False)
    monkeypatch.setattr(settings, "cura_openrouter_require_zdr", False)
    from app.llm.openrouter_policy import messages_contain_personal_clinical

    assert messages_contain_personal_clinical([{"role": "user", "content": message}])
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", OpenAICompatibleLLMClient._real_complete)
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=False)
    with pytest.raises(LLMUnavailableError, match="not approved"):
        client.complete([{"role": "user", "content": message}])


def test_general_hba1c_definition_stays_non_personal():
    message = "What is HbA1c used to measure?"
    assert requires_personal_record(message) is False
    assert routing_state_has_personal_context(JevRoutingState(current_message=message)) is False


def test_requested_dates_do_not_use_the_later_report():
    early = date(2026, 9, 2)
    later = date(2026, 9, 7)
    reports = [
        BloodReport(report_id="a", report_date=early, markers=[_marker("glucose", "Average Blood Glucose", 125.5, early)]),
        BloodReport(report_id="b", report_date=later, markers=[_marker("glucose", "Average Estimated Glucose", 105.41, later)]),
    ]
    selected, missing = select_markers_on_dates(reports, ["glucose"], [early, later])
    assert missing == []
    assert [(item.name, item.value, item.measured_at) for item in selected] == [
        ("Average Blood Glucose", 125.5, early),
        ("Average Estimated Glucose", 105.41, later),
    ]


def test_cross_source_dates_stay_on_their_own_source():
    text = (
        "My 2026-09-01 blood report shows Cholesterol Total at 199.4 mg/dl. "
        "My 2026-09-06 Bio-AI record stores Dyslipidemia as Healthy (score 8.0)."
    )
    assert requested_blood_dates(text) == [date(2026, 9, 1)]
    assert requested_report_date(text) == date(2026, 9, 6)


def test_sitting_phrase_is_a_questionnaire_topic():
    from app.pipeline.questionnaire_topics import questionnaire_topic

    text = (
        'I recorded "1-4 hours" for "How long do you sit continuously every day '
        'due to work or lifestyle?"'
    )
    assert questionnaire_topic(text) == "sitting"


def test_undated_questionnaire_answer_is_kept():
    from integrations.supershyft.questionnaire import _usable_response

    assert _usable_response({"completed_at": None, "answer": "1-4 hours", "status": None})
    assert _usable_response({"completed_at": None, "answer": None, "status": None}) is False


def test_stored_result_dose_request_keeps_retrieval_open():
    from app.pipeline.safety import SafetyLayer

    decision = SafetyLayer().check_input(
        "My 2026-09-04 blood report stores Bilirubin Direct at 0.15 mg/dl. "
        "Can you diagnose me from it and tell me what dose to take?"
    )
    assert decision.blocked is False
    assert decision.category == "medication_misuse"
    assert "dose" in (decision.caution or "").lower()
    pure = SafetyLayer().check_input("Which drug should I start and what dose?")
    assert pure.blocked is True


def test_specific_dated_marker_does_not_expand_its_family():
    from app.pipeline.context_builder import _dated_display_keys

    message = "On 2026-09-02, HbA1c is 6.0 % and the stored flag is high."
    assert _dated_display_keys(message, ["hba1c", "glucose", "fasting_blood_glucose", "ldl"]) == ["hba1c"]


def test_panel_question_keeps_family_expansion():
    from app.pipeline.context_builder import _dated_display_keys

    family = ["ldl", "hdl", "cholesterol", "triglycerides"]
    assert _dated_display_keys("Show my full lipid panel on 2026-09-01", family) == family


def test_general_hba1c_definition_does_not_need_personal_records():
    from app.pipeline.query_planner import build_query_plan

    plan = build_query_plan("What is HbA1c used to measure?")
    assert plan.needs_personal_data is False
    assert plan.needs_blood is False
    assert plan.knowledge_scope.value == "general"


def test_dated_result_without_my_stays_personal():
    message = "On 2026-09-02 and 2026-09-07, what glucose-related result name and value are stored on each date?"
    assert requires_personal_record(message) is True


def test_page_filter_drops_other_pages():
    from app.contracts.uploaded_document import DocumentHealthFact, UploadedDocumentContext
    from app.documents.lookup import cover_requested_entities

    def fact(page, value, code="fasting_blood_glucose"):
        return DocumentHealthFact(
            canonical_code=code,
            display_name="Fasting glucose" if page == 2 else "Estimated glucose",
            value=value,
            unit="mg/dL",
            page_number=page,
            source_document_id="doc",
        )

    ctx = UploadedDocumentContext(document_id="doc", structured_facts=[fact(2, 87.7), fact(6, 140.0, "glucose")])
    rows = cover_requested_entities([ctx], ["fasting_blood_glucose"], "What is the fasting glucose on page 2?")
    values = [item.value for row in rows for item in row.facts]
    assert values == [87.7]
