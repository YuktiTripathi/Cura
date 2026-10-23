"""Fasting glucose stays a measurement; ranges, estimates, and instrument ids do not."""

from app.contracts.uploaded_document import UploadedDocumentContext
from app.documents.extraction import ExtractedPage
from app.documents.facts import extract_facts_from_pages, facts_from_extracted
from app.documents.lookup import FOUND, cover_requested_entities, format_coverage
from app.documents.value_extraction import extract_marker_from_text


PAGE1 = """\
HbA1c - Glycosylated Hemoglobin
Method: HPLC
Machine: TOSOH G11
5.00 % 4.2 - 5.7
Average Estimated Glucose
Method: Calculated
96.80
As per ADA:
Normal : <5.7
Prediabetes 5.7 - 6.4
Diabetes: >= 6.5
Patient Id : 20512445655
"""

PAGE2 = """\
Fasting Blood Sugar
Glucose, Fasting
Method: Hexokinase
Machine: DXC 700AU
87.7 mg/dl 70 - 100
Normal : < 100 mg/dl
Impaired fasting glucose (IFG) : 100 - 126 mg/dl
Diabetes : >= 126 mg/dl
Patient Id : 20512445655
"""

PAGE8 = """\
Creatinine
Method: Jaffe
Machine: AU 5800
1.06 mg/dl 0.7-1.4
Estimated GFR
90.01 mL/min/1.73m2
Urea
Method: AU 5800
31.5 mg/dl 17 - 43
"""

PAGE12 = """\
Immunoglobulin - IgE Total - Serum
Method: Immunoassay
Machine: IM1600
199.3 IU/ml <158
"""


def _pages():
    blobs = [(1, PAGE1), (2, PAGE2), (8, PAGE8), (12, PAGE12)]
    return [
        ExtractedPage(page_number=number, text=text, character_count=len(text))
        for number, text in blobs
    ]


def _by(doc, key):
    return [item for item in doc.biomarkers if item.normalized_name == key and item.value is not None]


def test_fasting_glucose_is_the_measured_row_not_the_range():
    doc = extract_facts_from_pages("doc", _pages())
    fasting = _by(doc, "fasting_blood_glucose")
    assert len(fasting) == 1
    assert fasting[0].value == 87.7
    assert fasting[0].unit == "mg/dL"
    assert fasting[0].source_page == 2
    assert (fasting[0].reference_low, fasting[0].reference_high) == (70.0, 100.0)
    assert fasting[0].measurement_kind == "measured"
    assert all(item.value != 100 for item in fasting)


def test_estimated_glucose_is_calculated_and_not_a_fasting_conflict():
    doc = extract_facts_from_pages("doc", _pages())
    calculated = [item for item in doc.biomarkers if item.measurement_kind == "calculated"]
    assert any(item.value == 96.8 and item.source_page == 1 for item in calculated)
    facts = facts_from_extracted(doc)
    ctx = UploadedDocumentContext(document_id="doc", structured_facts=facts)
    rows = cover_requested_entities([ctx], ["fasting_blood_glucose"])
    assert rows[0].status == FOUND
    assert rows[0].facts[0].value == 87.7
    assert "Conflicting" not in format_coverage(rows)


def test_instrument_and_patient_ids_are_not_results():
    doc = extract_facts_from_pages("doc", _pages())
    values = {item.value for item in doc.biomarkers}
    assert 5800 not in values
    assert 700 not in values
    assert 20512445655 not in values
    creatinine = _by(doc, "creatinine")
    assert creatinine[0].value == 1.06
    assert creatinine[0].source_page == 8
    egfr = _by(doc, "egfr")
    assert egfr[0].value == 90.01
    assert egfr[0].source_page == 8


def test_total_ige_is_not_assigned_to_another_marker():
    extracted = extract_marker_from_text(PAGE12, "creatinine", page=12)
    assert extracted is None or extracted.value != 199.3


def test_kidney_panel_lists_members_without_merging_them():
    doc = extract_facts_from_pages("doc", _pages())
    ctx = UploadedDocumentContext(document_id="doc", structured_facts=facts_from_extracted(doc))
    rows = {row.code: row for row in cover_requested_entities([ctx], ["kidney_function"])}
    assert rows["creatinine"].facts[0].value == 1.06
    assert rows["egfr"].facts[0].value == 90.01
    assert rows["urea"].facts[0].value == 31.5
    assert rows["creatinine"].status == FOUND
    assert rows["creatinine"].facts[0].value != rows["urea"].facts[0].value


def test_ratio_and_prose_numbers_are_not_the_analyte():
    text = "BUN/Creatinine Ratio\n13.89 Ratio\nGFR is used above age 20 years in adults."
    creatinine = extract_marker_from_text(text, "creatinine")
    egfr = extract_marker_from_text(text, "egfr")
    assert creatinine is None or creatinine.value is None
    assert egfr is None or egfr.value is None


def test_two_real_hdl_values_still_conflict():
    pages = [
        ExtractedPage(1, "HDL cholesterol 57 mg/dL", 24),
        ExtractedPage(2, "HDL cholesterol 41 mg/dL", 24),
    ]
    facts = facts_from_extracted(extract_facts_from_pages("doc", pages))
    ctx = UploadedDocumentContext(document_id="doc", structured_facts=facts)
    rows = cover_requested_entities([ctx], ["hdl"])
    assert rows[0].status == "AMBIGUOUS"
    assert "Conflicting" in format_coverage(rows)


def test_selected_document_does_not_read_the_other_report():
    mine = facts_from_extracted(extract_facts_from_pages("mine", _pages()))
    other_pages = [ExtractedPage(1, "Glucose, Fasting\n110 mg/dL 70 - 100", 40)]
    other = facts_from_extracted(extract_facts_from_pages("other", other_pages))
    ctx = UploadedDocumentContext(document_id="mine", structured_facts=mine)
    rows = cover_requested_entities([ctx], ["fasting_blood_glucose"])
    assert rows[0].facts[0].value == 87.7
    assert all(item.source_document_id == "mine" for item in rows[0].facts)
    assert other[0].source_document_id == "other"
