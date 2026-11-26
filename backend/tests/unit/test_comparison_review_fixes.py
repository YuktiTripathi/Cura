"""Fixes from the 70 question live comparison: wrong facts, leaked names, repeated tics, one wording per gap."""

from types import SimpleNamespace as N

import pytest
from fastapi.testclient import TestClient

from app.contracts.common import AnswerDepth, IntentType
from app.contracts.health_context import HealthContext
from app.main import app
from app.pipeline.answer_consistency import (
    blood_half_for_ambiguity,
    collapse_referrals,
    drop_label_echo,
    drop_stock_closer,
    fix_bio_ai_counts,
)
from app.pipeline.evidence_inventory import _expand_family_keys, _measurement, classify_marker_trends
from app.pipeline.gap_words import how_far
from app.pipeline.lab_parameters import retrieval_keys
from app.pipeline.presentation import sanitize_internal_ids
from app.pipeline.safety import MEDICATION_MISUSE
from app.pipeline.topic_risk import high_risk_topics

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def chat(message: str, conversation_id: str | None = None):
    return client.post("/api/v1/chat", headers=H, json={"message": message, "conversation_id": conversation_id}).json()


def _marker(key, value, low, high, unit="mg/dL", name=None):
    return N(key=key, name=name or key, value=value, reference_low=low, reference_high=high, unit=unit, measured_at=None, flag=None)


# ---- Bio-AI counts are the report's own ----

def _bio(statuses):
    return N(bio_ai_risks=[N(status=s) for s in statuses])


@pytest.mark.parametrize(
    "text",
    [
        "Your report has 8 assessment areas and 7 are raised.",
        "Your report covers 8 assessment areas, with 7 raised.",
        "It looked at 8 areas and 7 were raised.",
    ],
)
def test_bio_ai_area_counts_follow_the_report(text):
    fixed = fix_bio_ai_counts(text, _bio(["elevated", "elevated", "moderate", "moderate", "moderate", "low", "low", "low"]))
    assert "8" in fixed and "5" in fixed and "7" not in fixed


def test_a_correct_count_is_left_alone():
    text = "Your report covers 8 assessment areas, with 5 raised."
    assert fix_bio_ai_counts(text, _bio(["elevated"] * 5 + ["low"] * 3)) == text


def test_no_bio_ai_data_means_no_change():
    assert fix_bio_ai_counts("8 areas and 7 were raised", N(bio_ai_risks=[])) == "8 areas and 7 were raised"


# ---- "my sugar", "my kidney" name a group ----

def test_a_generic_sugar_question_reaches_the_fasting_result():
    held = [_marker("fasting_blood_glucose", 102, 70, 99)]
    assert _expand_family_keys(["glucose"], held) == ["fasting_blood_glucose"]
    assert "fasting_blood_glucose" in retrieval_keys("glucose")


def test_a_group_name_becomes_the_results_the_report_holds():
    held = [_marker("creatinine", 0.92, 0.6, 1.3), _marker("egfr", 98, 90, 120)]
    assert _expand_family_keys(["kidney_function"], held) == ["creatinine", "egfr"]
    assert _expand_family_keys(["kidney_function"], []) == ["kidney_function"]


def test_group_names_are_not_reported_missing_when_a_member_is_held():
    held = [_marker("creatinine", 0.92, 0.6, 1.3)]
    assert classify_marker_trends("What about my kidney?", held, [])["missing"] == []


def test_insulin_as_a_test_is_not_a_medication_question():
    assert high_risk_topics("Compare my sugar and insulin") == []
    assert high_risk_topics("Is my insulin level normal?") == []
    assert "medication" in high_risk_topics("Can I take insulin with food")
    assert "medication" in high_risk_topics("how many units of insulin should I inject")


def test_medicine_safety_questions_get_one_fixed_reply():
    assert any(p.search("Is paracetamol safe with an empty stomach?") for p in MEDICATION_MISUSE)
    assert not any(p.search("What is my vitamin D?") for p in MEDICATION_MISUSE)
    reply = chat("Is paracetamol safe with an empty stomach?")["answer"]
    assert "can't advise on medication" in reply


def test_kidney_question_uses_the_creatinine_on_the_report():
    answer = chat("What about my kidney?")["answer"]
    assert "I don't see Kidney function" not in answer


def test_sugar_and_insulin_question_is_not_a_medicine_refusal():
    answer = chat("Compare my sugar and insulin")["answer"]
    assert "reviewed source" not in answer and "medication called" not in answer


# ---- leaked names ----

def test_internal_source_and_field_names_never_reach_the_person():
    out = sanitize_internal_ids(
        "Reported on 18 Aug 2026 from your blood_report. Source: your blood_report.\n"
        "Your report does not include thyroid_function."
    )
    assert "blood_report" not in out and "thyroid_function" not in out and "Source:" not in out
    assert "thyroid function" in out


# ---- one wording per gap ----

@pytest.mark.parametrize(
    "value,low,high,word",
    [(138, 0, 100, "moderately"), (155, 0, 150, "slightly"), (12.6, 30, 100, "clearly"), (154, 200, 900, "moderately"), (41, 40, 60, None)],
)
def test_the_same_gap_always_gets_the_same_word(value, low, high, word):
    assert how_far(value, low, high) == word


def test_the_word_travels_with_the_evidence():
    # Distance-from-range labels are not a biomarker-specific clinical basis, so they stay out of model evidence.
    assert "how_far" not in _measurement(_marker("ldl", 138, 0, 100))
    assert "how_far" not in _measurement(_marker("hdl", 41, 40, 60))


# ---- the stock closing line, repeated referral, echoed names ----

def test_the_stock_closing_line_is_dropped_but_advice_stays():
    out = drop_stock_closer("Swap fried snacks for chana.\n- Walk daily. Small, steady steps add up.\nSmall steady changes can add up.")
    assert "steady" not in out.lower() and "Swap fried snacks for chana." in out and "Walk daily." in out


def test_a_short_answer_asks_for_a_doctor_once():
    out = collapse_referrals(
        "Your Vitamin D is low.\n- Please show this result to a doctor.\n- Arrange a doctor visit soon and show it."
    )
    assert out.lower().count("doctor") == 1


def test_a_long_answer_with_sections_keeps_each_referral():
    text = "## Vitamins\n- Discuss low D with a doctor.\n## Heart\n- Discuss LDL with a doctor."
    assert collapse_referrals(text) == text


def test_the_name_is_not_said_twice():
    assert drop_label_echo("Your creatinine is **Creatinine: 0.92 mg/dL**, within range.") == "Your creatinine is **0.92 mg/dL**, within range."
    assert drop_label_echo("**LDL: 138 mg/dL** is high.") == "**LDL: 138 mg/dL** is high."


# ---- ask which Bio-AI report, but say what the blood report shows first ----

def test_blood_half_lists_the_biggest_gaps_first():
    ctx = N(markers=[_marker("ldl", 138, 0, 100, name="LDL"), _marker("vitamin_d", 12.6, 30, 100, "ng/mL", "Vitamin D"), _marker("hdl", 41, 40, 60, name="HDL")])
    text = blood_half_for_ambiguity(ctx)
    assert text.index("Vitamin D") < text.index("LDL") and "HDL" not in text


def test_blood_half_is_empty_when_everything_is_in_range():
    assert blood_half_for_ambiguity(N(markers=[_marker("hdl", 41, 40, 60)])) == ""


def test_mixed_blood_and_bio_ai_question_gets_blood_first_then_the_question():
    answer = chat("What should I focus on first from my blood and Bio-AI reports?")["answer"]
    assert "Vitamin D" in answer and "Which report would you like me to use?" in answer
    assert "For the Bio-AI side, I found" in answer

