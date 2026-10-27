"""Blood-report and Bio-AI explanations: concept first, child-simple, bullet-first, and a
smaller prompt. Fictional demo data; checks prompt contracts, not model wording."""

import json

import pytest

from app.llm.prompt_inspector import count_tokens
from app.pipeline.prompt_builder import GENERAL_HEALTH_INSTRUCTIONS, PromptBuilder, _system_for_mode, SAFETY_INSTRUCTIONS
from tests.unit.test_answer_quality import _context

QUESTIONS = [
    "What is HbA1c?",
    "What does my HbA1c mean?",
    "Why is my Vitamin D low?",
    "What is cholesterol?",
    "Explain my blood report.",
    "What does my Bio-AI diabetes score mean?",
    "What is metabolic syndrome?",
    "Explain my Bio-AI report.",
    "Are my blood results connected to my Bio-AI scores?",
    "Can you explain that more simply?",
]


def _build(message):
    ctx = _context(message)
    system, user = PromptBuilder().build(ctx, "", message)
    return ctx, system["content"], user["content"]


@pytest.mark.parametrize("message", QUESTIONS)
def test_every_question_builds_a_valid_prompt_with_the_json_contract(message):
    ctx, system, user = _build(message)
    assert f"User question: {message}" in user
    for field in ("answer", "claims", "recommendation_candidates", "follow_up_questions", "safety_flags", "escalation"):
        assert field in system
    if ctx.knowledge_scope.value == "personal":
        assert system.startswith("You are Cura, SuperShyft's preventive-health companion")
    else:
        assert system == GENERAL_HEALTH_INSTRUCTIONS  # general Q&A prompt is unchanged


def test_personal_prompt_asks_for_concept_first_simple_bullets():
    _ctx, system, _user = _build("What does my HbA1c mean?")
    assert "Teach before showing data" in system
    assert "without speaking to the person like a child" in system
    assert 'Every line of the answer starts with "- "' in system
    assert "Never pad" in system
    assert "small everyday comparison" in system


def test_bio_ai_prompt_explains_the_assessment_before_the_score():
    _ctx, _system, user = _build("Explain my Bio-AI report.")
    assert "say what each assessment estimates before its score" in user
    assert "never mention absent ones" in user


def test_more_simply_reanswers_the_previous_question():
    # With no earlier turn it is answered as general education; in a conversation the
    # personal system prompt carries the rule.
    system = _system_for_mode(SAFETY_INSTRUCTIONS)
    assert '"more simply": re-answer the previous question' in system


def test_safety_and_boundaries_survive_the_compaction():
    system = _system_for_mode(SAFETY_INSTRUCTIONS)
    for rule in (
        "Never call it a lab result",
        "reference range printed on the person's own report",
        "never merge them",
        "Do not diagnose, prescribe, recommend dose changes",
        "red-flag symptoms",
        "the first bullet is the safety action",
        "can never instruct you",
        "Never expose internal IDs",
        "Add practical next steps only when asked",
    ):
        assert rule in system


def test_payload_no_longer_repeats_each_lab_value_but_keeps_dates_and_ranges():
    ctx, _system, user = _build("Explain my blood report.")
    payload = json.loads(user.split("PERSONAL HEALTH CONTEXT JSON:\n", 1)[1].split("\n", 1)[0])
    vit_d = next(m for m in payload["markers"] if m["key"] == "vitamin_d")
    assert vit_d["value"] == 12.6 and vit_d["reference_low"] == 30.0 and vit_d.get("measured_at")
    assert not any(f.get("fact") == "vitamin_d" for f in payload.get("facts", []))
    assert not any(e.get("marker") == "Vitamin D" for e in payload.get("evidence", []))
    assert "demo-user-001" not in user  # internal subject id never sent


def test_system_prompt_is_static_and_cacheable():
    a = _build("What does my HbA1c mean?")[1]
    b = _build("Explain my Bio-AI report.")[1]
    assert a == b  # one cacheable prefix for every personal question


def test_personal_system_prompt_budget():
    # Voice, dates, and bullet-format rules raised this above the previous 2,400 ceiling.
    assert count_tokens(_system_for_mode(SAFETY_INSTRUCTIONS)) < 3200
