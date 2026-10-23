from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import MarkerFlag as F
from app.pipeline.grounding import _attribution_issues
from app.pipeline.report_explainer import explain_bio_ai, explain_blood_report


def _m(name, value, unit, flag):
    return BloodMarker(id=name, key=name, name=name, value=value, unit=unit, flag=flag)


MARKERS = [
    _m("Chlorides", 99, "mmol/L", F.low),
    _m("Cholesterol Total", 228.9, "mg/dl", F.high),
    _m("Triglycerides", 265.9, "mg/dl", F.high),
    _m("LDL Cholestrol Calculated", 128.25, "mg/dl", F.high),
    _m("MCV", 80.1, "fL", F.low),
    _m("Ferritin", 22.6, "ng/ml", F.low),
    _m("TIBC", 429.18, "µg/dl", F.high),
    _m("MPV Mean Platelate Count", 9.7, "fL", F.high),
    _m("MPV", 9.7, "fL", F.high),
    _m("Hba1c", 9.1, "%", F.high),
    _m("Sodium", 140, "mmol/L", F.normal),
]


def test_blood_report_leads_with_urgent_area_and_explains_patterns():
    text = explain_blood_report(MARKERS, in_range=38, out_of_range=18)
    assert text.startswith("Most of your results look fine: 38 of 56")
    assert text.index("**Blood sugar**") < text.index("**Cholesterol and blood fats**")
    assert "range used to diagnose diabetes" in text
    assert "iron stores are running low" in text
    assert "doctor soon" in text.split("**What to do next:**")[1]


def test_blood_report_dedupes_and_cleans_lab_spellings():
    text = explain_blood_report(MARKERS)
    assert text.count("9.7 fL") == 1
    assert "Cholestrol" not in text and "Platelate" not in text
    assert "Sodium" not in text


def test_blood_report_all_in_range():
    assert "all the results" in explain_blood_report([_m("Sodium", 140, "mmol/L", F.normal)])


def test_bio_ai_ranks_attention_and_links_blood_results():
    risks = [
        BioAIRisk(code="hypertension", name="Hypertension", score=17, status="Healthy"),
        BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=70, status="High"),
        BioAIRisk(code="dyslipidemia", name="Dyslipidemia", score=84, status="Very High"),
    ]
    text = explain_bio_ai(risks, MARKERS)
    assert "not diagnoses" in text
    assert text.index("Dyslipidemia: 84") < text.index("Type 2 diabetes: 70")
    assert "HbA1c 9.1% (high) is outside the range" in text
    assert "**Looking good:** Hypertension" in text


def test_bio_ai_all_healthy():
    text = explain_bio_ai([BioAIRisk(code="thyroid", name="Thyroid", score=10, status="low"),
                           BioAIRisk(code="obesity", name="Obesity", score=12, status="low")])
    assert "none of your Bio-AI scores is in a raised range" in text


def test_grounding_reads_multi_word_marker_names():
    catalog = {"measured": {"fasting_blood_glucose": [{"value": "102.0000", "unit": "mg/dL", "current": True}]},
               "bio": {}, "derived": {}, "ranges": {}}
    assert _attribution_issues("Your Fasting Blood Glucose is 102 mg/dL.", catalog) == []
