"""Natural document questions stay on deterministic routes."""

from app.documents.extraction import ExtractedPage
from app.documents.pageindex import build_pageindex, retrieve_pageindex
from app.documents.query_policy import wants_document_narrative, wants_document_structured, wants_document_summary
from app.pipeline.lab_parameters import fuzzy_lab_keys


def test_natural_questions_pick_a_route():
    cases = {
        "Summarize the important findings in my report.": "summary",
        "Are my kidneys okay?": "panel",
        "Tell me about my allergy results.": "section",
        "Is anything unusual in my report?": "summary",
        "Should I worry about my cholesterol?": "marker",
        "What does my Bio-Allergy Plus report say?": "section",
        "What is my fasting glucose?": "marker",
    }
    for message, expected in cases.items():
        if expected == "summary":
            assert wants_document_summary(message)
        elif expected == "section":
            assert wants_document_narrative(message)
            assert not wants_document_structured(message)
        elif expected == "panel":
            assert "kidney_function" in fuzzy_lab_keys(message)
            assert wants_document_structured(message)
        else:
            assert fuzzy_lab_keys(message)
            assert wants_document_structured(message)
            assert not wants_document_summary(message)


def test_allergy_retrieval_prefers_the_result_page_over_the_header():
    pages = [
        ExtractedPage(
            12,
            "IMMUNOGLOBULIN E (IgE) TOTAL\n199.3 IU/ml <158\n",
            40,
        ),
        ExtractedPage(
            18,
            "Patient Name : Example Person\nOrder Id : 1\nBarcode : ABC\nDEPARTMENT OF ALLERGY-ELISA\nBio-Allergy Plus\n",
            80,
        ),
    ]
    tree = build_pageindex("doc", pages)
    hits = retrieve_pageindex(tree, "What does my Bio-Allergy Plus report say?")
    assert hits
    assert hits[0].page_start == 12
    assert "199.3" in hits[0].text
