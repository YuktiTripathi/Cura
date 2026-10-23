"""Result rows stay attached to the printed biomarker, not the band beside them."""

from app.documents.extraction import ExtractedPage
from app.documents.facts import extract_facts_from_pages, facts_from_extracted
from app.documents.value_extraction import extract_known_observations

CYSTATIN_PAGE = """
GFR With Cystatin C
Serum Creatinine
Method: Modified Jaffe, Kinetic
Machine: BECKMAN COULTER AU 5800
1.03 mg/dl 0.7 - 1.4
Cystatin C
0.97 mg/L 0.5 - 1.03
GFR With Cystatin C
Method: Calculated(CKD-EPI Creatinine CystatinC
Equation)
91.73 •>= 90 mL/min/1.73m2:
Normal or high (Stage G1).
•60–89 mL/min/1.73m2:
Mildly decreased (Stage G2).
"""

LIPID_PAGE = """
Lipid Profile
Total Cholesterol
Method: Enzymatic
167.0 mg/dl Desirable : <200
Borderline: 200-239
High : >/=240
Serum Triglycerides
Method: Enzymatic
81.0 mg/dl Desirable : <150
Borderline high : 150-199
High : 200-499
Very high : > 500
Serum HDL Cholesterol
Method: Enzymatic immuno inhibition
73.0 mg/dl 40 - 60
"""

NON_HDL_PAGE = """
Non-HDL Cholesterol
Method: Calculated
94.0 mg/dl 0.0 - 160.0
"""

KFT_PAGE = """
Kidney Function Test (KFT)
Serum Creatinine
Method: Jaffes Kinetic
1.06 mg/dl 0.7-1.4
"""


def _values(text: str, page: int):
    rows = extract_known_observations(text, page)
    return [(item.parameter, item.value, item.unit, item.page, item.section) for item in rows]


def test_gfr_result_is_not_stored_as_creatinine():
    rows = _values(CYSTATIN_PAGE, 3)
    creatinine = [item for item in rows if item[0] == "creatinine"]
    assert creatinine == [("creatinine", 1.03, "mg/dL", 3, "GFR With Cystatin C")]
    assert ("egfr_cystatin", 91.73, None, 3, "GFR With Cystatin C") in rows
    assert all(item[1] != 91.73 or item[0] != "creatinine" for item in rows)


def test_lipid_bands_are_not_patient_results():
    rows = _values(LIPID_PAGE, 5)
    by_key = {item[0]: item for item in rows}
    assert by_key["cholesterol"][1] == 167.0
    assert by_key["cholesterol"][2] == "mg/dL"
    assert by_key["triglycerides"][1] == 81.0
    assert by_key["hdl"][1] == 73.0
    assert 240.0 not in {item[1] for item in rows}
    assert 500.0 not in {item[1] for item in rows}


def test_non_hdl_is_not_hdl():
    rows = _values(NON_HDL_PAGE, 6)
    assert rows[0][0] == "non_hdl"
    assert rows[0][1] == 94.0
    assert all(item[0] != "hdl" for item in rows)


def test_panels_keep_both_creatinine_observations():
    pages = [
        ExtractedPage(3, CYSTATIN_PAGE, len(CYSTATIN_PAGE)),
        ExtractedPage(8, KFT_PAGE, len(KFT_PAGE)),
    ]
    facts = facts_from_extracted(extract_facts_from_pages("fixture", pages))
    creatinine = [item for item in facts if item.canonical_code == "creatinine"]
    assert {(item.value, item.page_number, item.section) for item in creatinine} == {
        (1.03, 3, "GFR With Cystatin C"),
        (1.06, 8, "Kidney Function Test (KFT)"),
    }
    assert all(not item.conflict_group for item in creatinine)
