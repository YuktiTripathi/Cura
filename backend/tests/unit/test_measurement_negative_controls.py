"""Numbers that must not become biomarker rows."""

from app.documents.extraction import ExtractedPage
from app.documents.facts import extract_facts_from_pages


def _rows(text):
    page = ExtractedPage(1, text, len(text))
    return [item for item in extract_facts_from_pages("neg", [page]).biomarkers if item.value is not None]


def test_prose_instrument_identity_range_and_dates_are_not_results():
    text = "\n".join(
        [
            "The note says glucose can vary during illness and quotes 99 as an example.",
            "Machine: AU 5800",
            "Patient Id : 20512445655",
            "Normal : < 100 mg/dl",
            "Collection date: 01 Jan 2026",
            "Reference range 70 - 100 mg/dL",
        ]
    )
    assert _rows(text) == []
