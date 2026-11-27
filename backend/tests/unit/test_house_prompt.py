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
    old = settings.cura_response_mode
    settings.cura_response_mode = "plain"
    yield
    settings.cura_response_mode = old


def _build(message):
    ctx = _context(message)
    system, user = PromptBuilder().build(ctx, "", message)
    return system["content"], user["content"]


def test_shipped_defaults_are_house_and_plain():
    fields = Settings.model_fields
    assert fields["cura_response_mode"].default == "plain"
    assert fields["llm_max_output_tokens"].default >= 1200


def test_house_core_has_no_dashes_and_one_json_contract():
    assert "—" not in HOUSE_CORE and "–" not in HOUSE_CORE
    assert HOUSE_CORE.count("valid JSON object") == 1
    for field in ("answer", "claims", "recommendation_candidates", "follow_up_questions", "safety_flags", "escalation"):
        assert field in HOUSE_CORE


@pytest.mark.parametrize("message", QUESTIONS)
def test_house_prompt_carries_the_voice_and_no_brevity_caps(house, message):
    system, user = _build(message)
    assert system.startswith("# CURA, your personal health companion")
    for phrase in ("Answer the actual question directly", "medical knowledge library", "Indian"):
        assert phrase in system
    assert "WHOLE REPORT LAYOUTS" not in system
    for hint in HIDDEN_HINTS:
        assert hint not in system and hint not in user, hint
    assert f"User question: {message}" in user


def test_house_follow_up_instruction_is_natural_and_capped_at_four(house):
    system, _user = _build("What does my HbA1c mean?")
    assert "Generate four" in system
    assert "user's perspective" in system


def test_house_variant_raises_the_structured_answer_temperature(house):
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    client = OpenAICompatibleLLMClient.__new__(OpenAICompatibleLLMClient)
    client.model = "openai/gpt-5-mini"
    client.personal_health = False
    payload = client._build_payload([{"role": "user", "content": "hi"}], "json_object")
    assert payload["temperature"] == settings.answer_temperature > 0


def test_house_prompt_forbids_report_templates_and_unrelated_bio_ai():
    assert "unnecessary headings" in HOUSE_CORE
    assert "Do not mention unrelated information" in HOUSE_CORE
    assert "Never invent personal information" in HOUSE_CORE
    assert "Do not diagnose, prescribe" in HOUSE_CORE


def test_findings_are_ranked_by_distance_outside_their_range():
    from app.contracts.presentation import PresentedFinding
    from app.pipeline.presentation import _distance_outside_range

    mild = PresentedFinding(label="a", numeric_value=5.22, reference_low=3.5, reference_high=5.2)
    big = PresentedFinding(label="b", numeric_value=178.8, reference_low=0, reference_high=100)
    inside = PresentedFinding(label="c", numeric_value=50, reference_low=0, reference_high=100)
    assert _distance_outside_range(big) > _distance_outside_range(mild) > _distance_outside_range(inside) == 0


def test_house_prompt_carries_the_safety_and_bio_ai_rules():
    for phrase in (
        "Do not diagnose, prescribe",
        "predicted risks, not confirmed diagnoses",
        "not instructions",
        "Protect personal health information",
        "percentage probabilities",
    ):
        assert phrase in HOUSE_CORE, phrase


def test_house_follow_ups_stay_relevant_and_personal():
    assert "Generate four" in HOUSE_CORE
    assert "user's perspective" in HOUSE_CORE


def test_nutrition_guidance_answers_the_food_question_first_without_prescriptions():
    from app.pipeline.prompt_modules import is_nutrition_overview

    assert is_nutrition_overview("What should I know about my nutrition?")
    assert not is_nutrition_overview("What can I eat to lower my LDL?")
    assert not is_nutrition_overview("What is a balanced diet?")
    question = "Based on my health results and eating habits, how can I eat better for my body?"
    assert is_nutrition_overview(question)
    from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.pipeline.prompt_modules import house_system

    context = HealthContext(
        intent=IntentType.nutrition_guidance,
        knowledge_scope=KnowledgeScope.personal,
        answer_depth=AnswerDepth.focused,
    )
    system = house_system(context, question)
    assert "NUTRITION" not in system
    assert "WHOLE REPORT LAYOUTS" not in system
    assert "exactly this layout" not in system
    assert "2 to 4 action bullets" not in system
    for old in ("## What your body needs", "## Foods to include", "4 to 6 bullets"):
        assert old not in system


def test_broad_nutrition_sends_food_results_risks_and_habits_together():
    from app.contracts.bio_ai import BioAIRisk
    from app.contracts.blood import BloodMarker
    from app.contracts.common import AnswerDepth, KnowledgeScope, MarkerFlag
    from app.contracts.health_context import HealthContext
    from app.contracts.questionnaire import QuestionnaireAnswer
    from app.pipeline.evidence_inventory import assemble_evidence
    from app.pipeline.query_planner import build_query_plan

    question = "Based on my health results and eating habits, how can I eat better for my body?"
    plan = build_query_plan(question)
    assert plan.needs_blood and plan.needs_bio_ai and plan.needs_questionnaire
    focused = build_query_plan("What can I eat to lower my LDL?")
    assert not focused.needs_bio_ai
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[BloodMarker(id="1", key="vitamin_d", name="Vitamin D", value=12.0, unit="ng/mL", flag=MarkerFlag.low, reference_low=30, reference_high=100)],
        bio_ai_risks=[
            BioAIRisk(code="cardiac_health", name="Cardiac Health", score=40, status="Increased"),
            BioAIRisk(code="thyroid_health", name="Thyroid Health", score=10, status="Healthy"),
        ],
        questionnaire=[
            QuestionnaireAnswer(response_id="r", assessment_instance_id="a", question_id="q", question_key="food_groups", question="Food groups", value="pulses", response_type="text", subject_id="s"),
            QuestionnaireAnswer(response_id="r2", assessment_instance_id="a", question_id="q2", question_key="sleeping_hours", question="Sleep", value="7", response_type="text", subject_id="s"),
        ],
    )
    payload = assemble_evidence(plan, context).prompt_payload()
    assert [row["key"] for row in payload["measurements"]] == ["vitamin_d"]
    assert [row["code"] for row in payload["bio_ai_risks"]] == ["cardiac_health"]
    assert [row["key"] for row in payload["questionnaire"]] == ["food_groups"]
