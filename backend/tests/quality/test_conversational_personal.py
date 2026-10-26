"""Blood-report and Bio-AI answers should read like general Q&A: scoped to the question,
plain, and without forced lists, word counts or next steps. Safety rules must survive.

These check prompt construction and post-processing contracts, not model wording.
"""

import pytest

from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse
from app.core.config import settings
from app.pipeline.presentation import flatten_structured_response
from app.pipeline.prompt_builder import PromptBuilder, SAFETY_INSTRUCTIONS, question_scope
from app.pipeline.reasoning import _missing_score_note
from tests.unit.test_answer_quality import _context

CASES = [
    ("What does my HbA1c mean?", "single_marker"),  # 1 single marker
    ("Is my ferritin low?", "single_marker"),  # 2 abnormal-marker check
    ("Are my HbA1c and fasting glucose connected?", "several_markers"),  # 3 related markers
    ("Explain my complete blood report", "whole_blood"),  # 4 whole blood report
    ("What does my metabolic syndrome score mean?", "single_bio_ai"),  # 5 single Bio-AI
    ("Explain my Bio-AI report", "whole_bio_ai"),  # 6 whole Bio-AI report
    ("How do my Bio-AI scores relate to my blood results?", "cross_source"),  # 7 cross-source
    ("Why?", "follow_up"),  # 8 short follow-up
    ("What should I focus on improving?", "action"),  # 9 action
    ("I have chest pain and my LDL is high, what should I do?", "urgent"),  # 10 safety
]


def _prompt(message: str, *, package: bool = False):
    ctx = _context(message)
    if package:
        ctx.evidence_package = {"measurements": [{"name": "HbA1c", "value": 9.1, "unit": "%"}], "missing": []}
    system, user = PromptBuilder().build(ctx, "", message)
    return ctx, system["content"], user["content"]


@pytest.mark.parametrize("message,scope", CASES)
def test_question_scope_matches_intent(message, scope):
    assert question_scope(_context(message), message) == scope


@pytest.mark.parametrize("message,scope", CASES)
def test_every_personal_branch_carries_the_scope(message, scope):
    for package in (False, True):
        ctx, _system, user = _prompt(message, package=package)
        if ctx.knowledge_scope.value != "personal":
            pytest.skip("general branch")
        assert "QUESTION SCOPE:" in user


def test_active_defaults_are_the_legacy_rich_path():
    assert settings.cura_prompt_variant == "legacy"
    assert settings.answer_prompt_compact is False
    assert settings.cura_response_mode == "rich"
    _ctx, system, _user = _prompt("What does my HbA1c mean?")
    assert system.startswith(SAFETY_INSTRUCTIONS.split("\n")[0])
    assert "PRIORITY ORDER" in system


def test_conflicts_resolved_in_system_prompt():
    _ctx, system, _user = _prompt("Explain my complete blood report")
    # Ranked priorities, with safety above format.
    assert system.index("1. Medical accuracy and safety") < system.index("5. Format and length")
    # No forced bullet count for every multi-point answer, and no hard word caps.
    assert "then 3 to 5 Markdown bullets" not in system
    assert "stays within 150 words" not in system
    assert "guides, not limits" in system
    # Numbers: one clear rule instead of "never repeat" vs "always include".
    assert "say its value and unit (or score and level) once" in system
    # Next steps only when asked or clinically needed.
    assert "NEXT STEPS: add a next step only when" in system


def test_single_marker_prompt_is_narrow_and_has_no_forced_next_step():
    _ctx, _system, user = _prompt("What does my HbA1c mean?")
    assert "Do not review other results or the whole report" in user
    assert "End with one short next step" not in user
    assert "as long as the important findings need" not in user  # "explain my X" is not a full review


def test_whole_bio_ai_prompt_has_no_word_band_or_forced_bullets():
    _ctx, _system, user = _prompt("Explain my Bio-AI report")
    assert "100 to 160 words" not in user
    assert "3 to 5 plain bullets" not in user
    assert "overall picture first" in user


def test_safety_rules_are_kept():
    _ctx, system, _user = _prompt("Explain my Bio-AI report")
    for rule in (
        "BIO_AI_ASSESSMENT is an assessment, not a diagnosis",
        "QUESTIONNAIRE_RESPONSE and USER_STATED_HEALTH_INFORMATION are user-reported context",
        "that range decides low, normal, or high",
        "Do not diagnose, prescribe medication, recommend dose changes",
        "If SOURCE CONFLICTS exist",
        "Never invent values",
    ):
        assert rule in system


def test_urgent_question_puts_safety_first():
    _ctx, _system, user = _prompt("I have chest pain and my LDL is high, what should I do?")
    assert "The first sentence is the safety action" in user
    assert "First sentence is the immediate safety action" in user


def test_skipped_abnormal_value_is_said_as_a_sentence_not_a_raw_dump():
    presentation = StructuredResponse(
        mode=ResponseMode.interpretation,
        summary="Your blood sugar control has been higher than ideal over the last few months.",
        findings=[PresentedFinding(label="HbA1c", value="9.1", unit="%", status="high")],
    )
    text = flatten_structured_response(presentation)
    assert "Stored records" not in text
    assert text.startswith("Your blood sugar control")  # the explanation leads
    assert "HbA1c 9.1 %" in text  # the abnormal value is still never hidden


def test_bio_ai_score_note_only_adds_relevant_scores():
    ctx = _context("Explain my Bio-AI report")  # loads every Bio-AI score
    ctx.requested_entity_codes = ["dyslipidemia"]
    note = _missing_score_note("What does my Bio-AI dyslipidemia score mean?", ctx, "It is a risk estimate.")
    assert "Stored scores" not in note
    assert "Dyslipidemia" in note
    assert "Cardiac" not in note and "Thyroid" not in note
    assert "These are risk estimates" not in note  # the answer already says it


def test_whole_report_score_note_skips_reassuring_scores():
    ctx = _context("Explain my Bio-AI report")
    note = _missing_score_note("Explain my Bio-AI report", ctx, "")
    assert "Thyroid" not in note  # low band: reassuring, not worth a raw line
    assert "Dyslipidemia" in note
