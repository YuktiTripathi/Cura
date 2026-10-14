from datetime import date

from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.documents.extraction import ExtractedPage
from app.documents.pageindex import build_pageindex, retrieve_pageindex
from app.pipeline.conversation_state import ensure_named_report_metrics
from app.pipeline.lab_parameters import match_lab_keys
from app.pipeline.personal_selection import companion_abnormal_markers
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag


def test_follow_up_names_refetch_the_report_marker():
    plan = QueryPlan(
        intent=IntentType.general_health_question,
        raw_message="But is Absolute Basophils Count at 0.01 10^3/uL actually serious?",
        conversation_turn="follow_up_question",
    )
    plan = ensure_named_report_metrics(plan)
    assert plan.needs_blood is True
    assert "absolute_basophils_count" in plan.requested_metrics
    assert plan.topic == "absolute_basophils_count"


def test_education_question_does_not_force_a_personal_fetch():
    plan = QueryPlan(
        intent=IntentType.general_health_question,
        raw_message="What is a basophil?",
    )
    plan = ensure_named_report_metrics(plan)
    assert plan.needs_blood is False


def test_overview_question_returns_document_text_without_keyword_overlap():
    tree = build_pageindex(
        "doc-a",
        [ExtractedPage(page_number=1, text="Platelet count 180. Vitamin D 25 ng/mL.", character_count=40)],
    )
    hits = retrieve_pageindex(tree, "Explain my uploaded report")
    assert hits
    assert "25" in hits[0].text
    assert hits[0].page_start == 1


def test_named_panel_markers_resolve_without_per_marker_special_cases():
    keys = match_lab_keys(
        "Globulin, BUN Urea Nitrogen, Alkaline Phosphatase, Chlorides, Absolute Neutrophil Count, hs-CRP"
    )
    for key in ("globulin", "bun", "alkaline_phosphatase", "chloride", "absolute_neutrophil_count", "crp"):
        assert key in keys


def test_focus_question_keeps_other_abnormal_results():
    report = BloodReport(
        report_id="r1",
        report_date=date(2026, 9, 1),
        markers=[
            BloodMarker(id="1", key="hemoglobin", name="Hemoglobin", value=11.9, unit="g/dL", flag=MarkerFlag.low, report_id="r1"),
            BloodMarker(id="2", key="tsh", name="TSH", value=10.1, unit="uIU/mL", flag=MarkerFlag.high, report_id="r1"),
            BloodMarker(id="3", key="albumin", name="Albumin", value=4.2, unit="g/dL", flag=MarkerFlag.normal, report_id="r1"),
        ],
    )
    extra = companion_abnormal_markers(reports=[report], selected=[report.markers[0]], message="Which result should I focus on first?")
    assert [item.key for item in extra] == ["tsh"]


def _report(rid, day, markers):
    return BloodReport(report_id=rid, report_date=day, markers=markers)


def _ctx():
    from app.contracts.common import AnswerDepth
    from app.contracts.health_context import HealthContext

    return HealthContext(intent=IntentType.latest_result, answer_depth=AnswerDepth.focused)


def test_unnamed_blood_report_is_not_a_missing_marker():
    from app.pipeline.context_builder import ContextBuilder

    report = _report("r1", date(2026, 9, 6), [
        BloodMarker(id="1", key="hemoglobin", name="Hemoglobin", value=13, unit="g/dL", flag=MarkerFlag.normal, report_id="r1"),
        BloodMarker(id="2", key="esr", name="ESR", value=20, unit="mm/hr", flag=MarkerFlag.high, report_id="r1"),
    ])
    ctx = _ctx()
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        raw_message="Help me understand my latest blood report.",
        needs_blood=True,
    )
    ContextBuilder(None)._fill_blood(ctx, plan, [report], [])
    assert [m.key for m in ctx.markers] == ["esr"]
    assert ctx.missing == []
    assert ctx.in_range_summary.out_of_range == 1


def test_history_keeps_both_dates():
    from app.pipeline.context_builder import ContextBuilder

    def alp(rid, day, value):
        return BloodMarker(id=rid, key="alkaline_phosphatase", name="ALP", value=value, unit="U/L", flag=MarkerFlag.high, report_id=rid)

    reports = [
        _report("a", date(2026, 9, 3), [alp("a", date(2026, 9, 3), 110)]),
        _report("b", date(2026, 9, 6), [alp("b", date(2026, 9, 6), 130)]),
    ]
    ctx = _ctx()
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        raw_message="How has my ALP changed from my earlier report?",
        requested_metrics=["alkaline_phosphatase"],
        needs_blood=True,
    )
    ContextBuilder(None)._fill_blood(ctx, plan, reports, [])
    assert [m.value for m in ctx.markers] == [110, 130]
    assert ctx.comparisons


def test_missing_named_test_is_not_replaced():
    from app.pipeline.context_builder import ContextBuilder
    from app.pipeline.renderer import DeterministicRenderer

    report = _report("r1", date(2026, 9, 6), [
        BloodMarker(id="1", key="fasting_blood_glucose", name="Fasting Sugar", value=75.8, unit="mg/dl", flag=MarkerFlag.normal, report_id="r1"),
    ])
    ctx = _ctx()
    plan = QueryPlan(
        intent=IntentType.latest_result,
        raw_message="What is my latest Postprandial Glucose?",
        requested_metrics=["postprandial_glucose"],
        topic="postprandial_glucose",
        needs_blood=True,
    )
    ContextBuilder(None)._fill_blood(ctx, plan, [report], [])
    assert [m.key for m in ctx.markers] == []
    assert any(item.key == "postprandial_glucose" for item in ctx.missing)
    answer = DeterministicRenderer().render(plan.raw_message, ctx)
    assert "75.8" not in answer
    assert "postprandial" in answer.lower() or "Postprandial" in answer


def test_abnormal_subset_does_not_become_the_report_size():
    from app.pipeline.context_builder import ContextBuilder

    markers = [
        BloodMarker(id="1", key="esr", name="ESR", value=20, unit="mm/hr", flag=MarkerFlag.high, report_id="r1"),
        BloodMarker(id="2", key="albumin", name="Albumin", value=4, unit="g/dL", flag=MarkerFlag.normal, report_id="r1"),
        BloodMarker(id="3", key="sodium", name="Sodium", value=140, unit="mmol/L", flag=MarkerFlag.normal, report_id="r1"),
    ]
    ctx = _ctx()
    plan = QueryPlan(
        intent=IntentType.report_explanation,
        raw_message="Which abnormal results matter most?",
        time_operation="latest_report",
        selectors=["ABNORMAL"],
        needs_blood=True,
    )
    ContextBuilder(None)._fill_blood(ctx, plan, [_report("r1", date(2026, 9, 6), markers)], [])
    assert ctx.in_range_summary.in_range == 2
    assert ctx.in_range_summary.out_of_range == 1
    assert [m.key for m in ctx.markers] == ["esr"]


def test_named_marker_question_is_not_a_whole_health_template():
    from app.pipeline.narrative import wants_narrative_summary

    assert wants_narrative_summary("Is my Absolute Eosinophil Count a reassuring result?") is False
    assert wants_narrative_summary("How am I doing overall, using my reports?") is True


def test_prompt_package_keeps_history_and_questionnaire():
    from app.contracts.common import AnswerDepth
    from app.contracts.health_context import Comparison, HealthContext, InRangeSummary
    from app.contracts.questionnaire import QuestionnaireAnswer
    from app.pipeline.evidence_inventory import assemble_evidence

    ctx = HealthContext(
        intent=IntentType.trend,
        answer_depth=AnswerDepth.focused,
        markers=[
            BloodMarker(id="b", key="alkaline_phosphatase", name="ALP", value=130, unit="U/L", flag=MarkerFlag.high, report_id="b", measured_at=date(2026, 9, 6)),
        ],
        comparisons=[Comparison(topic="alkaline_phosphatase", previous_value=110, current_value=130, previous_date=date(2026, 9, 3), current_date=date(2026, 9, 6))],
        questionnaire=[
            QuestionnaireAnswer(
                response_id="1", assessment_instance_id="a", question_id="q",
                question_key="physical_activity_frequency", question="How much activity?",
                value="30-60 minutes a day", response_type="text", subject_id="u",
            )
        ],
        in_range_summary=InRangeSummary(in_range=50, out_of_range=16, unclassified=5),
    )
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        raw_message="Use my questionnaire answer when you explain my ALP.",
        needs_questionnaire=True,
        task_contract={"response_type": "MARKER_EXPLANATION", "original_message": "questionnaire alkaline phosphatase"},
    )
    package = assemble_evidence(plan, ctx).prompt_payload()
    values = {row["value"] for row in package["measurements"]}
    assert 110 in values and 130 in values
    assert package["questionnaire"][0]["value"] == "30-60 minutes a day"
    assert package["report_counts"]["total_markers"] == 71


def test_blank_scan_does_not_invent_a_section():
    tree = build_pageindex(
        "doc-b",
        [ExtractedPage(page_number=1, text="   ", character_count=0, method="ocr")],
    )
    assert retrieve_pageindex(tree, "Explain my uploaded report") == []
