"""Properties of the answer specification. These do not call the language model."""

import pytest

from app.pipeline.query_planner import build_query_plan


CASES = [
    ("What is LDL cholesterol?", "explain", "optional", False, False),
    ("What is my LDL?", "lookup", "required", False, False),
    ("Why is my LDL high?", "interpret", "required", False, False),
    ("What does my chloride result mean?", "interpret", "required", False, False),
    ("Is my liver functioning properly?", "interpret", "required", False, False),
    ("What is heart health?", "explain", "optional", False, False),
    ("How is my heart health?", "interpret", "required", False, False),
    ("How is my overall health?", "synthesize", "required", True, False),
    ("What should I do to improve my cholesterol?", "advise", "required", False, True),
    ("Explain LDL without using my reports.", "explain", "none", False, False),
]


@pytest.mark.parametrize(("message", "goal", "personal", "broad", "advice"), CASES)
def test_answer_spec_matches_the_question_class(message, goal, personal, broad, advice):
    plan = build_query_plan(message)
    spec = plan.task_contract or {}
    assert spec.get("goal") == goal, message
    assert spec.get("personal_context") == personal, message
    assert spec.get("broad_summary") is broad, message
    assert spec.get("recommendations_requested") is advice, message
    if not broad:
        assert "ldl" not in spec.get("card_keys", []) or "ldl" in (message or "").lower() or "cholesterol" in message.lower() or "heart" in message.lower()


def test_narrow_question_does_not_approve_a_whole_report():
    spec = build_query_plan("What does my chloride result mean?").task_contract
    assert spec["broad_summary"] is False
    assert spec["goal"] == "interpret"
    assert len(spec["card_keys"]) <= 6


def test_blood_report_starter_asks_for_an_explanation():
    from app.pipeline.response_planner import is_report_level_request

    plan = build_query_plan("Help me understand my latest blood report")
    spec = plan.task_contract or {}
    assert plan.intent.value == "report_explanation"
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is False
    assert spec["goal"] == "interpret"
    assert spec["length_band"] == "120-180"
    assert spec["broad_summary"] is False
    assert spec["recommendations_requested"] is False
    assert spec["primary_source"] == "blood_report"
    assert is_report_level_request("Help me understand my latest blood report") is False
    assert is_report_level_request("Show me my latest blood report") is True


def test_bio_ai_report_explanation_is_an_interpretation():
    plan = build_query_plan("Explain my latest Bio-AI report")
    spec = plan.task_contract
    assert spec["goal"] == "interpret"
    assert spec["length_band"] == "120-180"
    assert spec["broad_summary"] is False
    assert spec["recommendations_requested"] is False
    assert spec["primary_source"] == "bio_ai"
    assert plan.needs_blood is False


def test_definition_is_not_rewritten_as_a_lookup():
    spec = build_query_plan("What is LDL cholesterol?").task_contract
    assert spec["goal"] == "explain"
    assert spec["intent"] == "general_health_question"
