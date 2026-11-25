from app.medical_content.attach import note_for, passages_for
from app.medical_content.mapping import mapping_rows
from app.medical_content.registry import load_registry


def test_a_row_without_review_status_is_still_usable():
    from app.biomarkers.medical_registry import eligible

    assert eligible({"display_name": "ALT", "short_description": "An enzyme."})
    assert not eligible({"review_status": "rejected"})
    assert not eligible(None)


def test_library_loads_once_and_keeps_review_status():
    library = load_registry()
    assert library["version"] == "2.3"
    assert len(library["biomarkers"]) == 119
    assert len(library["relationships"]) == 219
    assert all(entry["review_status"] == "pending_clinical_review" for entry in library["biomarkers"])


def test_exact_matches_only_and_unresolved_stay_unresolved():
    rows = mapping_rows()
    confirmed = [row for row in rows if row["mapping_status"] == "exact_canonical_match"]
    unresolved = [row for row in rows if row["mapping_status"] == "unresolved"]
    assert confirmed
    assert all(row["canonical_identifier"] for row in confirmed)
    glucose = next(row for row in rows if row["content_key"] == "WB-070")
    assert glucose["canonical_identifier"] == "average_blood_glucose"
    assert not glucose["provider_identifier"]


def test_confirmed_marker_attaches_without_an_approval_flag():
    note = note_for("cholesterol_total", "within_range")
    assert note is not None
    assert "laboratory" in note.next_step.lower() or note.what_it_is
    assert note_for("not_a_real_marker", "within_range") is None
    assert passages_for(["cholesterol_total"])
