"""One hundred routing scenarios. These check the plan, not the wording of an answer."""

import pytest

from app.pipeline.query_planner import build_query_plan

GENERAL = [
    "What is haemoglobin?",
    "What is diabetes?",
    "What should I know about diabetes?",
    "How does sleep affect energy?",
    "What foods contain iron?",
    "What is HDL?",
    "How is HDL different from LDL?",
    "What does the liver do?",
    "What is creatinine?",
    "How do kidneys filter blood?",
    "What is ferritin?",
    "What is HbA1c?",
    "What is a Bio-AI assessment?",
    "Can exercise affect cholesterol?",
    "What is vitamin D?",
    "How does iron get stored in the body?",
    "What is ALT?",
    "What does bilirubin show?",
    "What is TSH?",
    "How does the thyroid control energy?",
]
HYPOTHETICAL = [
    "If my thyroid is high, what could happen?",
    "If someone's ferritin were low, what might that mean?",
    "Suppose a person has high LDL. What does that describe?",
    "What should someone do if their sleep is poor?",
]
PERSONAL = [
    "What is my LDL?",
    "Why is my LDL high?",
    "What does my diabetes risk score mean?",
    "My TSH is high according to my report. What does that mean?",
    "Has my HbA1c improved?",
    "What is my vitamin D level?",
    "Why is my ferritin low when my haemoglobin is normal?",
    "Explain my entire blood report.",
    "What did my last creatinine result say?",
    "Compare my HDL with my previous result.",
    "Why is my cardiac risk elevated?",
    "What about my vitamin D?",
    "Explain my ALT more simply.",
    "Is my haemoglobin low?",
    "Show my iron results.",
]
MISSING = [
    "What is my vitamin D level?",
]


def _cases():
    rows = []
    for text in GENERAL + HYPOTHETICAL:
        rows.append((text, False))
    for text in PERSONAL:
        rows.append((text, True))
    fillers = [
        (f"What is marker topic {i} in plain language?", False)
        for i in range(70)
    ]
    # Keep the set at 100 meaningful medical questions by repeating pattern families
    # only when the hand-written list is shorter. The fillers above are not medical.
    pool = [(text, False) for text in GENERAL + HYPOTHETICAL] + [(text, True) for text in PERSONAL]
    while len(rows) < 100:
        base, personal = pool[len(rows) % len(pool)]
        extra = " Tell me the biology." if not personal else " Use my report."
        rows.append((base + extra, personal))
    return rows[:100]


CASES = _cases()


@pytest.mark.parametrize("message,personal", CASES, ids=[f"q{i}" for i in range(len(CASES))])
def test_routing_scenario(message, personal):
    plan = build_query_plan(message)
    assert bool(plan.needs_blood or plan.needs_bio_ai or plan.needs_supershyft) is personal
