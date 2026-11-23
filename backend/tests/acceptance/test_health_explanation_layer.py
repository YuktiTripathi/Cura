"""Relationship engine and safety validator: approved rules only, no causal claims, unsafe text rejected."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_unified_health import bio, blood, m  # noqa: E402

from app.biomarkers.unified_overview import build_category_detail  # noqa: E402
from app.health_explanation.relationship_engine import rules  # noqa: E402
from app.health_explanation.safety_validator import safety_problems  # noqa: E402

MEENA = [
    m("HbA1c", 5.9, 4.0, 5.7, "%"),
    m("Fasting Blood Glucose", 104, 70, 99, "mg/dL"),
    m("LDL Cholesterol", 142, 0, 100, "mg/dL"),
    m("HDL Cholesterol", 38, 50, 200, "mg/dL"),
    m("Triglycerides", 168, 0, 150, "mg/dL"),
]
RISKS = [("type_2_diabetes", "High Risk", 72), ("cardiac_health", "Increased Risk", 48)]


def _all_details():
    from app.biomarkers.health_categories import CATEGORIES

    got = [build_category_detail(c.id, blood(MEENA), bio(RISKS)) for c in CATEGORIES]
    return [d for d in got if d is not None]


def test_every_relationship_comes_from_an_approved_rule_and_is_never_causal():
    known = {r["rule_id"] for k in ("scenario_rules", "marker_group_rules") for r in rules()[k]}
    seen = [r for d in _all_details() for r in d.relationships]
    assert seen
    for r in seen:
        assert r.rule_id in known
        assert r.causal_claim is False
        assert r.evidence_status == "rule_based_unreviewed"
        assert r.rules_version == rules()["rules_version"]
        assert not safety_problems(r.interpretation)


def test_two_outside_blood_sugar_results_are_read_as_one_pattern_without_naming_a_condition():
    ids = [r.rule_id for d in _all_details() for r in d.relationships]
    assert "grp_blood_sugar_pair" in ids


def test_no_relationship_when_nothing_matches():
    only_one = [m("HbA1c", 5.9, 4.0, 5.7, "%")]
    from app.biomarkers.health_categories import CATEGORIES

    for c in CATEGORIES:
        d = build_category_detail(c.id, blood(only_one), None)
        assert d is None or all(r.rule_id != "grp_blood_sugar_pair" for r in d.relationships)


@pytest.mark.parametrize(
    "text,check",
    [
        ("You have type 2 diabetes.", "diagnosis"),
        ("This is caused by your diet.", "causal_claim"),
        ("This rules out heart disease.", "rules_out"),
        ("Take 500 mg of metformin daily.", "dose_or_medicine"),
        ("You have a 72% chance of diabetes.", "probability"),
    ],
)
def test_unsafe_text_is_rejected(text, check):
    assert check in safety_problems(text)


@pytest.mark.parametrize(
    "text",
    [
        "Your HbA1c is 5.9 %, slightly above the range of 4.0 to 5.7 %.",
        "A result in range does not rule out a problem.",
        "This is an estimate of the future, not a diagnosis.",
        "A prediction does not correct a measurement.",
    ],
)
def test_safe_plain_text_passes(text):
    assert safety_problems(text) == []
