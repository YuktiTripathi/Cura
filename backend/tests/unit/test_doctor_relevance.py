from app.pipeline.markdown_tidy import drop_routine_doctor
from app.pipeline.prompt_modules import HOUSE_CORE


def test_routine_visit_filler_is_dropped():
    text = "- Your ALP is 120, slightly above range. Share these scores with your doctor at your next routine visit.\n- Discuss this with your doctor."
    out = drop_routine_doctor(text)
    assert "routine visit" not in out and "Discuss this" not in out
    assert "ALP is 120" in out


def test_real_referral_is_kept():
    text = "- Your LDL is far above range. See a doctor within a few weeks and bring this report."
    assert drop_routine_doctor(text) == text


def test_prompt_does_not_force_a_doctor_bullet():
    assert "One of them says how soon to see a doctor" not in HOUSE_CORE
    assert "goes in the last bullet" not in HOUSE_CORE


def test_narrow_questions_skip_report_layouts():
    from types import SimpleNamespace
    from app.contracts.common import IntentType
    from app.pipeline.prompt_modules import core_for
    narrow = SimpleNamespace(intent=IntentType.blood_marker_explanation)
    wide = SimpleNamespace(intent=IntentType.broad_health_summary)
    assert "SHAPE 1A, a whole" not in core_for(narrow, "What is urea?") and "Answer exactly what the user is asking" in core_for(narrow, "What is urea?")
    assert "SHAPE 1A, a whole" in core_for(wide, "Explain my report")


def test_negated_diagnosis_wording_gets_no_boilerplate():
    from app.pipeline.safety import _asserts_diagnosis
    assert not _asserts_diagnosis("It does not mean you have heart disease.")
    assert not _asserts_diagnosis("neither one alone proves that you have a condition")
    assert _asserts_diagnosis("You have diabetes.")


def test_cross_source_question_keeps_blood_measurements():
    import inspect
    from app.pipeline import evidence_inventory
    assert "plan.needs_blood" in inspect.getsource(evidence_inventory.assemble_evidence)


def test_glued_bullets_split_and_question_labels_go():
    from app.pipeline.markdown_tidy import drop_bullet_labels, split_inline_bullets
    out = split_inline_bullets("Nice question. - One idea here. - Another idea here.")
    assert out.count("\n- ") == 2
    assert drop_bullet_labels("- Worry?: It is still above the range.") == "- It is still above the range."
    assert drop_bullet_labels("- Change: 142.0 mg/dL to 138.0 mg/dL").startswith("- 142.0")


def test_groups_use_body_system_names_not_lab_packages():
    from app.retrieval.relationship_map import group_measurements
    rows = [{"key": "vitamin_d", "name": "Vitamin D"}, {"key": "ldl", "name": "LDL"}]
    labels = [g["label"] for g in group_measurements(rows)]
    assert labels == ["Vitamins", "Cholesterol and blood fats"]
