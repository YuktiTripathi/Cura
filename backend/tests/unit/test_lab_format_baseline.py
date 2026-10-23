"""Baseline for lab-report layouts. Locks current extractor behavior, including known misses.

These assertions are a measurement snapshot, not a claim that every layout is clinically correct.
"""

from app.documents.extraction import ExtractedPage
from app.documents.facts import extract_facts_from_pages

CASES = {
    "three_column": "LDL Cholesterol 142 mg/dL 0 - 100\nHDL Cholesterol 55 mg/dL 40 - 60",
    "value_on_next_line": "Glucose, Fasting\nMethod: Hexokinase\n87.7 mg/dL 70 - 100",
    "range_line_before_value": "Fasting glucose\n70 - 100 mg/dL\n87.7",
    "reversed_columns": "Reference 70-100 Result 87.7 Unit mg/dL Test Fasting glucose",
    "mmol_unit": "Fasting glucose 4.8 mmol/L 3.9 - 5.6",
    "free_and_total_t4": "Free T4 1.2 ng/dL 0.8 - 1.8\nTotal T4 8.1 ug/dL 4.5 - 12.0",
    "urea_and_bun": "Blood urea 31.5 mg/dL 17 - 43\nBUN 14.7 mg/dL 8 - 20",
    "ige_total_and_specific": "Total IgE 199.3 IU/mL <158\nSpecific IgE D1 3.2 kUA/L",
    "creatinine_and_ratio": "Serum creatinine 1.06 mg/dL 0.7 - 1.4\nBUN/Creatinine Ratio 13.9",
    "two_egfr_equations": "eGFR creatinine 90\neGFR cystatin C 78",
    "estimated_vs_fasting": "Average Estimated Glucose\nMethod: Calculated\n96.8\nGlucose, Fasting\n87.7 mg/dL 70 - 100",
    "current_and_previous": "Glucose, Fasting\n87.7 mg/dL\nPrevious fasting glucose 110 mg/dL",
    "prose_plus_result": "Creatinine is discussed in the note. Creatinine 1.06 mg/dL.",
    "unknown_marker": "Apolipoprotein B 98 mg/dL 40 - 125",
    "two_dates_one_page": "Collection date: 01 Jan 2026\nLDL 100 mg/dL\nCollection date: 01 Jun 2026\nLDL 140 mg/dL",
    "no_text_layer": "",
}


def _facts(name, text):
    page = ExtractedPage(1, text, len(text), "text" if text else "empty")
    return [item for item in extract_facts_from_pages(name, [page]).biomarkers if item.value is not None]


def test_layout_baseline_snapshot():
    found = {name: [(item.normalized_name, item.value, item.measurement_kind) for item in _facts(name, text)] for name, text in CASES.items()}
    # Works on name-then-value rows already in the ontology.
    assert ("ldl", 142.0, "measured") in found["three_column"]
    assert ("fasting_blood_glucose", 87.7, "measured") in found["value_on_next_line"]
    assert ("fasting_blood_glucose", 4.8, "measured") in found["mmol_unit"]
    assert ("urea", 31.5, "measured") in found["urea_and_bun"]
    assert ("bun", 14.7, "measured") in found["urea_and_bun"]
    assert found["creatinine_and_ratio"] == [("creatinine", 1.06, "measured")]
    assert ("fasting_blood_glucose", 87.7, "measured") in found["estimated_vs_fasting"]
    assert ("glucose", 96.8, "calculated") in found["estimated_vs_fasting"]
    assert ("creatinine", 1.06, "measured") in found["prose_plus_result"]
    assert ("fasting_blood_glucose", 87.7, "measured") in found["range_line_before_value"]
    assert ("fasting_blood_glucose", 87.7, "measured") in found["reversed_columns"]
    assert ("free_t4", 1.2, "measured") in found["free_and_total_t4"]
    assert ("t4", 8.1, "measured") in found["free_and_total_t4"]
    assert any(name.lower().startswith("total ige") for name, *_ in found["ige_total_and_specific"])
    assert any("specific ige" in name.lower() for name, *_ in found["ige_total_and_specific"])
    assert ("egfr", 90.0, "measured") in found["two_egfr_equations"]
    assert ("egfr_cystatin", 78.0, "measured") in found["two_egfr_equations"]
    assert ("creatinine", 90.0, "measured") not in found["two_egfr_equations"]
    assert ("fasting_blood_glucose", 87.7, "measured") in found["current_and_previous"]
    assert ("fasting_blood_glucose", 110.0, "measured") in found["current_and_previous"]
    assert any("apolipoprotein" in name.lower() for name, *_ in found["unknown_marker"])
    assert {value for _name, value, _kind in found["two_dates_one_page"]} >= {100.0, 140.0}
    assert found["no_text_layer"] == []
