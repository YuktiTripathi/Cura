"""Question typos resolve to a test name. Extracted PDF text is not fuzzy-matched here."""

from app.pipeline.lab_parameters import fuzzy_lab_keys


def test_single_token_typos_resolve():
    assert fuzzy_lab_keys("whats my creatnine") == ["creatinine"]
    assert fuzzy_lab_keys("creatinin level") == ["creatinine"]
    assert fuzzy_lab_keys("fasting glucoze") == ["fasting_blood_glucose"]
    assert fuzzy_lab_keys("my kidny functon") == ["kidney_function"]
    assert fuzzy_lab_keys("cholestrol report") == ["cholesterol"]
    assert fuzzy_lab_keys("whats my hba1c") == ["hba1c"]
    assert fuzzy_lab_keys("is my blood sugar normal") == ["glucose"]
    assert fuzzy_lab_keys("explain my thyroid test") == ["thyroid_function"]


def test_renal_phrasing_stays_on_the_kidney_panel():
    assert fuzzy_lab_keys("renal test result") == ["kidney_function"]


def test_creatine_asks_instead_of_using_creatinine():
    from app.pipeline.lab_parameters import question_clarification

    assert fuzzy_lab_keys("what is my creatine") == []
    assert "creatinine" in (question_clarification("what is my creatine") or "").lower()
    assert "creatine" in (question_clarification("what is my creatine") or "").lower()


def test_similar_biomarkers_are_not_collapsed():
    assert fuzzy_lab_keys("what is my creatine") == []
    assert fuzzy_lab_keys("what is my HDL") == ["hdl"]
    assert fuzzy_lab_keys("what is my LDL") == ["ldl"]
    assert fuzzy_lab_keys("what is my VLDL") == ["vldl"]
    assert fuzzy_lab_keys("what is my free T4") == ["free_t4"]
    assert fuzzy_lab_keys("what is my T4") == ["t4"]
    assert fuzzy_lab_keys("what is my urea") == ["urea"]
    assert fuzzy_lab_keys("what is my BUN") == ["bun"]
    assert "glucose" not in fuzzy_lab_keys("what is my fasting glucose") or fuzzy_lab_keys("what is my fasting glucose") == ["fasting_blood_glucose"]
