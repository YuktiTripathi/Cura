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


def test_a_definition_does_not_carry_personal_cards():
    from app.pipeline.presentation import _visible_markers
    from app.pipeline.query_planner import build_query_plan

    plan = build_query_plan("What is insulin resistance?")
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        markers=[BloodMarker(id="1", key="hba1c", name="HbA1c", value=9.1, unit="%", flag=F.high)],
    )
    assert (plan.task_contract or {}).get("goal") == "explain"
    assert _visible_markers(plan, context) == []
    fats = build_query_plan("How can I lower my triglycerides?")
    assert fats.task_contract["card_keys"] == ["triglycerides"]


def test_incomplete_tail_is_dropped_when_earlier_lines_are_complete():
    from app.pipeline.reasoning import trim_incomplete_tail

    text = "- Your score is 71, which is high.\n- Dyslipidemia estimates how likely your"
    assert trim_incomplete_tail(text).rstrip().endswith("high.")
    assert "how likely your" not in trim_incomplete_tail(text)
    assert trim_incomplete_tail("- Dyslipidemia estimates how likely your") == "- Dyslipidemia estimates how likely your"


def test_a_single_result_question_does_not_carry_the_whole_panel():
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag
    from app.pipeline.prompt_builder import _relevant_markers
    from app.pipeline.query_planner import build_query_plan

    plan = build_query_plan("What does my Iron Serum result mean?")
    iron = BloodMarker(id="1", key="iron", name="Iron", value=35, unit="µg/dL", flag=MarkerFlag.low)
    ferritin = BloodMarker(id="2", key="ferritin", name="Ferritin", value=8, unit="ng/mL", flag=MarkerFlag.low)
    ctx = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        markers=[iron, ferritin],
        task_contract=plan.task_contract,
    )
    keys = [_topic_key(marker.key) for marker in _relevant_markers(ctx)]
    assert keys == ["iron"]


def _topic_key(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def test_bio_score_does_not_become_a_timed_certainty():
    from app.contracts.query import QueryPlan
    from app.pipeline.clinical_postcheck import review_clinical_output

    ctx = HealthContext(
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        bio_ai_risks=[BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=71, status="high")],
    )
    plan = QueryPlan(intent=IntentType.bio_ai_score, raw_message="What does my Dyslipidemia score mean?")
    out, flags = review_clinical_output(
        "Your Dyslipidemia score is 71, high. You will develop heart disease within the next 5 years.",
        plan=plan,
        context=ctx,
    )
    assert "bio_ai_time_horizon" in flags
    assert "bio_ai_outcome_certainty" in flags
    assert "71" in out
    assert "high" in out.lower()
    assert "next 5 years" not in out
    assert "you will develop" not in out.lower()


def test_bio_score_is_not_rewritten_into_a_disease_probability():
    from app.contracts.query import QueryPlan
    from app.pipeline.clinical_postcheck import review_clinical_output

    ctx = HealthContext(
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        bio_ai_risks=[BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=71, status="high")],
    )
    plan = QueryPlan(intent=IntentType.bio_ai_score, raw_message="What does my Dyslipidemia score mean?")
    out, flags = review_clinical_output(
        "Your Dyslipidemia score of 71 means a 71% chance of developing heart disease. Your HbA1c is 9.1%.",
        plan=plan,
        context=ctx,
    )
    assert "bio_ai_score_as_probability" in flags
    assert "71% chance" not in out
    assert "9.1%" in out
    assert "risk estimate" in out.lower()
    chance, chance_flags = review_clinical_output(
        "This score estimates your chance of having unhealthy blood fats. Your HbA1c is 9.1%.",
        plan=plan,
        context=ctx,
    )
    assert "bio_ai_chance_as_probability" in chance_flags
    assert "estimates your chance" not in chance
    assert "9.1%" in chance

    from app.contracts.common import KnowledgeScope
    from app.contracts.presentation import ResponseMode
    from app.contracts.query import QueryPlan
    from app.pipeline.presentation import _headline

    plan = QueryPlan(
        intent=IntentType.trend,
        raw_message="Has my alkaline phosphatase changed since my last report?",
        domains=["red_cell_anaemia_health"],
        knowledge_scope=KnowledgeScope.personal,
    )
    context = HealthContext(intent=IntentType.trend, answer_depth=AnswerDepth.simple)
    heading = _headline(plan, context, ResponseMode.trend)
    assert "anaemia" not in heading.lower()
    assert "alkaline" in heading.lower()
    assert "trend" in heading.lower()

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
