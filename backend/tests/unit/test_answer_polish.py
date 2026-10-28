from app.contracts.bio_ai import BioAIRisk
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.pipeline.answer_polish import polish_answer


def _ctx(intent=IntentType.report_explanation, risks=()):
    return HealthContext(intent=intent, answer_depth=AnswerDepth.simple,
                         knowledge_scope=KnowledgeScope.personal, bio_ai_risks=list(risks))


def test_lab_answer_never_calls_results_risk_estimates():
    out = polish_answer("Your Hba1c is high. This is a risk estimate, not a diagnosis.", _ctx(), intent="report_explanation")
    assert "HbA1c" in out
    assert "risk estimate" not in out
    assert "reading of your results, not a diagnosis" in out


def test_qualifier_appears_once():
    text = ("Scores point to blood fats. These are risk estimates, not diagnoses.\n"
            "- Hypertension looks fine. These are risk estimates, not diagnoses.")
    assert polish_answer(text, _ctx(intent=IntentType.bio_ai_explanation)).count("not diagnoses") == 1


def test_internal_wording_becomes_plain():
    out = polish_answer("Thyroid Health was not retrieved, so there is no estimate.", _ctx())
    assert "retrieved" not in out and "isn't included in your report" in out


def test_unlisted_bio_ai_assessment_is_dropped():
    risks = [BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=84, status="Very High"),
             BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High")]
    text = ("Your strongest signals are Dyslipidemia and Type 2 diabetes.\n"
            "- NAFLD refers to an estimated risk of fat buildup in the liver.\n"
            "- Dyslipidemia fits your high LDL.")
    out = polish_answer(text, _ctx(intent=IntentType.bio_ai_explanation, risks=risks))
    assert "NAFLD" not in out
    assert "Dyslipidemia fits your high LDL." in out


def test_qualifier_does_not_cut_a_content_sentence():
    text = (
        "- This Dyslipidemia score estimates your chance of having unhealthy blood fats, "
        "and it is a risk estimate not a diagnosis.\n"
        "- Your score is 71, which is high."
    )
    out = polish_answer(text, _ctx(intent=IntentType.bio_ai_explanation, risks=[
        BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=71, status="high")
    ]))
    assert "unhealthy blood fats" in out
    assert not out.endswith("blood")
    assert "71" in out


def test_incomplete_bullets_anywhere_are_repaired():
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag

    marker = BloodMarker(id="1", key="hba1c", name="HbA1c", value=9.1, unit="%", flag=MarkerFlag.high)
    ctx = HealthContext(intent=IntentType.report_explanation, answer_depth=AnswerDepth.simple,
                        knowledge_scope=KnowledgeScope.personal, markers=[marker])
    text = "\n".join([
        "- Your average blood",
        "- The middle point is still",
        "- HbA1c reflects average sugar.\n  over recent months.",
        "- The closing thought is",
        "- Your HbA1c is 9.1%.",
        "- LDL is 162 mg/dL.",
    ])
    out = polish_answer(text, ctx, intent="report_explanation")
    assert "average blood" not in out
    assert "middle point is still" not in out
    assert "closing thought is" not in out
    assert "over recent months." in out
    assert "9.1%" in out
    assert "162 mg/dL" in out
    only = polish_answer("- Your HbA1c is 9.1% and the explanation of average blood", ctx, intent="report_explanation")
    assert "9.1%" in only
    assert "average blood" not in only


def test_listed_assessment_is_kept():
    risks = [BioAIRisk(code="nafld", name="NAFLD", score=40, status="Moderate")]
    out = polish_answer("NAFLD is moderate.", _ctx(intent=IntentType.bio_ai_explanation, risks=risks))
    assert out == "NAFLD is moderate."


def test_brief_carries_guideline_notes_and_bio_links():
    from app.contracts.blood import BloodMarker
    from app.contracts.common import MarkerFlag
    from app.pipeline.answer_evidence import build_clinical_evidence_brief

    hba1c = BloodMarker(id="1", key="hba1c", name="Hba1c", value=9.1, unit="%", flag=MarkerFlag.high,
                        reference_low=4.2, reference_high=5.7)
    vit_d = BloodMarker(id="2", key="vitamin_d", name="Vitamin D", value=29.8, unit="ng/mL", flag=MarkerFlag.low)
    blood = HealthContext(intent=IntentType.report_explanation, answer_depth=AnswerDepth.broad,
                          knowledge_scope=KnowledgeScope.personal, markers=[vit_d, hba1c])
    brief = build_clinical_evidence_brief(blood, primary_source="blood_report")
    assert "diagnose diabetes" in brief["guideline_notes"][0]
    assert brief["patterns"][0]["measured_results"][0]["name"].lower() == "hba1c"

    risks = [BioAIRisk(code=f"r{i}", name=f"Risk {i}", score=10 + i, status="low") for i in range(5)]
    risks.append(BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High"))
    bio = HealthContext(intent=IntentType.bio_ai_explanation, answer_depth=AnswerDepth.broad,
                        knowledge_scope=KnowledgeScope.personal, markers=[hba1c], bio_ai_risks=risks)
    brief = build_clinical_evidence_brief(bio, primary_source="bio_ai")
    assert len(brief["assessments"]) == 6
    top = brief["assessments"][0]
    assert top["related_blood_results"] == ["HbA1c 9.1% (high)"]
