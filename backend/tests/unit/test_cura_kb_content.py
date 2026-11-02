"""Cura knowledge base passages in app/retrieval/content (biomarkers and Bio-AI conditions)."""

import json

import pytest

from app.retrieval import medical
from app.retrieval.hybrid import HybridMedicalKnowledgeProvider
from app.retrieval.medical import is_servable, load_content_dir

KB_FILES = ("cura_biomarkers.json", "cura_bio_ai_conditions.json")
BIO_AI_TOPICS = {
    "dyslipidemia", "stroke", "cardiac_health", "pcos", "metabolic_syndrome",
    "hypothyroidism", "obesity", "type_2_diabetes", "hypertension", "masld",
}


def _rows():
    rows = []
    for name in KB_FILES:
        rows.extend(json.loads((medical.CONTENT_DIR / name).read_text(encoding="utf-8")))
    return rows


def test_files_are_lists_of_passages_with_required_fields():
    rows = _rows()
    assert len(rows) >= 122
    for row in rows:
        assert row["topics"] and row["keywords"] and row["excerpt"].strip()
        assert row["content_kind"] == "cura_summary"


def test_names_are_unique_because_retrieval_dedupes_on_name_and_url():
    keys = [(row["name"], row["url"]) for row in _rows()]
    assert len(set(keys)) == len(keys)


def test_all_ten_bio_ai_conditions_are_present():
    topics = {t for row in _rows() for t in row["topics"]}
    assert BIO_AI_TOPICS <= topics


def test_excerpts_carry_no_reference_ranges_or_dashes():
    for row in _rows():
        assert "–" not in row["excerpt"] and "—" not in row["excerpt"]
        assert "General ranges" not in row["excerpt"]


def test_draft_passages_are_never_servable_until_reviewed():
    docs = [d for d in load_content_dir(medical.CONTENT_DIR) if d.name.startswith("Cura knowledge base:")]
    assert docs
    for doc in docs:
        if doc.review_status in {"reviewed", "published"}:
            assert doc.reviewer and doc.reviewed_on
        else:
            assert not is_servable(doc)


@pytest.mark.parametrize(
    "question,topic,expected",
    [
        ("What does my hemoglobin mean?", "hemoglobin", "hemoglobin"),
        ("Why is my SGPT high?", "alt", "alt"),
        ("What is a high RDW?", None, "rdw"),
        ("What is dyslipidemia?", "dyslipidemia", "dyslipidemia"),
        ("What is PCOS?", "pcos", "pcos"),
    ],
)
def test_questions_find_the_matching_passage(question, topic, expected):
    hits = HybridMedicalKnowledgeProvider().query(question, topic, limit=3)
    assert any(expected in doc.topics for doc in hits)
