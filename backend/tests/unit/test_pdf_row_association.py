"""Regression: each biomarker in an uploaded PDF keeps its own value, unit, reference range and row.

Before the fix, a marker could take its reference range from the next row (LDL got HbA1c's
4.0-5.6), labelled ranges were searched across the whole page (every marker got the first
"Reference range" on the page), and digits inside names ("A1c") were read as values.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.documents.extraction import extract_pdf_pages
from app.documents.facts import extract_facts_from_pages, facts_from_extracted
from app.documents.lab_answer import render_lab_answer
from app.documents.structured import extract_structured_from_chunks
from app.documents.value_extraction import extract_marker_from_text
from tests.helpers.pdf_fixtures import make_text_pdf

# (key, value, unit, low, high, name as printed) for six markers with different ranges.
PANEL = [
    ("ldl", 142.0, "mg/dL", 0.0, 100.0),
    ("hdl", 38.0, "mg/dL", 40.0, 60.0),
    ("triglycerides", 180.0, "mg/dL", 0.0, 150.0),
    ("hba1c", 5.9, "%", 4.0, 5.6),
    ("vitamin_d", 18.0, "ng/mL", 30.0, 100.0),
    ("crp", 2.4, "mg/L", 0.0, 1.0),
]

LAYOUTS = {
    # Typical table export: name, result, unit, bare range.
    "table": [
        "Test Result Unit Reference Range",
        "LDL Cholesterol 142 mg/dL 0 - 100",
        "HDL Cholesterol 38 mg/dL 40 - 60",
        "Triglycerides 180 mg/dL 0 - 150",
        "HbA1c 5.9 % 4.0 - 5.6",
        "25-OH Vitamin D 18 ng/mL 30 - 100",
        "hs-CRP 2.4 mg/L 0 - 1.0",
    ],
    # Labelled ranges with alternative lab names.
    "labelled": [
        "Cholesterol - LDL: 142 mg/dL Reference range: 0-100",
        "HDL-C: 38 mg/dL Reference range: 40-60",
        "Serum Triglycerides: 180 mg/dL Reference range: 0-150",
        "Glycated Haemoglobin (HbA1c): 5.9 % Reference range: 4.0-5.6",
        "25-Hydroxy Vitamin D: 18 ng/mL Reference range: 30-100",
        "High Sensitivity C-Reactive Protein: 2.4 mg/L Reference range: 0-1.0",
    ],
    # Bracketed "ref" ranges, "to" separators.
    "bracketed": [
        "LDL-C 142 mg/dL (ref 0 to 100)",
        "HDL 38 mg/dL (ref 40 to 60)",
        "TG 180 mg/dL (ref 0 to 150)",
        "Hb A1c 5.9 % (ref 4.0 to 5.6)",
        "25 Hydroxy Vitamin D 18 ng/mL (ref 30 to 100)",
        "C-Reactive Protein 2.4 mg/L (ref 0 to 1.0)",
    ],
}


def _pdf_markers(pages):
    doc = extract_facts_from_pages("doc-1", extract_pdf_pages(make_text_pdf(pages)))
    return {item.normalized_name: item for item in doc.biomarkers}, doc


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_adjacent_biomarkers_keep_their_own_row(layout):
    lines = LAYOUTS[layout]
    markers, _ = _pdf_markers([lines])
    assert set(markers) == {key for key, *_ in PANEL}, f"unexpected markers: {sorted(markers)}"
    for key, value, unit, low, high in PANEL:
        item = markers[key]
        assert (item.value, item.unit, item.reference_low, item.reference_high) == (value, unit, low, high), key
        assert item.source_page == 1
        # The excerpt is exactly the marker's own printed row and its line number points at it.
        row = lines[item.source_line - 1]
        assert item.excerpt == row, key
        assert f"{value:g}" in row


def test_reported_case_ldl_does_not_take_hba1c_range_from_next_line():
    markers, doc = _pdf_markers(
        [[
            "Lab Report - 12 Sep 2026",
            "LDL Cholesterol 142 mg/dL (ref < 100)",
            "HbA1c 5.6 % (ref 4.0-5.6)",
            "Vitamin D 18 ng/mL (ref 30-100)",
        ]]
    )
    ldl, hba1c, vit_d = markers["ldl"], markers["hba1c"], markers["vitamin_d"]
    assert (ldl.value, ldl.unit, ldl.reference_low, ldl.reference_high) == (142.0, "mg/dL", None, 100.0)
    assert ldl.reference_range == "< 100"
    assert ldl.flag == "high"
    assert ldl.source_line == 2 and ldl.excerpt == "LDL Cholesterol 142 mg/dL (ref < 100)"
    assert (hba1c.reference_low, hba1c.reference_high, hba1c.source_line) == (4.0, 5.6, 3)
    assert (vit_d.reference_low, vit_d.reference_high, vit_d.source_line) == (30.0, 100.0, 4)

    facts = {fact.canonical_code: fact for fact in facts_from_extracted(doc)}
    assert facts["ldl"].reference_text == "< 100"
    assert facts["ldl"].status == "high"
    assert facts["hba1c"].status == "normal"
    assert facts["ldl"].page_number == 1
    assert facts["ldl"].provenance_text == "LDL Cholesterol 142 mg/dL (ref < 100)"


def test_marker_without_range_does_not_borrow_the_next_rows_range():
    markers, _ = _pdf_markers([["LDL Cholesterol 142 mg/dL", "HbA1c 5.6 % 4.0 - 5.6"]])
    assert markers["ldl"].reference_low is None and markers["ldl"].reference_high is None
    assert markers["ldl"].flag is None
    assert (markers["hba1c"].reference_low, markers["hba1c"].reference_high) == (4.0, 5.6)


def test_labelled_range_is_not_shared_across_the_page():
    markers, _ = _pdf_markers([LAYOUTS["labelled"]])
    ranges = {key: (item.reference_low, item.reference_high) for key, item in markers.items()}
    assert len(set(ranges.values())) == len(ranges), ranges
    # Out of range against its own range, not "normal" against LDL's 0-100.
    assert markers["hba1c"].flag == "high"


def test_single_text_run_splits_rows_at_the_next_biomarker_name():
    markers, _ = _pdf_markers(["LDL Cholesterol 142 mg/dL HbA1c 5.6 % 4.0 - 5.6 hs-CRP 0.4 mg/L < 1.0"])
    assert markers["ldl"].reference_high is None
    assert markers["ldl"].excerpt == "LDL Cholesterol 142 mg/dL"
    assert (markers["hba1c"].value, markers["hba1c"].reference_high) == (5.6, 5.6)
    assert (markers["crp"].value, markers["crp"].unit, markers["crp"].reference_high) == (0.4, "mg/L", 1.0)


def test_names_nested_in_another_label_are_not_separate_results():
    markers, _ = _pdf_markers(
        [["Glycated Haemoglobin (HbA1c): 6.1 %", "Cholesterol - LDL: 131 mg/dL"]]
    )
    assert set(markers) == {"hba1c", "ldl"}
    assert markers["hba1c"].value == 6.1


def test_total_cholesterol_row_is_kept_next_to_ldl_and_hdl_rows():
    markers, _ = _pdf_markers(
        [["Cholesterol 210 mg/dL 0 - 200", "LDL Cholesterol 142 mg/dL 0 - 100", "HDL Cholesterol 38 mg/dL 40 - 60"]]
    )
    assert markers["cholesterol"].value == 210.0
    assert (markers["cholesterol"].reference_low, markers["cholesterol"].reference_high) == (0.0, 200.0)
    assert markers["ldl"].value == 142.0 and markers["hdl"].value == 38.0


def test_biomarkers_keep_their_page():
    markers, _ = _pdf_markers([["LDL Cholesterol 142 mg/dL 0 - 100"], ["HbA1c 5.9 % 4.0 - 5.6"]])
    assert markers["ldl"].source_page == 1
    assert markers["hba1c"].source_page == 2
    assert markers["hba1c"].source_line == 1


def test_chunk_extraction_uses_the_same_row_rule():
    chunk = SimpleNamespace(text="\n".join(LAYOUTS["table"]), page_start=3)
    doc = extract_structured_from_chunks("doc-1", [chunk])
    found = {item.normalized_name: item for item in doc.biomarkers}
    for key, value, unit, low, high in PANEL:
        assert (found[key].value, found[key].unit, found[key].reference_low, found[key].reference_high) == (
            value,
            unit,
            low,
            high,
        )
        assert found[key].source_page == 3


def test_one_sided_range_reaches_the_answer_text():
    value = extract_marker_from_text("LDL Cholesterol 142 mg/dL (ref < 100)\nHbA1c 5.6 % 4.0-5.6", "ldl", page=1)
    assert value is not None and value.reference_text == "< 100"
    answer = render_lab_answer([value], "what is my ldl")
    assert answer is not None
    assert "< 100 mg/dL" in answer
    assert "4" not in answer.split("is 142")[1].replace("< 100", "")


def test_columnar_table_reads_value_on_following_lines():
    lines = [
        "KIDNEY FUNCTION & ELECTROLYTES",
        "Test Name",
        "Value",
        "Unit",
        "Biological Reference Interval",
        "Creatinine",
        "0.57",
        "mg/dL",
        "0.3 - 1.2",
        "Sodium",
        "137",
        "mmol/L",
        "136 - 146",
        "Chloride",
        "105",
        "mmol/L",
        "101 - 109",
    ]
    markers, _ = _pdf_markers([lines])
    assert (markers["creatinine"].value, markers["creatinine"].unit) == (0.57, "mg/dL")
    assert (markers["sodium"].value, markers["sodium"].unit, markers["sodium"].reference_low, markers["sodium"].reference_high) == (
        137.0,
        "mmol/L",
        136.0,
        146.0,
    )
    assert (markers["chloride"].value, markers["chloride"].unit, markers["chloride"].reference_low, markers["chloride"].reference_high) == (
        105.0,
        "mmol/L",
        101.0,
        109.0,
    )
    assert markers["creatinine"].reference_high != 146.0


def test_columnar_table_does_not_give_next_marker_the_previous_value():
    markers, _ = _pdf_markers(
        [[
            "Sodium",
            "137",
            "mmol/L",
            "Chloride",
            "105",
            "mmol/L",
        ]]
    )
    assert markers["sodium"].value == 137.0
    assert markers["chloride"].value == 105.0


def test_one_sided_range_reaches_fact_evidence():
    from app.pipeline.document_answer import _fact_evidence

    _, doc = _pdf_markers([["LDL Cholesterol 142 mg/dL (ref < 100)", "HbA1c 5.6 % (ref 4.0-5.6)"]])
    facts = {fact.canonical_code: fact for fact in facts_from_extracted(doc)}
    assert _fact_evidence(facts["ldl"]).reference_range == "< 100 mg/dL"
    assert _fact_evidence(facts["hba1c"]).reference_range == "4–5.6 %"
