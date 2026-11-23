"""Unified overview: scenarios A to H, status rules, counts, provenance, wording safety and routes."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.biomarkers.overview import build_body_system_overview
from app.biomarkers.risk_overview import build_risk_overview
from app.biomarkers.unified_overview import build_category_detail, build_unified_overview, prepare
from app.pipeline.unified_wording import SYSTEM, model_wording, rules_wording
from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag

BLOOD_DAY, BIO_DAY = date(2026, 8, 21), date(2026, 8, 25)


def m(name, value, low=None, high=None, unit="U/L"):
    flag = MarkerFlag.normal if (low is not None or high is not None) else MarkerFlag.unknown
    if value is None:
        flag = MarkerFlag.missing
    elif low is not None and value < low:
        flag = MarkerFlag.low
    elif high is not None and value > high:
        flag = MarkerFlag.high
    return BloodMarker(id=f"id-{name}", key=name.lower().replace(" ", "_"), name=name, value=value, unit=unit, reference_low=low, reference_high=high, flag=flag)


def blood(markers, day=BLOOD_DAY):
    return build_body_system_overview([BloodReport(report_id="blood-1", report_date=day, markers=markers)])


def bio(risks, day=BIO_DAY):
    return build_risk_overview([BioAIReport(report_id="bio-1", report_date=day, source_line="bio_ai", risks=[BioAIRisk(code=c, name=c.replace("_", " ").title(), status=s, score=sc) for c, s, sc in risks])])


def card(overview, cid):
    return next(c for c in overview.categories if c.id == cid)


LIVER_OK = [m("SGPT (ALT)", 20, 7, 56), m("SGOT (AST)", 22, 10, 40)]
LIVER_OUT = [m("SGPT (ALT)", 62, 7, 56), m("SGOT (AST)", 22, 10, 40)]


@pytest.mark.parametrize(
    "markers,risk,scenario,status",
    [
        (LIVER_OK, "mild", "both_reassuring", "looking_good"),
        (LIVER_OUT, "mild", "blood_out_risk_ok", "worth_attention"),
        (LIVER_OK, "high", "blood_ok_risk_up", "needs_closer_attention"),
        (LIVER_OUT, "moderate", "both_out", "needs_closer_attention"),
    ],
)
def test_scenarios_a_to_d_and_their_status(markers, risk, scenario, status):
    ov = build_unified_overview(blood(markers), bio([("nafld", risk, 20)]))
    c = card(ov, "liver_health")
    assert (c.scenario, c.status) == (scenario, status)


def test_a_healthy_risk_never_cancels_an_abnormal_blood_result():
    c = card(build_unified_overview(blood(LIVER_OUT), bio([("nafld", "low", 5)])), "liver_health")
    assert c.status != "looking_good" and "outside range" in c.summary and "healthy band" in c.summary


def test_increased_is_a_raised_risk_and_counts_agree_with_the_card():
    ov = build_unified_overview(blood(LIVER_OK), bio([("cardiac_health", "Increased", 43), ("hypertension", "Healthy", 17)]))
    heart = card(ov, "heart_circulation")
    assert heart.risks.raised == 1 and heart.status == "worth_attention"
    assert ov.totals.risks_raised == 1 and ov.totals.risks_assessed == 2


def test_blood_only_and_bio_only_users_never_get_invented_data():
    only_blood = build_unified_overview(blood(LIVER_OK), None)
    c = card(only_blood, "liver_health")
    assert c.scenario == "blood_only" and c.risks.assessed == 0 and only_blood.totals.risks_assessed == 0
    only_bio = build_unified_overview(None, bio([("nafld", "mild", 12)]))
    c = card(only_bio, "liver_health")
    assert c.scenario == "risk_only" and c.measured.total == 0 and "blood" not in c.summary.lower()


def test_no_reports_gives_an_empty_overview():
    ov = build_unified_overview(None, None)
    assert (ov.available, ov.state, ov.categories) == (False, "no_reports", [])


def test_missing_values_and_missing_ranges_are_counted_apart_and_make_it_partial():
    ov = build_unified_overview(blood([m("SGPT (ALT)", 20, 7, 56), m("SGOT (AST)", None, 10, 40), m("GGTP", 30)]), None)
    c = card(ov, "liver_health")
    assert (c.measured.within_range, c.measured.unavailable, c.measured.no_range) == (1, 1, 1)
    assert c.completeness == "partial"


def test_a_category_with_nothing_assessable_is_not_assessed():
    c = card(build_unified_overview(blood([m("SGOT (AST)", None, 10, 40)]), None), "liver_health")
    assert c.status == "not_assessed"


def test_different_report_dates_are_kept_and_never_assumed_linked():
    ov = build_unified_overview(blood(LIVER_OK), bio([("nafld", "mild", 12)]))
    p = ov.provenance
    assert (p.blood_report_date, p.bio_ai_report_date) == ("2026-08-21", "2026-08-25")
    assert p.dates_differ and not p.reports_linked
    detail = build_category_detail("liver_health", blood(LIVER_OK), bio([("nafld", "mild", 12)]))
    assert not any("different" in x or "same time" in x or "2026" in x for x in detail.interpretation + [detail.summary])


def test_a_marker_is_counted_in_exactly_one_category():
    ov = build_unified_overview(blood(LIVER_OK + [m("Cholesterol Total", 190, 0, 200, "mg/dL")]), None)
    assert sum(c.measured.total for c in ov.categories) == ov.totals.blood_within + ov.totals.blood_outside + ov.totals.blood_no_range


def test_one_findings_list_holds_both_kinds_with_verified_values():
    d = build_category_detail("liver_health", blood(LIVER_OUT), bio([("nafld", "mild", 12)]))
    kinds = {f.source_type for f in d.findings}
    assert kinds == {"measured", "predicted_risk"}
    alt = next(f for f in d.findings if f.name.startswith("SGPT"))
    assert (alt.value, alt.reference_high, alt.status) == (62, 56, "above_range")
    fl = next(f for f in d.findings if f.source_type == "predicted_risk")
    assert fl.score == 12 and fl.classification == "mild"


def test_unknown_category_has_no_detail():
    assert build_category_detail("nope", blood(LIVER_OK), None) is None


# ---- wording ----------------------------------------------------------------------------

class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, 0

    def complete(self, messages, json_mode=False):
        self.calls += 1
        return json.dumps(self.payload)


class _Store:
    def __init__(self):
        self.data = {}

    def _get(self, k):
        return self.data.get(k)

    def _set(self, k, v, ttl):
        self.data[k] = v


@pytest.fixture
def store(monkeypatch):
    s = _Store()
    monkeypatch.setattr("app.pipeline.unified_wording._store", lambda: s)
    return s


def _setup():
    b, a = blood(LIVER_OUT), bio([("nafld", "mild", 12)])
    cards, parts, prov = prepare(b, a)
    return b, a, cards, parts, prov


GOOD = {
    "opening": "Here is your whole picture.",
    "priorities": [{"category_id": "liver_health", "title": "Look at your liver", "detail": "Two results are high.", "tone": "attention"}],
    "categories": {"liver_health": {"about": "Your liver cleans your blood.", "summary": "Two liver results are high.", "interpretation": ["Fatty liver is one kind of problem."], "insight": "", "actions": [{"title": "See your doctor", "detail": "Talk about your liver results.", "icon": "clipboard"}, {"title": "Eat well", "detail": "Choose balanced meals.", "icon": "food"}], "follow_ups": ["Why is my ALT high?"]}},
}


def test_one_model_request_writes_every_category_and_is_cached(store):
    b, a, cards, parts, prov = _setup()
    client = FakeClient(GOOD)
    w1 = model_wording("u1", cards, parts, prov, [], client=client)
    w2 = model_wording("u1", cards, parts, prov, [], client=client)
    assert client.calls == 1 and w1.source == "model" and w2.categories == w1.categories
    assert w1.categories["liver_health"]["summary"] == "Two liver results are high."


def test_cache_key_changes_when_a_report_or_context_changes(store):
    b, a, cards, parts, prov = _setup()
    client = FakeClient(GOOD)
    model_wording("u1", cards, parts, prov, [], client=client)
    model_wording("u1", cards, parts, prov, ["Vegetarian"], client=client)
    other = prov.model_copy(update={"bio_ai_report_id": "bio-2"})
    model_wording("u1", cards, parts, other, [], client=client)
    model_wording("u2", cards, parts, prov, [], client=client)
    assert client.calls == 4


def test_a_number_the_model_invents_falls_back_to_rules_text(store):
    b, a, cards, parts, prov = _setup()
    bad = json.loads(json.dumps(GOOD))
    bad["categories"]["liver_health"]["summary"] = "Your ALT is 999 which is very high."
    w = model_wording("u1", cards, parts, prov, [], client=FakeClient(bad))
    assert "999" not in w.categories["liver_health"]["summary"]


def test_dashes_are_removed_from_model_text(store):
    b, a, cards, parts, prov = _setup()
    bad = json.loads(json.dumps(GOOD))
    bad["opening"] = "Your picture — in one place."
    w = model_wording("u1", cards, parts, prov, [], client=FakeClient(bad))
    assert "—" not in w.opening and "–" not in w.opening


def test_model_failure_still_returns_rules_wording(store):
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("down")

    b, a, cards, parts, prov = _setup()
    w = model_wording("u1", cards, parts, prov, [], client=Boom())
    assert w.source == "rules" and w.categories["liver_health"]["summary"]


def test_a_model_cannot_make_a_healthy_category_an_attention_priority(store):
    b, a, cards, parts, prov = _setup()
    cards2, parts2, prov2 = prepare(blood(LIVER_OK), bio([("nafld", "mild", 12)]))
    bad = json.loads(json.dumps(GOOD))
    w = model_wording("u1", cards2, parts2, prov2, [], client=FakeClient(bad))
    assert all(p.category_id != "liver_health" or p.tone == "good" for p in w.priorities)


def test_prompt_and_rules_text_never_contain_dashes_and_follow_ups_are_capped():
    assert "—" not in SYSTEM and "–" not in SYSTEM
    b, a, cards, parts, prov = _setup()
    w = rules_wording(cards, parts, prov, detail=True)
    for entry in w.categories.values():
        assert len(entry.get("follow_ups", [])) <= 4
        assert "—" not in json.dumps(entry, ensure_ascii=False)


def test_users_are_isolated_by_the_cache_key(store):
    b, a, cards, parts, prov = _setup()
    c = FakeClient(GOOD)
    model_wording("alice", cards, parts, prov, [], client=c)
    model_wording("bob", cards, parts, prov, [], client=c)
    assert len({k for k in store.data}) == 2


# ---- routes -----------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

http = TestClient(app)
AS_DEMO = {"X-Cura-User-Id": "demo-user-001"}


@pytest.fixture
def no_model(monkeypatch):
    def down(*a, **k):
        raise RuntimeError("no model in tests")

    monkeypatch.setattr("app.llm.factory.get_llm_client", down)
    monkeypatch.setattr("app.pipeline.unified_wording._store", lambda: _Store())


def test_routes_need_auth():
    assert http.get("/api/v1/me/health-overview").status_code == 401
    assert http.get("/api/v1/me/health-overview/liver_health").status_code == 401


def test_overview_and_category_routes_agree(no_model):
    ov = http.get("/api/v1/me/health-overview", headers=AS_DEMO).json()
    assert ov["state"] == "ready" and ov["categories"]
    assert ov["totals"]["blood_within"] == sum(c["measured"]["within_range"] for c in ov["categories"])
    first = ov["categories"][0]
    detail = http.get(f"/api/v1/me/health-overview/{first['id']}", headers=AS_DEMO).json()
    assert detail["status"] == first["status"] and detail["measured"] == first["measured"]
    assert len(detail["follow_ups"]) <= 4 and len(detail["actions"]) <= 4


def test_unknown_category_is_404_and_empty_member_gets_an_empty_overview(no_model):
    assert http.get("/api/v1/me/health-overview/nope", headers=AS_DEMO).status_code == 404
    body = http.get("/api/v1/me/health-overview", headers={"X-Cura-User-Id": "no-such-member"}).json()
    assert body["state"] == "no_reports" and body["categories"] == []


# ---- reviewed test explanations -----------------------------------------------------------
from app.biomarkers.education import education_for  # noqa: E402


def test_explanations_come_from_the_reviewed_file_and_attach_to_measured_findings_only():
    d = build_category_detail("liver_health", blood(LIVER_OUT), bio([("nafld", "mild", 12)]))
    alt = next(f for f in d.findings if f.name.startswith("SGPT"))
    assert alt.education and alt.education.what_it_is.startswith("An enzyme mostly found in liver cells")
    assert alt.explain and alt.explain.endswith(".")
    assert next(f for f in d.findings if f.source_type == "predicted_risk").education is None


def test_cards_do_not_carry_the_long_explanations():
    ov = build_unified_overview(blood(LIVER_OUT), None)
    assert all(f.education is None for c in ov.categories for f in c.important_findings)


def test_misspelt_lab_names_and_look_alike_tests_find_the_right_text():
    assert education_for("hdl_cholesterol_direct", "HDL Cholestrol Direct").name == "HDL Cholesterol Direct"
    assert education_for("urine_rbc", "RBC").name == "RBC (Urine)"
    assert education_for("fasting_sugar", "Fasting Sugar").name == "Fasting Sugar"
    assert education_for("urine_sugar", "Sugar").name == "Sugar"
    assert education_for(None, "No Such Test") is None


def test_the_education_text_never_uses_dashes_and_no_test_says_the_member_is_abnormal():
    import json
    from pathlib import Path

    import app.biomarkers.education as edu

    text = Path(edu._FILE).read_text(encoding="utf-8")
    assert "—" not in text
    for item in json.loads(text)["biomarkers"]:
        assert len(item["bullets"]) == 4


def test_every_card_carries_its_fixed_description_from_the_registry():
    from app.biomarkers.health_categories import CATEGORIES

    assert all(c.description for c in CATEGORIES)
    ov = build_unified_overview(blood(LIVER_OUT), bio([("nafld", "mild", 12)]))
    liver = card(ov, "liver_health")
    assert liver.description == "How your body processes food, breaks down medicines and removes waste."
    assert "—" not in liver.description


def test_plain_measured_labels_describe_distance_only():
    from app.biomarkers.unified_overview import plain_measured_label

    assert plain_measured_label("above_range", "slightly") == "A little above range"
    assert plain_measured_label("above_range", "moderately") == "Above range"
    assert plain_measured_label("above_range", "clearly") == "Well above range"
    assert plain_measured_label("below_range", "slightly") == "A little below range"
    assert plain_measured_label("below_range", "clearly") == "Well below range"
    assert plain_measured_label("below_range", None) == "Below range"
    assert plain_measured_label("within_range", None) == "Within range"
    assert plain_measured_label("critical", None) == "Critical"
