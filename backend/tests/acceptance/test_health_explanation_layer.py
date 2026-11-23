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


def test_every_action_comes_from_the_approved_library_and_is_safe():
    from app.health_explanation.relationship_engine import action_library

    known = {a["action_id"] for a in action_library()["actions"]}
    details = _all_details()
    acts = [a for d in details for a in d.actions]
    assert acts
    for a in acts:
        assert a.action_id in known
        assert a.evidence_status == "rule_based_unreviewed"
        assert not safety_problems(a.title + " " + a.detail)


def test_a_model_cannot_add_or_change_actions():
    from app.biomarkers.unified_overview import prepare
    from app.pipeline.unified_wording import _fit, rules_wording

    cards, parts, prov = prepare(blood(MEENA), bio(RISKS))
    base = rules_wording(cards, parts, prov, detail=True)
    cid = cards[0].id
    raw = {"categories": {cid: {"summary": "Short summary.", "actions": [{"title": "Take vitamin D 2000 IU", "detail": "Daily.", "icon": "x"}, {"title": "B", "detail": "c"}]}}}
    got = _fit(raw, cards, parts, prov, set())
    assert got.categories[cid]["actions"] == base.categories[cid]["actions"]
    assert all("vitamin" not in a["title"].lower() for a in got.categories[cid]["actions"])


# Endpoints and isolation ------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_client = TestClient(app)
_A = {"X-Cura-User-Id": "demo-user-001"}


def test_overview_carries_versions_and_limitations():
    r = _client.get("/api/v1/health-explanation/overview", headers=_A)
    assert r.status_code == 200
    body = r.json()
    assert set(body["versions"]) == {"categories", "relationships", "actions", "wording"}
    assert isinstance(body["limitations"], list)


def test_refresh_returns_the_same_shape_and_category_and_finding_endpoints_work():
    ov = _client.post("/api/v1/health-explanation/refresh", headers=_A).json()
    assert ov["available"] in (True, False)
    if not ov["available"]:
        return
    cid = ov["categories"][0]["id"]
    detail = _client.get(f"/api/v1/health-explanation/categories/{cid}", headers=_A).json()
    fid = detail["findings"][0]["id"]
    f = _client.get(f"/api/v1/health-explanation/findings/{fid}", headers=_A).json()
    assert f["id"] == fid and f["data_quality"] in {"verified", "reference_unavailable", "unavailable"}


def test_unknown_category_and_finding_are_404_and_there_is_no_member_id_in_any_path():
    assert _client.get("/api/v1/health-explanation/categories/nope", headers=_A).status_code == 404
    assert _client.get("/api/v1/health-explanation/findings/nope", headers=_A).status_code == 404
    paths = [p for p in app.openapi()["paths"] if "health-explanation" in p]
    assert paths and not any("user" in p or "subject" in p or "member" in p for p in paths)


def test_one_members_finding_id_is_not_served_to_another_member():
    ov = _client.get("/api/v1/health-explanation/overview", headers=_A).json()
    if not ov["available"]:
        return
    cid = ov["categories"][0]["id"]
    fid = _client.get(f"/api/v1/health-explanation/categories/{cid}", headers=_A).json()["findings"][0]["id"]
    other = _client.get(f"/api/v1/health-explanation/findings/{fid}", headers={"X-Cura-User-Id": "no-such-member-999"})
    mine = _client.get(f"/api/v1/health-explanation/findings/{fid}", headers=_A)
    assert mine.status_code == 200
    # Another member either gets nothing or their own data. Never the first member's finding.
    assert other.status_code != 200 or other.json() != mine.json()


def test_data_quality_follows_what_the_report_supplied():
    from app.contracts.unified_health import Finding

    base = dict(id="x", source_type="measured", name="X", status_label="s")
    assert Finding(status="no_range", **base).data_quality == "reference_unavailable"
    assert Finding(status="no_value", **base).data_quality == "unavailable"
    assert Finding(status="above_range", **base).data_quality == "verified"
