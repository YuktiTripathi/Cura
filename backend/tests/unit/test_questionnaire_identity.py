from app.medical_content.questionnaire_identity import coverage, verified_library_question


def test_exact_wording_matches_regardless_of_case_and_punctuation():
    row = verified_library_question("how often do you ADD extra salt to your food")
    assert row is not None and row["question"].startswith("How often do you add extra salt")


def test_a_staging_id_alone_never_matches_and_unknown_wording_is_unmatched():
    assert verified_library_question(None) is None
    assert verified_library_question("What is your favourite colour?") is None


def test_library_has_no_production_keys_so_nothing_is_matched_by_key():
    assert coverage()["with_production_key"] == 0
