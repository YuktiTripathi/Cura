"""Alias resolution and post-answer grounding for confirmed evaluation misses."""

from types import SimpleNamespace

from app.pipeline.clinical_postcheck import correct_false_absence, drop_unsupported_lifestyle
from app.pipeline.lab_parameters import canonicalize_marker_name, match_lab_keys
from app.pipeline.renderer import DeterministicRenderer


def test_misspelled_vldl_resolves_to_the_stored_marker():
    assert canonicalize_marker_name("VLDL Cholestrol") == "vldl"
    assert "vldl" in match_lab_keys("What is my latest VLDL Cholestrol?")
    assert canonicalize_marker_name("Phosphorus Inorganic") == "phosphorus"
    assert canonicalize_marker_name("Homocysteine") == "homocysteine"
    assert canonicalize_marker_name("HS-CRP") == "crp"


def test_absence_sentence_is_replaced_when_the_panel_has_the_marker():
    context = SimpleNamespace(
        markers=[],
        panel_markers=[SimpleNamespace(key="vldl", name="VLDL Cholestrol", value=30.8, unit="mg/dl")],
        questionnaire=[],
    )
    text = "I don't see VLDL Cholestrol in the latest blood report, so that value is not available."
    revised, flags = correct_false_absence(text, context)
    assert "false_absence_corrected" in flags
    assert "30.8" in revised
    assert "not available" not in revised.lower()


def test_educational_range_is_not_treated_as_a_missing_personal_marker():
    context = SimpleNamespace(markers=[], panel_markers=[], questionnaire=[])
    text = "A typical reference range is 70-100 mg/dl. This is general information."
    revised, flags = correct_false_absence(text, context)
    assert flags == []
    assert revised == text


def test_foods_not_in_the_questionnaire_are_removed():
    context = SimpleNamespace(questionnaire=[SimpleNamespace(question_key="diet", question="", value="vegetarian")])
    text = "You follow a vegetarian diet with chicken, fish, and pulses. Your vitamin B12 is on the report."
    revised, flags = drop_unsupported_lifestyle(text, context)
    assert "unsupported_lifestyle_removed" in flags
    assert "chicken" not in revised.lower()
    assert "vitamin B12" in revised


def test_general_lifestyle_advice_is_kept():
    context = SimpleNamespace(questionnaire=[])
    text = "A balanced diet and limiting alcohol are general habits worth discussing with a clinician."
    revised, flags = drop_unsupported_lifestyle(text, context)
    assert flags == []
    assert revised == text


def test_personal_diet_claim_without_questionnaire_is_removed():
    context = SimpleNamespace(questionnaire=[])
    text = "You follow a vegetarian diet. Your iron result is on the report."
    revised, flags = drop_unsupported_lifestyle(text, context)
    assert "unsupported_lifestyle_removed" in flags
    assert "vegetarian" not in revised.lower()
    assert "iron" in revised.lower()


def test_a_marker_left_out_of_the_answer_is_not_called_absent():
    context = SimpleNamespace(
        markers=[SimpleNamespace(key="vldl", name="VLDL", value=30.8, unit="mg/dl")],
        panel_markers=[],
        questionnaire=[],
    )
    text = "Ferritin was not found in the retrieved records."
    revised, flags = correct_false_absence(text, context)
    assert flags == []
    assert "not found" in revised.lower()


def test_esr_fallback_does_not_append_bmi():
    context = SimpleNamespace(
        intent=SimpleNamespace(value="blood_marker_explanation"),
        markers=[
            SimpleNamespace(
                name="ESR",
                value=22,
                unit="mm/hr",
                flag=SimpleNamespace(value="high"),
                reference_low=0,
                reference_high=15,
                key="esr",
            )
        ],
        derived=[SimpleNamespace(fact="bmi", value=26.5, unit="kg/m2", notes=["Computed from stored height and weight"])],
        user_stated=[],
        missing=[],
        source_conflicts=[],
        facts=[],
        recommendations=[],
        comparisons=[],
        bio_ai_risks=[],
        evidence=[],
        status="ok",
        scenario=None,
        questionnaire=[],
    )
    answer = DeterministicRenderer().render("What should I focus on first given my ESR finding?", context)
    assert "bmi" not in answer.lower()
    assert "22" in answer
