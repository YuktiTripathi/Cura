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


def test_house_core_is_much_smaller_than_the_legacy_system_prompt():
    from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS

    assert len(HOUSE_CORE) < 0.8 * len(SAFETY_INSTRUCTIONS)


@pytest.mark.parametrize("message", QUESTIONS)
def test_house_prompt_carries_the_voice_and_no_brevity_caps(house, message):
    system, user = _build(message)
    assert system.startswith("You are the SuperShyft Health Assistant")
    for phrase in ("12 year old", "bullet points only", "Indian", "**Looking good:**", "**What to do first:**", "**When to see a doctor:**"):
        assert phrase in system
    for hint in HIDDEN_HINTS:
        assert hint not in system and hint not in user, hint
    assert f"User question: {message}" in user


def test_house_follow_up_instruction_asks_for_three_kinds_of_question(house):
    system, _user = _build("What does my HbA1c mean?")
    assert "exactly 3 questions" in system
    kinds = [system.index(f"{i}. {name}:") for i, name in enumerate(("Understanding", "Personal relevance", "Action"), 1)]
    assert kinds == sorted(kinds)
    assert re.search(r"never repeat", system, re.I)
    assert "Never assume a symptom" in system


def test_house_report_parts_come_in_the_required_order():
    order = ["The verdict", "One bullet for each body area", "**Looking good:**", "**What to do first:**", "**When to see a doctor:**"]
    positions = [HOUSE_CORE.index(part) for part in order]
    assert positions == sorted(positions)
    assert 'NO "##" headings' in HOUSE_CORE


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
    assert "under about 220 words" in HOUSE_CORE


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
        "Do not invent a scale, threshold or method",
        "does not rule out a condition",
        "Answer the question first",
    ):
        assert phrase in HOUSE_CORE
