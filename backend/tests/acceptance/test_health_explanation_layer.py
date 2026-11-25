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
    assert detail["story"]["understand_body"]
    ui_detail = _client.get(f"/api/v1/me/health-overview/{cid}", headers=_A).json()
    assert ui_detail["story"] == detail["story"]
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


@pytest.mark.parametrize("markers, risks, expected", [
    (MEENA, RISKS, "risk_raised"),
    (MEENA, [("cardiac_health", "Healthy", 12)], "risk_healthy"),
    (MEENA, [("cardiac_health", "Unexpected label", 12)], "risk_unknown"),
    (MEENA, [], None),
    ([], RISKS, "risk_raised"),
    ([m("LDL Cholesterol", 85, 0, 100, "mg/dL")], RISKS, "risk_raised"),
])
def test_heart_story_preserves_measured_and_predicted_evidence(markers, risks, expected):
    from app.health_explanation.category_story import CategoryProfile, build_story

    detail = build_category_detail("heart_circulation", blood(markers) if markers else None, bio(risks) if risks else None)
    assert detail is not None
    story = build_story(detail, CategoryProfile(None, None, []), "member")
    assert "pumps blood" in story.understand_body
    assert set(story.biomarker_meanings) == {f.id for f in detail.findings if f.source_type == "measured"}
    prediction = next((f for f in detail.findings if f.source_type == "predicted_risk"), None)
    if expected:
        assert prediction is not None and prediction.status == expected
        assert prediction.id in story.risk_explanations
        assert "cannot diagnose" in story.bio_ai_limitations
    else:
        assert not story.risk_explanations
        assert "no Bio-AI assessment" in story.bio_ai_limitations
    assert story.monitoring and story.questions


def test_story_validates_model_blocks_and_only_sends_category_context(monkeypatch):
    import json
    from types import SimpleNamespace

    from app.contracts.unified_health import SelfReportedFactor
    from app.health_explanation.category_story import CategoryProfile, build_story
    from app.core import request_controls as controls

    monkeypatch.setattr(controls.request_controls, "_get", lambda key: None)
    monkeypatch.setattr(controls.request_controls, "_set", lambda *args: None)
    calls = []

    def complete(messages, **kwargs):
        payload = json.loads(messages[1]["content"])
        calls.append(payload)
        assert "member-secret" not in json.dumps(payload)
        assert payload["category"] == "heart_circulation"
        assert "HbA1c" not in json.dumps(payload)
        assert payload["age_band"] == "40s"
        assert payload["self_reported"][0]["source_type"] == "self_reported"
        return json.dumps({"block_ids": ["Invented diagnosis"], "actions": ["Unsafe advice"]})

    detail = build_category_detail("heart_circulation", blood(MEENA), bio(RISKS))
    profile = CategoryProfile("40s", "female", [
        SelfReportedFactor(key="diet_preference", label="diet pattern", value="Vegetarian"),
        SelfReportedFactor(key="physical_activity_frequency", label="physical activity", value="Rarely"),
    ])
    story = build_story(detail, profile, "member-secret", allow_model=True, client=SimpleNamespace(complete=complete))
    assert len(calls) == 1
    assert story == build_story(detail, profile, "member-secret")
    assert {"diet_preference", "physical_activity_frequency"} <= {step.action_id for step in story.improvement_plan}
    assert "Invented diagnosis" not in story.model_dump_json()
    assert any("answers alone" in line or "HDL" in line for line in story.influences)

    def complete_valid(messages, **kwargs):
        payload = json.loads(messages[1]["content"])
        return json.dumps({"block_ids": list(reversed(payload["approved_blocks"]))})

    reordered = build_story(detail, profile, "member-secret", allow_model=True, client=SimpleNamespace(complete=complete_valid))
    assert set(reordered.influences) == set(story.influences)
    assert reordered.influences != story.influences
    assert reordered.biomarker_meanings == story.biomarker_meanings
    assert reordered.risk_explanations == story.risk_explanations


def test_story_uses_only_current_relevant_answers_for_the_principal():
    from types import SimpleNamespace

    from app.auth.models import AuthenticatedPrincipal
    from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
    from app.contracts.user import UserProfile
    from app.health_explanation.category_story import load_profile

    def answer(key, value, date, subject="member"):
        return QuestionnaireAnswer(
            subject_id=subject, response_id=date, assessment_instance_id="assessment",
            question_id=key, question_key=key, question=key, value=value,
            response_type="choice", recorded_at=date,
        )

    instance = QuestionnaireInstance(assessment_instance_id="assessment", subject_id="member", answers=[
        answer("diet_preference", "Vegetarian", "2026-03-01"),
        answer("diet_preference", "Mixed", "2026-02-01"),
        answer("diet_preference", "Unrelated member", "2026-04-01", "other"),
        answer("unrelated_key", "private", "2026-04-01"),
    ])
    registry = SimpleNamespace(
        users=SimpleNamespace(get_profile=lambda principal: UserProfile(subject_id=principal.subject_id, display_name="Private")),
        questionnaires=SimpleNamespace(query=lambda principal, plan: [instance]),
    )
    profile = load_profile(AuthenticatedPrincipal(subject_id="member"), registry, ["ldl"])
    assert [(factor.key, factor.value) for factor in profile.factors] == [("diet_preference", "Vegetarian")]


def test_category_consent_keeps_existing_report_view_without_enriching(monkeypatch):
    from app.auth.models import AuthenticatedPrincipal
    from app.pipeline import unified_service

    def unexpected_profile(*args):
        pytest.fail("A member without current consent must not enter story enrichment")

    monkeypatch.setattr(unified_service.settings, "enable_llm", True)
    monkeypatch.setattr(type(unified_service.settings), "consent_enforced", lambda self: True)
    monkeypatch.setattr(unified_service, "_load", lambda *args: (blood(MEENA), bio(RISKS)))
    monkeypatch.setattr(unified_service, "load_profile", unexpected_profile)
    monkeypatch.setattr(unified_service, "has_current_consent", lambda db, subject: False)
    detail = unified_service.unified_category(AuthenticatedPrincipal(subject_id="member"), object(), "heart_circulation", object())
    assert detail.story is not None
    assert detail.story.self_reported == []
    assert detail.story.biomarker_meanings
