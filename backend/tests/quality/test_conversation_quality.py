"""Answer-quality checks on the mock members. The model is off (tests/conftest.py), so
these cover the deterministic answers members get whenever the model is unavailable."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
U1, U2, IRON = "demo-user-001", "demo-user-002", "eval-user-iron"


def ask(user, message, conversation_id=None):
    body = {"message": message, **({"conversation_id": conversation_id} if conversation_id else {})}
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": user}, json=body).json()


def answer(user, message, conversation_id=None):
    return ask(user, message, conversation_id)["answer"]


def test_report_choice_reply_answers_the_original_question():
    first = ask(U1, "Which of my Bio-AI scores deserve attention?")
    assert "Which report" in first["answer"]
    second = answer(U1, "The advanced one", first["conversation_id"])
    assert "general medical knowledge service" not in second
    assert "deserve the most attention" in second


def test_iron_deficiency_question_reads_the_whole_pattern():
    text = answer(IRON, "Am I iron deficient?")
    assert "Haemoglobin" in text and "MCV" in text
    assert "iron-deficiency" in text
    assert "settle on their own" not in text


@pytest.mark.parametrize("question", ["my vitamin d", "Meri vitamin D report kaisi hai?"])
def test_short_lookup_keeps_the_flag_and_warning(question):
    text = answer(U1, question)
    assert "12.6" in text
    assert "low" in text.lower()
    assert "deficient" in text


def test_food_question_gets_food_advice():
    text = answer(U1, "What foods can help my vitamin D?").lower()
    assert "12.6" in text
    assert any(food in text for food in ("egg", "fish", "fortified", "mushroom"))
    assert "sunlight" in text


def test_supplement_question_is_referred_not_ignored():
    text = answer(IRON, "Should I take iron supplements?").lower()
    assert "doctor" in text
    assert "iron" in text
    assert "settle on their own" not in text


def test_what_can_i_do_follow_up_gives_steps():
    first = ask(U1, "What is my LDL?")
    text = answer(U1, "What can I do about it?", first["conversation_id"]).lower()
    assert "138" in text
    assert any(step in text for step in ("fibre", "fiber", "saturated", "exercise", "activity", "walk"))


def test_why_low_gives_common_causes():
    text = answer(U1, "Why is my vitamin D low?").lower()
    assert "sun" in text
    assert any(word in text for word in ("common", "causes", "reasons"))


def test_sugar_question_stays_on_blood_sugar():
    text = answer(U1, "Is my sugar ok?")
    assert "Triglycerides" not in text
    assert "isn't included" not in text
    assert "102" in text and "5.5" in text


def test_triglycerides_question_stays_on_triglycerides():
    text = answer(U1, "What does high triglycerides mean for me?")
    assert "155" in text
    assert "Glucose" not in text


def test_requested_date_that_has_no_report_is_said_plainly():
    text = answer(U1, "What is my HbA1c on 2020-01-01?")
    assert "2020" in text
    assert "Stored results for the requested dates" not in text


def test_most_important_result_names_one():
    text = answer(U1, "Which result is the most important?")
    assert text.count("**") <= 4
    assert "most important" in text.lower()


def test_kidney_question_is_explained():
    text = answer(U1, "How are my kidneys?")
    assert "was not found" not in text
    assert "eGFR" in text and "filter" in text


def test_cholesterol_ratio_is_calculated():
    text = answer(U1, "What's my cholesterol ratio?")
    assert "3.4" in text  # LDL 138 / HDL 41
    assert "was not in reports" not in text


def test_bio_ai_improved_does_not_lead_with_blood_changes():
    text = answer(U1, "Has my Bio-AI score improved?")
    assert not text.startswith("Since your previous report")


def test_missing_test_name_is_readable():
    assert "PSA" in answer(U1, "What is my PSA?")


def test_how_can_i_lower_my_test_is_personal():
    text = answer(U1, "How can I lower my LDL?")
    assert "138" in text and "knowledge service" not in text
    assert "walking" in text


def test_improve_results_is_not_matched_on_letters_inside_words():
    # "should" contains "tsh"; the answer must not be about TSH alone.
    text = answer(U1, "What should I do to improve my results?")
    assert "Vitamin D" in text and "LDL" in text


def test_most_important_puts_blood_sugar_first():
    assert answer(U1, "Which result is the most important?").startswith(
        "The most important result to look at is your Fasting Blood Glucose"
    )
