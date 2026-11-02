"""The Blood Report button uses an explicit entry point, not the words in the message."""

from datetime import date

from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.context_ref import ContextRef
from app.contracts.health_context import HealthContext
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.evidence_inventory import assemble_evidence
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.prompt_modules import modules_for
from app.pipeline.query_planner import build_query_plan

BUTTON = "Help me understand my latest blood report"
OVERVIEW = ContextRef(type="blood_report", source="supershyft", entry_point="blood_report_overview")
PLAIN = ContextRef(type="blood_report", source="supershyft")


def _marker(key, name, value, day, report_id, *, low=0, high=100, flag=MarkerFlag.high, unit="U/L"):
    return BloodMarker(
        id=f"{report_id}-{key}",
        key=key,
        name=name,
        value=value,
        unit=unit,
        reference_low=low,
        reference_high=high,
        flag=flag,
        report_id=report_id,
        measured_at=day,
    )


def _plan_overview():
    return build_query_plan(BUTTON, context_ref=OVERVIEW)


def test_button_sets_overview_marker_and_plain_report_text_does_not():
    plan = _plan_overview()
    assert plan.entry_point == "blood_report_overview"
    contract = plan.task_contract
    assert contract["entry_point"] == "blood_report_overview"
    assert contract["response_type"] == "BLOOD_REPORT_OVERVIEW"
    assert contract["primary_source"] == "blood_report"
    assert contract["goal"] == "synthesize"
    assert contract["broad_summary"] is True
    assert plan.intent == IntentType.report_explanation
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is False

    typed = build_query_plan(BUTTON, context_ref=PLAIN)
    assert typed.entry_point is None
    assert (typed.task_contract or {}).get("entry_point") != "blood_report_overview"

    same_words = build_query_plan(BUTTON)
    assert same_words.entry_point is None


def test_follow_up_ldl_and_general_question_leave_the_overview():
    ldl = build_query_plan("What does my LDL mean?")
    assert ldl.entry_point is None
    assert (ldl.task_contract or {}).get("response_type") != "BLOOD_REPORT_OVERVIEW"
    assert ldl.intent != IntentType.report_explanation or ldl.topic

    general = build_query_plan("What is cholesterol?")
    assert general.entry_point is None
    assert general.knowledge_scope == KnowledgeScope.general
    assert (general.task_contract or {}).get("response_type") != "BLOOD_REPORT_OVERVIEW"


def test_overview_keeps_the_whole_latest_report_and_dated_history():
    early = date(2026, 5, 1)
    late = date(2026, 9, 1)
    markers = [
        _marker(f"m{i}", f"Marker {i}", 10 + i, late, "new", flag=MarkerFlag.normal, low=0, high=50)
        for i in range(30)
    ]
    markers[0] = _marker("ldl", "LDL", 162, late, "new", low=0, high=100, unit="mg/dL")
    markers[1] = _marker("alt", "ALT", None, late, "new", flag=MarkerFlag.missing)
    old = BloodReport(
        report_id="old",
        report_date=early,
        markers=[_marker("ldl", "LDL", 140, early, "old", low=0, high=100, unit="mg/dL")],
    )
    latest = BloodReport(report_id="new", report_date=late, markers=markers)
    plan = _plan_overview()
    ctx = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
    )
    evidence = []
    ContextBuilder.__new__(ContextBuilder)._fill_blood(ctx, plan, [old, latest], evidence)
    keys = {item.key for item in ctx.markers}
    assert "ldl" in keys
    assert "m2" in keys
    assert len(ctx.markers) == 29
    assert all(item.report_id == "new" for item in ctx.markers)
    assert any(item.key == "alt" and item.reason == "not_measured" for item in ctx.missing)
    ldl = next(item for item in ctx.markers if item.key == "ldl")
    assert ldl.value == 162
    assert ldl.unit == "mg/dL"
    assert ldl.reference_high == 100
    trend = next(item for item in ctx.comparisons if item.topic == "ldl")
    assert trend.previous_value == 140
    assert trend.previous_date == early
    assert trend.current_value == 162
    assert trend.current_date == late
    assert not any(item.report_id == "old" for item in ctx.markers)

    package = assemble_evidence(plan, ctx)
    packed = {row["key"] for row in package.measurements}
    assert "ldl" in packed
    assert "m2" in packed
    assert len(packed) >= 29


def test_missing_report_stays_a_retrieval_gap():
    plan = _plan_overview()
    ctx = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
        task_contract=plan.task_contract,
    )
    ContextBuilder.__new__(ContextBuilder)._fill_blood(ctx, plan, [], [])
    assert ctx.markers == []
    assert ctx.missing
    assert plan.task_contract["primary_source"] == "blood_report"


def test_overview_prompt_is_added_without_replacing_safety():
    plan = _plan_overview()
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
        task_contract=plan.task_contract,
    )
    messages = PromptBuilder().build(context, "", BUTTON)
    system = messages[0]["content"]
    assert "Blood Report Interpretation Specialist" in system
    assert "Do not prescribe" in system or "do not prescribe" in system.lower()
    assert "Direct Answer" in system
    user = messages[1]["content"]
    assert "latest blood report" in user.lower()
    assert "BLOOD_REPORT_OVERVIEW" in modules_for(context, BUTTON)

    ldl_plan = build_query_plan("What does my LDL mean?")
    ldl_context = context.model_copy(update={"task_contract": ldl_plan.task_contract, "intent": ldl_plan.intent})
    assert "BLOOD_REPORT_OVERVIEW" not in modules_for(ldl_context, "What does my LDL mean?")
