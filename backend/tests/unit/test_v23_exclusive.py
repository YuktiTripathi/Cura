"""V2.3 is the only curated education source."""

from app.biomarkers.education import education_for
from app.biomarkers.medical_registry import category_about, chat_passages


def test_ferritin_identity_uses_v23():
    note = education_for("ferritin", "Ferritin")
    assert note is not None
    assert note.content_source == "medical_knowledge_v2.3"
    assert "iron" in note.what_it_is.lower()


def test_known_marker_text_comes_from_v23():
    note = education_for("cholesterol_total", "Cholesterol Total")
    assert note is not None
    assert note.content_source == "medical_knowledge_v2.3"
    assert note.body
    assert "LEGACY_SHOULD_NOT_APPEAR" not in note.what_it_is


def test_missing_marker_does_not_use_old_education_file():
    note = education_for("not_a_real_marker_zz", "Not A Real Marker ZZ")
    assert note is None


def test_category_about_uses_v23():
    text = category_about("heart_circulation")
    assert "heart" in text.lower()


def test_chat_passage_is_v23_and_not_a_legacy_article():
    lines = chat_passages("What is cholesterol?", ["cholesterol_total"])
    assert lines
    assert "medical knowledge base" not in lines[0].lower()
