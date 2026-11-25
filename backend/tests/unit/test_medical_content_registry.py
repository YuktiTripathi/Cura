from app.biomarkers import medical_registry as library
from app.biomarkers.education_notes import note_for


def test_a_row_without_review_status_is_still_usable():
    assert library.eligible({"display_name": "ALT", "short_description": "An enzyme."})
    assert not library.eligible({"review_status": "rejected"})
    assert not library.eligible(None)


def test_library_loads_once_and_keeps_review_status():
    assert library.CONTENT_VERSION == "2.3"
    assert len(library.relationships()) == 219
    assert len(library.bio_ai_content()) == 11
    rows = library._load("content/biomarker_content.json")
    assert len(rows) == 119
    assert all(row["review_status"] == "pending_clinical_review" for row in rows)


def test_identity_comes_from_the_inventory_not_from_names():
    identities = library._identity_by_content_key()
    assert identities.get("WB-070") == "average_blood_glucose"


def test_confirmed_marker_attaches_without_an_approval_flag():
    note = note_for("cholesterol_total", "within_range")
    assert note is not None and note.what_it_is
    assert note_for("not_a_real_marker", "within_range") is None
    assert library.chat_passages("What is cholesterol?", ["cholesterol_total"])
