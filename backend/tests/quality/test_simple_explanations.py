"""Blood-report and Bio-AI explanations: concept first, child-simple, bullet-first, and a
smaller prompt. Fictional demo data; checks prompt contracts, not model wording."""

import inspect
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
    assert system.startswith("# CURA, your personal health companion")


def test_personal_prompt_asks_for_friendly_explanation_in_the_bodys_terms():
    _ctx, system, _user = _build("What does my HbA1c mean?")
    assert "simple words" in system
    assert "Answer the actual question directly" in system


def test_bio_ai_prompt_explains_the_assessment_before_the_score():
    _ctx, _system, user = _build("Explain my Bio-AI report.")
    assert "say what each assessment estimates before its score" in user
    assert "never mention absent ones" in user


def test_more_simply_reanswers_the_previous_question():
    # The previous answer travels with the request, so "more simply" rewrites it in simpler words.
    message = "Can you explain that more simply?"
    ctx = _context(message)
    ctx.rewrite_previous_answer = "Your LDL is 162 mg/dL, above your report's range."
    _system, user = PromptBuilder().build(ctx, "", message)
    assert "Your LDL is 162 mg/dL" in user["content"]


def test_safety_and_boundaries_survive_the_rewrite():
    from app.pipeline.prompt_modules import HOUSE_CORE

    system = HOUSE_CORE.lower()
    for rule in (
        "do not diagnose, prescribe",
        "predicted risks, not confirmed diagnoses",
        "never invent personal information",
        "medical safety",
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
    # The conversational prompt plus the compact contract is far smaller than the old rule list.
    from app.pipeline.prompt_modules import HOUSE_CORE

    assert count_tokens(HOUSE_CORE) < 2000


# Real answers seen in the app (fictional values): the model copied data-sheet formats.
SHEET_ANSWER = """Quick idea: yes, high total cholesterol and high LDL are related, because LDL is a large part of total cholesterol.

- Cholesterol Total 228.9 mg/dl on 2026-08-08: total amount of cholesterol in the blood; this report marks it high.
- LDL Cholestrol Calculated 128.25 mg/dl on 2026-08-08: "bad" cholesterol; this report marks it high.
- HDL Cholestrol Direct 47.5 mg/dl on 2026-08-08: "good" cholesterol; this report marks it normal.
- Your questionnaire: sleeping_hours = Between 5 to 7 hours. Short sleep is linked with higher blood sugar.
- These are associations, not diagnoses. Why might my sleep affect blood sugar or fats?"""


def test_polish_turns_data_sheet_wording_into_plain_speech():
    from app.pipeline.answer_polish import polish_answer

    ctx = _context("Are my high cholesterol total and high LDL cholesterol connected?")
    ctx.bio_ai_risks = []
    ctx.markers = []
    out = polish_answer(SHEET_ANSWER, ctx, intent="latest_result")
    for bad in ("Quick idea:", "marks it", "Cholestrol", "sleeping_hours", " = ", "on 2026-08-08", "Why might my sleep"):
        assert bad not in out, bad
    assert out.startswith("Yes, high total cholesterol")
    # Values and meaning survive.
    for kept in ("228.9 mg/dl", "128.25 mg/dl", "47.5 mg/dl", "higher than the healthy range", "in the healthy range", "Between 5 to 7 hours"):
        assert kept in out, kept


def test_polish_keeps_dates_when_the_answer_compares_two_dates():
    from app.pipeline.answer_polish import _plain_speech

    text = "Your LDL went from 142 mg/dL on 2026-02-10 to 138 mg/dL on 2026-08-18."
    assert _plain_speech(text) == text
