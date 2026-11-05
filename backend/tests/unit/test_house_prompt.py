"""The house prompt variant (the shipped default): voice, no hidden brevity hints, JSON contract."""

import re

import pytest

from app.core.config import Settings, settings
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.prompt_modules import HOUSE_CORE
from tests.unit.test_answer_quality import _context

QUESTIONS = [
    "What does my HbA1c mean?",
    "Explain my blood report.",
    "What does my Bio-AI diabetes score mean?",
    "What is HbA1c?",
    "How can I optimize my diet based on my blood report?",
]

# Per question steering lines that cap length or forbid advice. The house voice must not carry them.
HIDDEN_HINTS = (
    "NARRATIVE LENGTH",
    "PRESENTATION:",
    "No lifestyle advice",
    "30 to 60 words",
    "Use 2 to 4 bullets",
    "Use 3 to 5 grouped bullets",
    "Depth: lookup. Be concise.",
)


@pytest.fixture
def house():
    old = (settings.cura_prompt_variant, settings.cura_response_mode)
    settings.cura_prompt_variant = "house"
    settings.cura_response_mode = "plain"
    yield
    settings.cura_prompt_variant, settings.cura_response_mode = old


def _build(message):
    ctx = _context(message)
    system, user = PromptBuilder().build(ctx, "", message)
    return system["content"], user["content"]


def test_shipped_defaults_are_house_and_plain():
    fields = Settings.model_fields
    assert fields["cura_prompt_variant"].default == "house"
    assert fields["cura_response_mode"].default == "plain"
    assert fields["llm_max_output_tokens"].default >= 1200


def test_house_core_has_no_dashes_and_one_json_contract():
    assert "—" not in HOUSE_CORE and "–" not in HOUSE_CORE
    assert HOUSE_CORE.count("Return one valid JSON object") == 1
    for field in ("answer", "claims", "recommendation_candidates", "follow_up_questions", "safety_flags", "escalation"):
        assert field in HOUSE_CORE


def test_house_core_is_smaller_than_the_legacy_system_prompt():
    from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS

    assert len(HOUSE_CORE) < len(SAFETY_INSTRUCTIONS)


@pytest.mark.parametrize("message", QUESTIONS)
def test_house_prompt_carries_the_voice_and_no_brevity_caps(house, message):
    system, user = _build(message)
    assert system.startswith("You are the SuperShyft Health Assistant")
    for phrase in ("12 year old", "bullet points only", "Indian", "no bold label at the start of either", "## What to do next"):
        assert phrase in system
    for hint in HIDDEN_HINTS:
        assert hint not in system and hint not in user, hint
    assert f"User question: {message}" in user


def test_house_follow_up_instruction_asks_for_four_kinds_of_question(house):
    system, _user = _build("What does my HbA1c mean?")
    assert "exactly 4 questions" in system
    kinds = [system.index(f"{i}. {name}:") for i, name in enumerate(("Understanding", "Personal relevance", "Action", "Explore"), 1)]
    assert kinds == sorted(kinds)
    assert re.search(r"never repeat", system, re.I)
    assert "Never assume a symptom" in system


def test_house_report_parts_come_in_the_required_order():
    order = ["SHAPE 1A", "One opening bullet", "First bullet, the numbers", "Second bullet, the meaning", "## What to do next", "SHAPE 1B, a Bio-AI report"]
    positions = [HOUSE_CORE.index(part) for part in order]
    assert positions == sorted(positions)
    assert "Teach the body system first, the biomarker second, the medical term third" in HOUSE_CORE
    assert "report_counts" in HOUSE_CORE and "within_range_by_body_system" in HOUSE_CORE
    assert "**What the numbers show:**" not in HOUSE_CORE and "**What it means:**" not in HOUSE_CORE


def test_legacy_variant_is_unchanged_and_still_available():
    old = settings.cura_prompt_variant
    settings.cura_prompt_variant = "legacy"
    try:
        system, user = _build("What does my HbA1c mean?")
    finally:
        settings.cura_prompt_variant = old
    assert system.startswith("You are Cura, SuperShyft's preventive-health companion")
    assert "NARRATIVE LENGTH" in user


def test_house_variant_raises_the_structured_answer_temperature(house):
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    client = OpenAICompatibleLLMClient.__new__(OpenAICompatibleLLMClient)
    client.model = "openai/gpt-5-mini"
    client.personal_health = False
    payload = client._build_payload([{"role": "user", "content": "hi"}], "json_object")
    assert payload["temperature"] == settings.answer_temperature > 0
    settings.cura_prompt_variant = "legacy"
    payload = client._build_payload([{"role": "user", "content": "hi"}], "json_object")
    assert payload["temperature"] == 0


def test_house_prompt_uses_twelve_year_old_voice_and_short_report_limits():
    assert "12 year old" in HOUSE_CORE and "5 year old" not in HOUSE_CORE
    assert "at most 4" in HOUSE_CORE
    assert "under about 230 words" in HOUSE_CORE


def test_house_prompt_picks_the_shape_from_the_question():
    assert "SHAPE 1" in HOUSE_CORE and "SHAPE 2" in HOUSE_CORE
    assert "NO headings" in HOUSE_CORE
    assert "Check direction before you explain a cause" in HOUSE_CORE
    assert "Never list missing tests" in HOUSE_CORE


def test_findings_are_ranked_by_distance_outside_their_range():
    from app.contracts.presentation import PresentedFinding
    from app.pipeline.presentation import _distance_outside_range

    mild = PresentedFinding(label="a", numeric_value=5.22, reference_low=3.5, reference_high=5.2)
    big = PresentedFinding(label="b", numeric_value=178.8, reference_low=0, reference_high=100)
    inside = PresentedFinding(label="c", numeric_value=50, reference_low=0, reference_high=100)
    assert _distance_outside_range(big) > _distance_outside_range(mild) > _distance_outside_range(inside) == 0


def test_house_prompt_carries_the_spec_safety_and_bio_ai_rules():
    for phrase in (
        "universal sunlight duration",
        "laboratory reference range",
        "never invent another scale",
        "does not rule out a condition",
        "Answer the question first",
    ):
        assert phrase in HOUSE_CORE


def test_house_follow_ups_are_spread_across_different_areas():
    assert "DIFFERENT results or body areas" in HOUSE_CORE
    assert "diet preference" in HOUSE_CORE


def test_house_general_follow_ups_stay_on_the_topic():
    assert "about THIS topic" in HOUSE_CORE
    assert "Never ask about routine blood tests" in HOUSE_CORE


def test_bio_ai_layout_states_the_scale_and_the_disclaimer_once():
    assert "AT MOST ONCE" in HOUSE_CORE
    for band in ("Healthy (0 to 25)", "Increased Risk (26 to 50)", "High Risk (51 to 75)", "Very High Risk (76 to 100)"):
        assert band in HOUSE_CORE
    assert "**How to read the scores:**" not in HOUSE_CORE and "**Then:**" not in HOUSE_CORE
    assert "**What to do first:**" in HOUSE_CORE
    assert "64 out of 100" in HOUSE_CORE
    assert "Say this here and nowhere else" in HOUSE_CORE


def test_advice_is_specific_and_adult():
    assert "thoughtful dietitian" in HOUSE_CORE
    assert "Never vague advice" in HOUSE_CORE
    assert "name the foods, how much or how often" in HOUSE_CORE


def test_nutrition_overview_is_detected_and_gets_its_own_layout():
    from app.pipeline.prompt_modules import NUTRITION_OVERVIEW, is_nutrition_overview

    assert is_nutrition_overview("What should I know about my nutrition?")
    assert not is_nutrition_overview("What can I eat to lower my LDL?")
    assert not is_nutrition_overview("What is a balanced diet?")
    assert "What to do next" in NUTRITION_OVERVIEW and "no bold label" in NUTRITION_OVERVIEW
