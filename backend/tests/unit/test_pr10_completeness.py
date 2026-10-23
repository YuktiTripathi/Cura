from types import SimpleNamespace

from app.llm.structured import parse_score_object
from app.pipeline.evidence_inventory import omitted_supported_facts, render_partial_trend


def _marker(key, name, value, unit, when, low=None, high=None):
    return SimpleNamespace(
        key=key, name=name, value=value, unit=unit, measured_at=when,
        reference_low=low, reference_high=high,
    )


def test_improvement_claim_is_replaced_by_the_numeric_change():
    markers = [
        _marker("hba1c", "HbA1c", 6.2, "%", "2026-06-12"),
        _marker("hba1c", "HbA1c", 6.1, "%", "2026-09-20"),
    ]
    text = render_partial_trend("Has my HbA1c improved?", markers)
    assert "6.2" in text and "6.1" in text
    assert "improvement" not in text.lower()
    assert "not a clinical conclusion" in text.lower()


def test_named_lipid_values_are_required_even_when_the_name_appears():
    markers = [
        _marker("hdl", "HDL", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", "HDL", 38, "mg/dL", "2026-09-20"),
        _marker("triglycerides", "Triglycerides", 240, "mg/dL", "2026-06-12"),
        _marker("triglycerides", "Triglycerides", 220, "mg/dL", "2026-09-20"),
    ]
    prose = "HDL rose from 37 to 38 mg/dL. Triglycerides moved down but stayed high."
    extra = omitted_supported_facts("How have my HDL and triglycerides changed?", markers, prose)
    assert "240" in extra and "220" in extra
    assert "total cholesterol" not in extra.lower()


def test_follow_up_keeps_the_retrieved_value():
    markers = [_marker("hba1c", "HbA1c", 6.1, "%", "2026-09-20", 4.4, 5.7)]
    extra = omitted_supported_facts("Why is it high?", markers, "Your HbA1c is above the report range.")
    assert extra and "6.1" in extra


def test_vitamin_d_value_and_range_are_required():
    markers = [_marker("vitamin_d", "Vitamin D", 34, "ng/mL", "2026-09-20", 30, 100)]
    extra = omitted_supported_facts("Explain my vitamin D.", markers, "Vitamin D is adequate.")
    assert "34" in extra and "30" in extra and "100" in extra


def test_fasting_glucose_comparison_is_not_a_clarification():
    markers = [
        _marker("fasting_blood_glucose", "Fasting Blood Glucose", 98, "mg/dL", "2026-06-12"),
        _marker("fasting_blood_glucose", "Fasting Blood Glucose", 96, "mg/dL", "2026-09-20"),
    ]
    text = render_partial_trend("Has my fasting glucose changed?", markers)
    assert "98" in text and "96" in text and "mg/dL" in text


def test_optional_unmentioned_marker_is_not_required():
    markers = [
        _marker("hdl", "HDL", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", "HDL", 38, "mg/dL", "2026-09-20"),
        _marker("ldl", "LDL", 96, "mg/dL", "2026-09-20"),
    ]
    extra = omitted_supported_facts("How has my HDL changed?", markers, "HDL was 37 mg/dL and then 38 mg/dL.")
    assert extra is None or "96" not in (extra or "")


def test_equivalent_numbers_and_judge_payloads():
    assert parse_score_object(
        '{"correctness": 4, "relevance": 5, "completeness": 4, "clarity": 5, "uncertainty": 4, "grounding": 5, "critical": false, "note": "ok"}'
    )["correctness"] == 4
    assert parse_score_object("")["error"] == "empty_response"
    assert parse_score_object('{"answer": "not scores"}')["error"].startswith("missing_")
    assert _same_number("1.1", "1.10")
    assert not _same_number("1.1", "1.2")


def _same_number(left: str, right: str) -> bool:
    return abs(float(left) - float(right)) < 1e-9
