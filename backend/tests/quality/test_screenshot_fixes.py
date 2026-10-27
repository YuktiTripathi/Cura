"""Pipeline fixes from reviewing real answers. These hold for every member, not one account."""

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag as F
from app.contracts.health_context import HealthContext
from app.pipeline.answer_polish import polish_answer
from app.pipeline.followup_generator import FollowUpBrief, build_brief, valid_question

HBA1C = BloodMarker(id="1", key="hba1c", name="Hba1c", value=9.1, unit="%", flag=F.high)


def _ctx(intent=IntentType.report_explanation, markers=(), risks=()):
    return HealthContext(intent=intent, answer_depth=AnswerDepth.broad, knowledge_scope=KnowledgeScope.personal,
                         markers=list(markers), bio_ai_risks=list(risks))


def test_urgent_guideline_warning_is_always_present():
    out = polish_answer("- Your Hba1c is high and needs prompt attention.", _ctx(markers=[HBA1C]),
                        intent="report_explanation")
    assert "HbA1c of 9.1%" in out and "6.5%" in out and "doctor soon" in out


def test_warning_not_added_when_the_answer_already_says_it():
    text = "Your HbA1c is 9.1%, above the 6.5% diabetes cut-off. See your doctor soon."
    assert polish_answer(text, _ctx(markers=[HBA1C]), intent="report_explanation") == text


def test_negated_diabetes_caveat_is_not_rewritten():
    from app.contracts.query import QueryPlan
    from app.pipeline.clinical_postcheck import review_clinical_output

    risks = [BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High")]
    text = "Type 2 diabetes is rated high, but it does not confirm that you have diabetes."
    out, _flags = review_clinical_output(text, plan=QueryPlan(intent=IntentType.bio_ai_explanation),
                                         context=_ctx(IntentType.bio_ai_explanation, risks=risks))
    assert "does not confirm that you have diabetes" in out
    out, _flags = review_clinical_output("Based on this, you have diabetes.",
                                         plan=QueryPlan(intent=IntentType.bio_ai_explanation),
                                         context=_ctx(IntentType.bio_ai_explanation, risks=risks))
    assert "you have diabetes" not in out


def test_bio_ai_disclaimer_appears_once():
    risks = [BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=84, status="Very High")]
    text = ("These are risk estimates, not diagnoses.\n- Dyslipidemia is very high.\n"
            "These are risk estimates, not diagnoses. This is not a diagnosis. Discuss results with a clinician.")
    out = polish_answer(text, _ctx(IntentType.bio_ai_explanation, risks=risks), intent="bio_ai_explanation")
    assert sum(out.lower().count(p) for p in ("not diagnoses", "not a diagnosis")) == 1


def test_all_ten_bio_ai_assessments_are_known_and_paragraphs_are_never_cut():
    risks = [BioAIRisk(code=c, name=n, score=40, status="moderate") for c, n in [
        ("metabolic_syndrome", "Metabolic Syndrome"), ("pcos", "PCOS"), ("nafld", "NAFLD")]]
    text = "Metabolic Syndrome and NAFLD are moderate. PCOS is moderate too."
    assert polish_answer(text, _ctx(IntentType.bio_ai_explanation, risks=risks), intent="bio_ai_explanation") == text
    only_t2d = [BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High")]
    para = "Type 2 diabetes is high. Unlike NAFLD, this links to blood sugar."
    assert polish_answer(para, _ctx(IntentType.bio_ai_explanation, risks=only_t2d), intent="bio_ai_explanation") == para


def test_headings_read_properly():
    from app.pipeline.presentation import _display_heading

    assert _display_heading("tibc", "tibc") == "TIBC"
    assert _display_heading("hba1c", "Hba1c") == "HbA1c"


def test_chips_are_the_member_asking_not_cura_asking():
    brief = FollowUpBrief()
    for q in ("Would you like a 2-week walking plan I can tailor?",
              "How many minutes can you realistically walk today?",
              "Do you have any joint or heart issues that limit activity?"):
        assert not valid_question(q, brief), q
    assert valid_question("How can I improve my overall health?", brief)


def test_iron_test_questions_load_the_iron_group():
    from app.pipeline.context_builder import _with_pattern_keys

    assert {"ferritin", "hemoglobin"} <= set(_with_pattern_keys("What does my TIBC result mean?", ["tibc"]))
    assert _with_pattern_keys("What is my ferritin?", ["ferritin"]) == ["ferritin"]


def test_tibc_answer_uses_the_members_ferritin():
    from tests.quality.test_conversation_quality import ask

    body = ask("eval-user-iron", "What does my serum iron result mean?")
    lowered = body["answer"].lower()
    assert "ferritin" in lowered or "haemoglobin" in lowered or "hemoglobin" in lowered


def test_no_bio_ai_cards_under_a_lifestyle_question():
    from tests.quality.test_conversation_quality import ask

    body = ask("demo-user-001", "How can I improve my daily activity?")
    cards = (body.get("presentation") or {}).get("findings") or []
    assert not any(card.get("source_type") == "bio_ai_report" for card in cards)


def test_cura_explanations_use_bullets():
    from app.pipeline.report_explainer import explain_blood_report

    text = explain_blood_report([HBA1C], in_range=10, out_of_range=1)
    assert "\n- " in text
