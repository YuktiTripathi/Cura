from types import SimpleNamespace

import pytest

from app.contracts.blood import BloodMarker
from app.pipeline.answer_plan import (
    AnswerPlan, Component, PlanIntent, Proportion, build_answer_plan, plan_prompt,
)


def _marker(key, name, value, low, high, flag):
    return BloodMarker(id=key, key=key, name=name, value=value, unit="x", reference_low=low, reference_high=high, flag=flag)


def _ctx(markers, *, turn=None, explained=(), kind="MARKER_LOOKUP", goal="interpret", intent="blood_marker_explanation", risks=()):
    return SimpleNamespace(
        markers=markers, bio_ai_risks=list(risks), task_contract={"response_type": kind, "goal": goal},
        intent=SimpleNamespace(value=intent), conversation_turn=turn, facts_already_explained=list(explained),
        explained_entities=[], comparisons=[],
    )


def test_tiny_gap_is_minor_and_brief_and_never_a_goal_to_chase():
    urea = _marker("urea", "Urea", 16.72, 17.0, 43.0, "low")
    plan = build_answer_plan(_ctx([urea]), "What does my Urea result mean?")
    assert plan.intent == PlanIntent.personal_interpretation
    assert plan.proportion == Proportion.minor and plan.detail_level == "brief"
    assert "goal_to_raise_or_lower_waste_marker" in plan.must_not_claim
    text = plan_prompt(plan)
    assert "recheck" not in text.lower() and "minor" not in text.lower()
    assert "Never suggest raising or lowering" in text


def test_large_gap_is_marked_and_escalates():
    vit_d = _marker("vitamin_d", "Vitamin D", 12.6, 30.0, 100.0, "low")
    plan = build_answer_plan(_ctx([vit_d]), "What does my Vitamin D result mean?")
    assert plan.proportion == Proportion.marked
    assert Component.escalation in plan.components and Component.mechanism in plan.components


def test_in_range_is_short_and_skips_cause_and_escalation():
    hba1c = _marker("hba1c", "HbA1c", 5.5, 4.0, 5.6, "normal")
    plan = build_answer_plan(_ctx([hba1c]), "What does my HbA1c mean?")
    assert plan.proportion == Proportion.within_range
    assert Component.mechanism not in plan.components and Component.escalation not in plan.components


def test_food_follow_up_does_not_repeat_the_explanation():
    urea = _marker("urea", "Urea", 16.72, 17.0, 43.0, "low")
    ctx = _ctx([urea], turn="FOLLOW_UP_QUESTION", explained=["Urea"])
    plan = build_answer_plan(ctx, "Which protein foods fit my usual vegetarian meals?")
    assert plan.intent == PlanIntent.follow_up and plan.follow_up
    assert plan.components == [Component.next_steps]
    text = plan_prompt(plan)
    assert "do not explain it again: Urea" in text and "Answer only the new question" in text


def test_missing_range_is_recorded_as_missing_evidence():
    m = _marker("x", "Mystery", 5.0, None, None, "unknown")
    plan = build_answer_plan(_ctx([m]), "What does my Mystery result mean?")
    assert "laboratory_reference_interval" in plan.missing_evidence


def test_plan_carries_no_values_or_report_text():
    urea = _marker("urea", "Urea", 16.72, 17.0, 43.0, "low")
    dumped = build_answer_plan(_ctx([urea]), "What does my Urea result mean?").model_dump_json()
    assert "16.72" not in dumped and "17.0" not in dumped


def test_unknown_plan_values_are_rejected():
    with pytest.raises(Exception):
        AnswerPlan(intent="not_an_intent")


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_modes_never_break_the_prompt(monkeypatch, mode):
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app
    from app.pipeline import prompt_modules as pm

    monkeypatch.setattr(settings, "answer_plan_mode", mode)
    monkeypatch.setattr(settings, "cura_prompt_variant", "house")
    monkeypatch.setattr(settings, "enable_llm", True)
    seen = {}
    original = pm.house_system

    def spy(context, message):
        out = original(context, message)
        seen["system"] = out
        return out

    monkeypatch.setattr(pm, "house_system", spy)
    res = TestClient(app).post("/api/v1/chat", headers={"X-Cura-User-Id": "demo-user-001"}, json={"message": "What does my latest HbA1c mean?"})
    assert res.status_code == 200
    assert seen["system"].startswith("# CURA, your personal health companion")
    assert "ANSWER PLAN" not in seen["system"] and "Begin with ONE short friendly sentence" not in seen["system"]


def test_plain_result_question_is_not_a_trend_just_because_an_earlier_report_exists():
    vit_d = _marker("vitamin_d", "Vitamin D", 12.6, 30.0, 100.0, "low")
    ctx = _ctx([vit_d])
    ctx.comparisons = [object()]
    assert build_answer_plan(ctx, "What does my latest Vitamin D result mean?").intent == PlanIntent.personal_interpretation
    assert build_answer_plan(ctx, "Has my Vitamin D improved since last time?").intent == PlanIntent.trend


def test_already_explained_names_are_plain_words():
    urea = _marker("urea", "Urea", 16.72, 17.0, 43.0, "low")
    ctx = _ctx([urea], turn="FOLLOW_UP_QUESTION", explained=["vitamin_d"])
    assert "vitamin d" in plan_prompt(build_answer_plan(ctx, "Which foods can help?"))
    assert "vitamin_d" not in plan_prompt(build_answer_plan(ctx, "Which foods can help?"))


def test_plain_lookup_is_brief_not_an_explanation():
    ldl = _marker("ldl", "LDL", 160.0, 0.0, 100.0, "high")
    plan = build_answer_plan(_ctx([ldl], goal="lookup"), "What is my LDL?")
    assert plan.intent == PlanIntent.lookup and plan.detail_level == "brief"
    assert Component.simple_explanation not in plan.components and Component.mechanism not in plan.components


def test_general_questions_with_a_marker_name_are_not_result_interpretations():
    vit_d = _marker("vitamin_d", "Vitamin D", 12.6, 30.0, 100.0, "low")
    ctx = _ctx([vit_d], kind=None, goal="explain", intent="blood_marker_explanation")
    assert build_answer_plan(ctx, "Can I take vitamin D with calcium?").intent != PlanIntent.personal_interpretation
    assert build_answer_plan(ctx, "Do I need a thyroid test?").intent != PlanIntent.personal_interpretation


def test_comparing_two_markers_is_not_a_trend():
    ctx = _ctx([_marker("glucose", "Glucose", 95.0, 70.0, 100.0, "normal")], kind=None, goal="compare")
    ctx.comparisons = [object()]
    assert build_answer_plan(ctx, "Compare my sugar and insulin").intent != PlanIntent.trend


def test_why_follow_up_keeps_the_reasons_but_not_the_definition():
    vit_d = _marker("vitamin_d", "Vitamin D", 12.6, 30.0, 100.0, "low")
    ctx = _ctx([vit_d], turn="FOLLOW_UP_QUESTION", explained=["vitamin_d"], kind=None, goal="explain")
    plan = build_answer_plan(ctx, "Why is it low?")
    assert plan.intent == PlanIntent.cause
    assert Component.mechanism in plan.components and Component.simple_explanation not in plan.components


def test_why_is_it_important_is_an_explanation_not_a_cause_question():
    tsh = _marker("tsh", "TSH", 2.0, 0.4, 4.0, "normal")
    assert build_answer_plan(_ctx([tsh]), "Why is my TSH important?").intent == PlanIntent.personal_interpretation


def test_exact_point_count_is_passed_to_the_model():
    plan = build_answer_plan(_ctx([_marker("glucose", "Glucose", 95.0, 70.0, 100.0, "normal")], kind=None), "Summarise my health in 3 points")
    assert plan.requested_points == 3
    assert "exactly 3 points" in plan_prompt(plan)
    assert build_answer_plan(_ctx([]), "Explain it in two sentences").requested_points == 2


def test_out_of_range_question_gets_a_list_plan_without_headings():
    plan = build_answer_plan(_ctx([_marker("ldl", "LDL", 138.0, 0.0, 100.0, "high")], kind=None), "Which of my blood values are out of range?")
    assert plan.intent == PlanIntent.out_of_range_list
    text = plan_prompt(plan)
    assert "outside their range" in text and "ANSWER PLAN" not in text


def test_plan_never_forces_a_shape_or_a_severity_from_range_distance():
    vit_d = _marker("vitamin_d", "Vitamin D", 12.6, 30.0, 100.0, "low")
    plan = build_answer_plan(_ctx([vit_d], goal="lookup"), "What is my latest Vitamin D?")
    text = plan_prompt(plan)
    for forbidden in ("ANSWER PLAN", "Begin with ONE", "in this order", "well outside", "routine recheck", "not call it minor"):
        assert forbidden not in text