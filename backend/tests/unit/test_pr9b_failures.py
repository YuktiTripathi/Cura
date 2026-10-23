from types import SimpleNamespace

from app.pipeline.evidence_inventory import classify_marker_trends, render_partial_trend
from app.pipeline.lab_parameters import match_lab_keys
from app.pipeline.safety import SafetyLayer, educational_symptom_question


def test_named_labs_include_ggtp_and_proteins_serum():
    keys = match_lab_keys("On 2026-09-01, Albumin is 4.5 g/dl and GGTP is 21.4 U/L.")
    assert "albumin" in keys and "ggt" in keys
    assert "proteins_serum" in match_lab_keys("what is the stored Proteins Serum and its unit?")


def test_blank_comparison_unit_does_not_claim_hba1c_units_differ():
    markers = [
        SimpleNamespace(key="hba1c", name="HbA1c", value=6.2, unit="%", measured_at="2026-06-12"),
        SimpleNamespace(key="hba1c", name="HbA1c", value=6.1, unit="%", measured_at="2026-09-20"),
    ]
    comparison = SimpleNamespace(
        topic="hba1c",
        previous_value=6.2,
        current_value=6.1,
        previous_date="2026-06-12",
        current_date="2026-09-20",
        previous_unit=None,
        current_unit=None,
    )
    coverage = classify_marker_trends("Has my HbA1c improved?", markers, [comparison])
    assert coverage["incompatible_units"] == []
    assert coverage["supported"][0]["absolute_change"] == -0.1
    text = render_partial_trend("Has my HbA1c improved?", markers, [comparison])
    assert "6.2" in text and "6.1" in text and "%" in text
    assert "units do not match" not in text.lower()
    assert "not a clinical conclusion" in text.lower()


def test_chest_pain_education_is_not_a_current_emergency():
    layer = SafetyLayer()
    education = layer.check_input("When should chest pain be treated as urgent?")
    assert education.blocked is False
    assert educational_symptom_question("What causes chest pain?")
    assert educational_symptom_question("When is chest pain an emergency?")
    assert educational_symptom_question("chest pain kab emergency hota hai?")
    assert layer.check_input("I have chest pain right now.").blocked is True
    assert layer.check_input("My father has severe chest pain.").blocked is True
    assert layer.check_input("Severe chest pain and difficulty breathing.").blocked is True
    assert layer.check_input("मुझे अभी छाती में दर्द हो रहा है").blocked is True
    assert layer.check_input("छाती में दर्द कब इमरजेंसी माना जाए?").blocked is False
