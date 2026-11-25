"""Deterministic routing checks for conversational questions. No model calls."""

import pytest

from app.pipeline.query_planner import build_query_plan

CASES = [
    ("What is haemoglobin?", False),
    ("What is diabetes?", False),
    ("What should I know about diabetes?", False),
    ("How does sleep affect energy?", False),
    ("What foods contain iron?", False),
    ("If my thyroid is high, what could happen?", False),
    ("What is my LDL?", True),
    ("Why is my LDL high?", True),
    ("What does my diabetes risk score mean?", True),
    ("My TSH is high according to my report. What does that mean?", True),
    ("Has my HbA1c improved?", True),
    ("What is my vitamin D level?", True),
    ("Why is my ferritin low when my haemoglobin is normal?", True),
    ("Explain my entire blood report.", True),
]


@pytest.mark.parametrize("message,personal", CASES)
def test_personal_retrieval_follows_the_question(message, personal):
    plan = build_query_plan(message)
    assert bool(plan.needs_blood or plan.needs_bio_ai or plan.needs_supershyft) is personal
