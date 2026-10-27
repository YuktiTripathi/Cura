"""Reported answer-quality failures: safety routing, one referral, report shape, chips, cards."""

from datetime import datetime

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, MarkerFlag as F
from app.contracts.health_context import HealthContext
from app.pipeline.answer_polish import polish_answer
from app.pipeline.followup_generator import is_member_question
from app.pipeline.presentation import _finding_from_marker
from app.pipeline.prompt_builder import GENERAL_HEALTH_INSTRUCTIONS, SAFETY_INSTRUCTIONS, _system_for_mode
from app.pipeline.report_explainer import explain_blood_report, related_blood_results
from app.pipeline.safety import SafetyLayer, lab_preparation_question, match_safety_category
from app.pipeline.safety_classifier import SafetyClassification


class _MedClassifier:
    def classify(self, text: str) -> SafetyClassification:
        return SafetyClassification("medication_misuse", "medium", 0.95, "en", "refuse")


def _marker(name, key, value, unit, flag):
    return BloodMarker(
        id=key, key=key, name=name, value=value, unit=unit, flag=flag, measured_at=datetime(2026, 8, 8)
    )


def test_fasting_lipid_question_is_not_a_medication_refusal():
    question = "Should I have this lipid test repeated fasting?"
    assert lab_preparation_question(question)
    assert match_safety_category(question)[0] == ""
    decision = SafetyLayer(classifier=_MedClassifier()).check_input(question)
    assert not decision.blocked
    assert "medication doses" not in (decision.answer or "")


def test_stopping_a_statin_is_still_refused():
    question = "Should I stop my statin?"
    assert match_safety_category(question)[0] == "medication_misuse"
    decision = SafetyLayer(classifier=_MedClassifier()).check_input(question)
    assert decision.blocked
    assert "medication" in (decision.answer or "").lower()


def test_high_hba1c_advice_is_not_repeated():
    marker = _marker("HbA1c", "hba1c", 9.1, "%", F.high)
    context = HealthContext(intent=IntentType.blood_marker_explanation, answer_depth=AnswerDepth.simple, markers=[marker])
    already = "Your HbA1c is 9.1%, which is high. Please talk with your doctor about it."
    out = polish_answer(already, context)
    assert out.lower().count("doctor") == 1
    assert "**Important:**" not in out


def test_urgent_hba1c_note_is_added_once_when_the_answer_omits_it():
    marker = _marker("HbA1c", "hba1c", 9.1, "%", F.high)
    context = HealthContext(intent=IntentType.blood_marker_explanation, answer_depth=AnswerDepth.simple, markers=[marker])
    out = polish_answer("HbA1c reflects your average blood sugar.", context)
    assert out.count("doctor") == 1
    assert "6.5%" in out


def test_urgent_report_mentions_medical_review_once():
    markers = [
        _marker("HbA1c", "hba1c", 9.1, "%", F.high),
        _marker("LDL", "ldl", 162, "mg/dl", F.high),
    ]
    text = explain_blood_report(markers, in_range=8, out_of_range=2)
    assert text.lower().count("discuss this result with your doctor") == 1
    assert "6.5%" in text
    assert "What to do next" not in text


def test_complete_blood_report_groups_findings_and_skips_routine_referral():
    markers = [
        _marker("Sodium", "sodium", 140, "mmol/L", F.normal),
        _marker("LDL", "ldl", 128, "mg/dl", F.high),
        _marker("HDL", "hdl", 38, "mg/dl", F.low),
        _marker("Triglycerides", "triglycerides", 220, "mg/dl", F.high),
        _marker("Chloride", "chloride", 99, "mmol/L", F.low),
    ]
    text = explain_blood_report(markers, in_range=20, out_of_range=4)
    assert "Cholesterol and blood fats" in text or "blood fats" in text.lower()
    assert "Sodium" not in text
    assert "What to do next" not in text


def test_bio_ai_pcos_does_not_pull_cholesterol():
    risk = BioAIRisk(code="pcos", name="PCOS", score=61, status="High")
    markers = [_marker("LDL", "ldl", 160, "mg/dl", F.high), _marker("HbA1c", "hba1c", 6.2, "%", F.high)]
    assert related_blood_results(risk, markers) == []


def test_stock_summary_and_missing_bio_line_are_removed():
    text = (
        "Here is a short plain summary of your blood report and what the main results mean.\n"
        "- Cut sugary drinks first.\n"
        "- Bio-AI risk data is not present in your report, so these are the measured blood results only."
    )
    out = polish_answer(text, HealthContext(intent=IntentType.blood_marker_explanation, answer_depth=AnswerDepth.simple))
    assert "short plain summary" not in out.lower()
    assert "not present" not in out.lower()
    assert "sugary drinks" in out


def test_food_question_is_told_to_name_foods_first():
    from app.pipeline.prompt_builder import _asked_task

    line = _asked_task("Which foods should I cut first to lower my LDL and triglycerides?")
    assert "foods to cut or eat" in line
    assert "doctor visit" in line


def test_generic_topic_chip_is_rejected():
    assert not is_member_question("What does this topic mean in general?")
    assert is_member_question("Which foods should I cut back on?")


def test_bio_qualifier_is_kept_once_at_the_end():
    text = (
        "These are risk estimates, not diagnoses.\n"
        "- Type 2 diabetes is high.\n"
        "These are risk estimates, not diagnoses."
    )
    out = polish_answer(text, HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=AnswerDepth.simple))
    assert out.lower().count("risk estimates, not diagnoses") == 1
    assert out.rstrip().lower().endswith("risk estimates, not diagnoses.")


def test_follow_up_chips_are_questions_the_member_would_ask():
    assert not is_member_question("Do you have any new symptoms or medication or supplement changes?")
    assert is_member_question("Could new symptoms or a medicine change affect this result?")
    assert is_member_question("Why is my HbA1c high?")


def test_lab_card_keeps_its_date():
    finding = _finding_from_marker(_marker("HbA1c", "hba1c", 9.1, "%", F.high))
    assert finding.source_date == "2026-08-08"
    assert finding.value == "9.1"


def test_personal_and_general_prompts_keep_the_same_json_contract():
    personal = _system_for_mode(SAFETY_INSTRUCTIONS)
    for field in ("answer", "claims", "recommendation_candidates", "follow_up_questions", "safety_flags", "escalation"):
        assert field in personal
        assert field in GENERAL_HEALTH_INSTRUCTIONS
    assert personal == _system_for_mode(SAFETY_INSTRUCTIONS)
