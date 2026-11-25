import pytest

from app.pipeline.prompt_modules import is_lifestyle_topic_question, RESULT_WALKTHROUGH, LIFESTYLE_FOCUS


@pytest.mark.parametrize("message", [
    "What does my sleep pattern say about my health?",
    "How is my stress affecting my health?",
    "Is my exercise routine enough?",
])
def test_habit_questions_are_lifestyle_focused(message):
    assert is_lifestyle_topic_question(message)


@pytest.mark.parametrize("message", [
    "Does my sleep explain my low vitamin D?",
    "What does my Alkaline Phosphatase result mean?",
    "Explain my blood report",
    "How does stress change my Bio-AI score?",
    "Is my exercise routine why my cholesterol is high?",
])
def test_lab_questions_are_not_lifestyle_focused(message):
    assert not is_lifestyle_topic_question(message)


def test_walkthrough_is_flexible_and_not_a_fixed_six_part_template():
    for rigid in ("What the test is", "How far outside", "Should you worry"):
        assert rigid not in RESULT_WALKTHROUGH
    assert "Answer the exact question asked" in RESULT_WALKTHROUGH
    assert "sections_already_shown" in RESULT_WALKTHROUGH
    assert "—" not in RESULT_WALKTHROUGH and "–" not in RESULT_WALKTHROUGH and "—" not in LIFESTYLE_FOCUS


def test_food_follow_up_does_not_get_the_result_walkthrough():
    from types import SimpleNamespace
    from app.pipeline.prompt_modules import is_result_walkthrough

    ctx = SimpleNamespace(task_contract={"response_type": "MARKER_LOOKUP", "goal": "interpret"}, intent=SimpleNamespace(value="blood_marker_explanation"), markers=[object()])
    assert is_result_walkthrough(ctx, "What does my Urea result mean?")
    assert not is_result_walkthrough(ctx, "Which protein foods fit my usual vegetarian meals to raise urea?")
    assert not is_result_walkthrough(ctx, "How can I improve my vitamin D?")


def test_marker_after_my_must_be_what_my_points_at():
    from app.pipeline.task_contract import _names_own_marker

    assert _names_own_marker("What does my Urea result mean?")
    assert _names_own_marker("is my cholestrol normal?")
    assert not _names_own_marker("Which protein foods fit my usual vegetarian meals to raise urea?")
    assert not _names_own_marker("What does cholesterol do in my body?")


def test_praise_opener_and_bullet_labels_are_removed_but_bold_labels_and_values_stay():
    from app.pipeline.markdown_tidy import drop_bullet_labels, drop_praise_opener

    text = "Thanks, great question about foods you can use.\n\n- Worry level: usually low.\n- One simple step: add dal.\n- **What to do first:** walk daily.\n- Urea: 16.7 mg/dL is a bit low."
    out = drop_bullet_labels(drop_praise_opener(text))
    assert out.startswith("- Usually low.")
    assert "- Add dal." in out
    assert "**What to do first:** walk daily." in out
    assert "- Urea: 16.7 mg/dL" in out


def test_dashes_empty_bullets_and_blank_lines_between_bullets_are_cleaned():
    from app.pipeline.markdown_tidy import clean_bullet_runs, drop_dashes

    assert drop_dashes("Vitamin D\u2013rich foods, range 43\u2013115, and so \u2014 yes") == "Vitamin D-rich foods, range 43 to 115, and so, yes"
    assert clean_bullet_runs("Intro\n\n-\n\n## Heart\n\n- a\n\n- b") == "Intro\n\n## Heart\n\n- a\n- b"


def test_diagnosis_reply_never_promises_results_it_does_not_show():
    from types import SimpleNamespace

    from app.pipeline.renderer import render_diagnosis_restraint

    ctx = SimpleNamespace(markers=[], requested_entity_codes=[], bio_ai_risks=[])
    out = render_diagnosis_restraint(ctx)
    assert "Here is what your results show" not in out and "Tell me which result" in out
