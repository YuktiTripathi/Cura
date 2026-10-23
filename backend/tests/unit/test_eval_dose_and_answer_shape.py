"""Regression tests for dose detection, duplicated answers, and explanation vs diagnosis."""

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse
from app.pipeline.presentation import flatten_structured_response
from app.pipeline.safety import explicit_diagnosis_request


def test_explanation_is_not_a_diagnosis_request():
    assert not explicit_diagnosis_request("Help me understand Absolute Basophils Count at 0.01 10^3/uL.")
    assert not explicit_diagnosis_request("Can you explain my HbA1c? It is 6.1 %.")
    assert explicit_diagnosis_request("Do I have diabetes?")
    assert explicit_diagnosis_request("Please diagnose me from this report.")


def test_explanation_is_not_printed_twice():
    prose = "Basophils are a kind of white blood cell. Your report marks 0.01 as low against 0.02 to 0.1."
    presentation = StructuredResponse(
        mode=ResponseMode.interpretation,
        headline="Red cell context",
        summary=prose,
        findings=[
            PresentedFinding(label="Absolute Basophils Count", value="0.01", unit="10^3/uL", status="low")
        ],
        interpretation=None,
    )
    text = flatten_structured_response(presentation, raw_answer=prose)
    assert text.count("Basophils are a kind of white blood cell") == 1
    assert "0.01" in text
    assert "low" in text


def test_generic_normal_claim_is_prefaced_with_the_report_range():
    from app.contracts.blood import BloodMarker
    from app.pipeline.presentation import prefer_report_range

    marker = BloodMarker(
        id="m",
        key="absolute_basophils_count",
        name="Absolute Basophils Count",
        value=0.0,
        unit="10^3/uL",
        reference_low=0.02,
        reference_high=0.1,
        flag=MarkerFlag.low,
    )
    context = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[marker],
    )
    text = prefer_report_range(
        "Absolute Basophils Count of 0.0 is commonly normal because ranges often start at 0.0.",
        context,
    )
    assert text.lower().startswith("your report marks absolute basophils count as low")
    assert "0.02" in text


def test_report_range_instruction_is_in_the_personal_prompt():
    from app.contracts.blood import BloodMarker
    from app.pipeline.prompt_builder import PromptBuilder

    marker = BloodMarker(
        id="m",
        key="absolute_basophils_count",
        name="Absolute Basophils Count",
        value=0.0,
        unit="10^3/uL",
        reference_low=0.02,
        reference_high=0.1,
        flag=MarkerFlag.low,
    )
    context = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[marker],
        data_source="supershyft",
    )
    messages = PromptBuilder().build(context, "", "Help me understand this result.")
    blob = "\n".join(item["content"] for item in messages)
    assert "must not override" in blob or "must not contradict" in blob
    assert "0.02" in blob or "reference" in blob.lower()
    assert "several markers" in blob.lower() or "different body systems" in blob.lower()
    assert "emergency number" in blob.lower()


def test_marker_explanation_is_not_repeated_for_common_labs():
    from app.contracts.query import QueryPlan

    for name in ("HbA1c", "Hemoglobin", "Albumin", "Triglycerides", "HS-CRP", "TSH"):
        prose = f"{name} reflects a specific measurement. Your report marks it high, which can have several common meanings. A clinician can help decide on a next step."
        presentation = StructuredResponse(
            mode=ResponseMode.interpretation,
            headline=name,
            summary=prose,
            findings=[PresentedFinding(label=name, value="1", unit="u", status="high")],
            interpretation=prose,
        )
        text = flatten_structured_response(presentation, raw_answer=prose)
        assert text.lower().count(prose[:24].lower()) == 1


def test_bun_alias_retrieves_stored_bun_without_merging_a_separate_urea():
    from datetime import date

    from app.contracts.blood import BloodMarker, BloodReport
    from app.pipeline.personal_selection import select_latest_markers

    bun = BloodMarker(id="1", key="bun_urea_nitrogen", name="BUN Urea Nitrogen", value=7.0, unit="mg/dL")
    report = BloodReport(report_id="r", report_date=date(2026, 9, 1), markers=[bun])
    selected, missing = select_latest_markers([report], ["bun"])
    assert missing == []
    assert selected[0].value == 7.0
    assert selected[0].name == "BUN Urea Nitrogen"
    urea_only, urea_missing = select_latest_markers([report], ["urea"])
    assert urea_only and urea_only[0].key == "bun_urea_nitrogen"
    both = BloodReport(
        report_id="r2",
        report_date=date(2026, 9, 2),
        markers=[
            bun,
            BloodMarker(id="2", key="urea", name="Urea", value=22.0, unit="mg/dL"),
        ],
    )
    picked, _ = select_latest_markers([both], ["urea"])
    assert picked[0].key == "urea" and picked[0].value == 22.0
    bun_pick, _ = select_latest_markers([both], ["bun"])
    assert bun_pick[0].key == "bun_urea_nitrogen" and bun_pick[0].value == 7.0


def test_report_question_without_an_upload_uses_health_context():
    from app.pipeline.query_planner import build_query_plan

    plan = build_query_plan("Anything in this report I should actually pay attention to, starting with HbA1c?")
    assert plan.needs_user_uploaded is False
    assert plan.needs_blood is True


def test_two_and_three_marker_questions_resolve_each_marker():
    from app.pipeline.lab_parameters import match_lab_keys

    two = match_lab_keys("How do HbA1c and Hemoglobin relate?")
    three = match_lab_keys("HbA1c, Hemoglobin Hb, and BUN Urea Nitrogen. How do these relate?")
    assert "hba1c" in two and "hemoglobin" in two
    assert {"hba1c", "hemoglobin", "bun"} <= set(three)


def test_lab_question_does_not_get_an_ungrounded_emergency_warning():
    from app.pipeline.safety import SafetyLayer
    from app.pipeline.safety_classifier import SafetyClassification

    class Urgent:
        def classify(self, text):
            return SafetyClassification(
                category="urgent_soon", severity="medium", confidence=0.95, language="en", action="caution"
            )

    lab = SafetyLayer(Urgent()).check_input("Is my HbA1c of 7.6% something I should worry about?")
    assert lab.caution is None
    soon = SafetyLayer(Urgent()).check_input("I have had a fever for 4 days.")
    assert soon.caution and "within the next day" in soon.caution

