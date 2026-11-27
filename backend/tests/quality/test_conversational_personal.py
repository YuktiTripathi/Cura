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


_BOUNDARY_SCOPES = {"urgent", "cross_source"}


@pytest.mark.parametrize("message,scope", CASES)
def test_only_safety_and_source_boundaries_are_stated_as_scope(message, scope):
    """Answer shape is the model's choice; only urgent and cross-source boundaries remain in the prompt."""
    for package in (False, True):
        ctx, _system, user = _prompt(message, package=package)
        if ctx.knowledge_scope.value != "personal":
            pytest.skip("general branch")
        assert ("QUESTION SCOPE:" in user) == (scope in _BOUNDARY_SCOPES)


def test_active_defaults_use_the_cura_conversational_prompt():
    assert settings.cura_prompt_variant == "legacy"
    assert settings.answer_prompt_compact is False
    _ctx, system, _user = _prompt("What does my HbA1c mean?")
    assert system.startswith(SAFETY_INSTRUCTIONS.split("\n")[0])
    assert system.startswith("CURA: Conversational Behaviour")
    assert "You are CURA, a personal health companion within SuperShyft." in system


def test_system_prompt_carries_no_fixed_answer_shape():
    _ctx, system, _user = _prompt("Explain my complete blood report")
    lowered = system.lower()
    for shape in ("150 words", "60 words", "3 to 5 bullets", "3 to 5 grouped", "2 to 3 bullets", "the whole answer is bullets", "format (always"):
        assert shape not in lowered
    if settings.cura_prompt_variant == "house":
        assert "avoid unnecessary headings" in lowered
    else:
        assert "a simple question gets a simple answer" in lowered


def test_single_marker_prompt_prescribes_no_scope_length_or_next_step():
    _ctx, _system, user = _prompt("What does my HbA1c mean?")
    for phrase in ("No other results", "NARRATIVE LENGTH", "PRESENTATION:", "RESPONSE BRIEF", "bullets"):
        assert phrase not in user


def test_whole_bio_ai_prompt_has_no_word_band_or_forced_bullets():
    _ctx, _system, user = _prompt("Explain my Bio-AI report")
    assert "100 to 160 words" not in user
    assert "3 to 5 plain bullets" not in user
    assert "One-line overall picture" not in user


def test_safety_rules_are_kept():
    _ctx, system, _user = _prompt("Explain my Bio-AI report")
    lowered = system.lower()
    for rule in (
        "bio-ai items are risk estimates, not diagnoses",
        "questionnaire answers are self-reported",
        "reference range printed on the person's own report",
        "do not diagnose or prescribe",
        "never merge conflicting sources",
        "personal facts come only from the supplied context",
        "a predicted risk is not a diagnosis",
    ):
        assert rule in lowered


def test_urgent_question_puts_safety_first():
    _ctx, system, user = _prompt("I have chest pain and my LDL is high, what should I do?")
    assert "The first sentence is the safety action" in user
    assert "red-flag symptoms" in system


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
    assert note == ""  # a whole-report answer is not extended with a dump of stored scores
