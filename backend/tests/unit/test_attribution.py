"""Biomarker, unit, date, trend, Bio-AI, and BMI attribution."""

from datetime import date

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, MarkerFlag
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.health_context import Comparison, HealthContext
from app.pipeline.clinical_postcheck import drop_unsupported_trends
from app.pipeline.grounding import GroundingChecker
from app.pipeline.trend_engine import comparison


def _ctx(**kwargs) -> HealthContext:
    return HealthContext(intent=IntentType.latest_result, answer_depth=AnswerDepth.simple, **kwargs)


def _hba1c(**kwargs) -> BloodMarker:
    base = dict(id="1", key="hba1c", name="HbA1c", value=9.1, unit="%", reference_low=4.0, reference_high=5.6, flag=MarkerFlag.high, measured_at=date(2026, 9, 6), report_id="r1")
    base.update(kwargs)
    return BloodMarker(**base)


def test_same_number_on_the_wrong_biomarker_is_rejected():
    ctx = _ctx(markers=[_hba1c(), BloodMarker(id="2", key="glucose", name="Glucose", value=214, unit="mg/dl", flag=MarkerFlag.high)])
    issues = GroundingChecker().unsupported_number_sentences("Your HbA1c is 214%.", ctx)
    assert issues and issues[0][1] == "214"


def test_correct_value_with_the_wrong_unit_is_rejected():
    ctx = _ctx(markers=[_hba1c()])
    assert GroundingChecker().unsupported_number_sentences("Your HbA1c is 9.1 mg/dl.", ctx)


def test_value_from_the_wrong_report_date_is_rejected():
    ctx = _ctx(markers=[_hba1c()])
    assert GroundingChecker().unsupported_number_sentences("Your HbA1c is 9.1% on 01 Jan 2020.", ctx)


def test_valid_current_measurement_is_kept():
    ctx = _ctx(markers=[_hba1c()])
    assert GroundingChecker().unsupported_number_sentences("Your HbA1c is 9.1% on 2026-09-06.", ctx) == []


def test_reference_range_is_not_a_personal_result_and_a_general_range_is_kept():
    ctx = _ctx(markers=[_hba1c()])
    checker = GroundingChecker()
    assert checker.unsupported_number_sentences("Your HbA1c report range is 4.0 to 5.6.", ctx) == []
    assert checker.unsupported_number_sentences("A typical HbA1c range is 4 to 6.", ctx) == []
    assert checker.unsupported_number_sentences("Your HbA1c is 5.6%.", ctx)


def test_missing_history_blocks_a_newly_abnormal_claim():
    ctx = _ctx(markers=[_hba1c()])
    revised, flags = drop_unsupported_trends("Your HbA1c is newly abnormal.", ctx)
    assert "unsupported_trend_removed" in flags
    assert "newly abnormal" not in revised.lower()


def test_deterministic_increase_is_kept():
    ctx = _ctx(
        markers=[_hba1c()],
        comparisons=[comparison("hba1c", 8.0, 9.1, previous_date=date(2026, 8, 1), current_date=date(2026, 9, 6))],
    )
    revised, flags = drop_unsupported_trends("Your HbA1c increased.", ctx)
    assert flags == []
    assert "increased" in revised.lower()


def test_missing_bio_ai_score_is_rejected_and_the_right_score_is_kept():
    ctx = _ctx(bio_ai_risks=[BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=19, status="Healthy")])
    checker = GroundingChecker()
    assert checker.unsupported_number_sentences("Your NAFLD score is 40.", ctx)
    assert checker.unsupported_number_sentences("Your type 2 diabetes score is 19.", ctx) == []


def test_bmi_without_height_and_weight_is_rejected():
    ctx = _ctx()
    assert GroundingChecker().unsupported_number_sentences("Your BMI is 26.5 kg/m2.", ctx)


def test_stored_bmi_is_kept():
    ctx = _ctx(derived=[ProvenancedFact(fact="bmi", value=26.5, unit="kg/m2", source="derived", source_type="derived", fact_type=FactKind.measured_personal_fact)])
    assert GroundingChecker().unsupported_number_sentences("Your BMI is 26.5 kg/m2.", ctx) == []


def test_older_report_value_is_not_a_current_result():
    from app.pipeline.clinician_handoff import build_clinician_handoff, format_handoff
    from app.pipeline.clinical_postcheck import correct_false_absence
    from app.pipeline.grounding import drop_unverified_claims

    older = BloodMarker(id="old", key="hba1c", name="HbA1c", value=6.2, unit="%", flag=MarkerFlag.high, measured_at=date(2026, 9, 3), report_id="old")
    current = BloodMarker(id="new", key="triglycerides", name="Triglycerides", value=180, unit="mg/dl", flag=MarkerFlag.high, measured_at=date(2026, 9, 6), report_id="new")
    crp = BloodMarker(id="crp", key="crp", name="HS-CRP", value=2.1, unit="mg/L", flag=MarkerFlag.high, measured_at=date(2026, 9, 6), report_id="new")
    ctx = _ctx(markers=[older, current, crp], panel_markers=[current, crp])
    assert GroundingChecker().unsupported_number_sentences("Your HbA1c is 6.2%.", ctx)
    assert GroundingChecker().unsupported_number_sentences("Your HbA1c is 6.2% on 2026-09-03.", ctx) == []
    handoff = format_handoff(build_clinician_handoff(ctx))
    assert "hba1c" not in handoff.lower()
    assert "triglycerides" in handoff.lower()
    revised, flags = correct_false_absence("HS-CRP was not measured.", ctx)
    assert "false_absence_corrected" in flags
    assert "2.1" in revised
    visible = drop_unverified_claims("Your average glucose is 131.24 mg/dl.\nYour triglycerides are 180 mg/dl.", ctx)
    assert "131.24" not in visible
    assert "180" in visible


def test_educational_number_is_not_a_personal_claim():
    ctx = _ctx(markers=[_hba1c()])
    text = "Many adults walk 30 minutes a day. A typical fasting glucose discussion uses 70-100 mg/dl as a general range."
    assert GroundingChecker().unsupported_number_sentences(text, ctx) == []


def test_verified_value_survives_the_same_clause_as_an_unsupported_value():
    from app.pipeline.grounding import drop_unverified_claims

    line = "Your HbA1c is 9.1% with glucose 300 mg/dl."
    visible = drop_unverified_claims(line, _ctx(markers=[_hba1c()]))
    assert "9.1" in visible
    assert "300" not in visible


def test_verified_value_stays_when_the_same_sentence_has_an_unsupported_value():
    from app.pipeline.grounding import drop_unverified_claims

    line = "Your HbA1c is 9.1% and your glucose is 300 mg/dl."
    visible = drop_unverified_claims(line, _ctx(markers=[_hba1c()]))
    assert "9.1" in visible
    assert "300" not in visible


def test_a_true_result_is_kept_when_another_number_in_the_line_is_not():
    from app.pipeline.grounding import drop_unverified_claims

    marker = BloodMarker(
        id="alp", key="alkaline_phosphatase", name="Alkaline phosphatase",
        value=148, unit="U/L", reference_low=44, reference_high=147, flag=MarkerFlag.high,
    )
    ctx = _ctx(markers=[marker])
    line = "Your alkaline phosphatase is 148 U/L, just above a general cutoff of 120."
    assert "148" in drop_unverified_claims(line, ctx)
