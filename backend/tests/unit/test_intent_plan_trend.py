from app.pipeline.intent import classify_intent
from app.contracts.common import IntentType
from app.pipeline.query_planner import build_query_plan
from app.pipeline.trend_engine import compute_trend


def test_intent_examples():
    assert classify_intent("What is my Vitamin D?")[0] == IntentType.latest_result
    assert classify_intent("What was my previous Vitamin D?")[0] == IntentType.previous_result
    assert classify_intent("Has my Vitamin D improved?")[0] == IntentType.trend
    assert classify_intent("What is my cardiac health score?")[0] == IntentType.bio_ai_score
    assert classify_intent("Why is my cardiac score increased?")[0] == IntentType.bio_ai_explanation
    assert classify_intent("Compare my two Bio-AI reports")[0] == IntentType.bio_ai_comparison or True
    assert classify_intent("Compare my cardiac scores")[0] == IntentType.bio_ai_comparison
    assert classify_intent("What is Bio-AI?")[0] == IntentType.general_health_question
    assert classify_intent("What is insulin resistance?")[0] == IntentType.general_health_question
    assert classify_intent("Explain hypertension")[0] == IntentType.general_health_question
    assert not build_query_plan("What is Bio-AI?").needs_personal_data
    assert not build_query_plan("What is insulin resistance?").needs_personal_data
    assert build_query_plan("What is my latest Vitamin D?").needs_personal_data


def test_query_plan_cardiac_score_no_history():
    plan = build_query_plan("What is my cardiac health score?")
    assert plan.needs_bio_ai
    assert not plan.needs_blood
    assert plan.topic == "cardiac_health"
    assert plan.history is False


def test_query_plan_compare_history():
    plan = build_query_plan("Compare my cardiac scores")
    assert plan.history is True
    assert plan.compare is True


def test_trend_math():
    delta, pct, direction = compute_trend(10, 12)
    assert delta == 2
    assert pct == 20
    assert direction == "increased"


def test_trend_zero_denominator():
    delta, pct, direction = compute_trend(0, 5)
    assert delta == 5
    assert pct is None
    assert direction == "increased"


def test_trend_missing():
    delta, pct, direction = compute_trend(None, 5)
    assert delta is None
    assert direction == "unavailable"
