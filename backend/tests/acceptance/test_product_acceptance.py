"""Product acceptance tests on a synthetic report ("Meena").

Synthetic data only. The chat model is off in tests (tests/conftest.py), so the chat checks cover the
deterministic answers. They do not show how a live model words things, and nothing here is clinical review
or usability testing.

Meena has nine blood markers. Six are outside the supplied reference ranges and three are inside them:
  outside: HbA1c 5.9 %, fasting glucose 104 mg/dL, LDL 142, HDL 38, triglycerides 168, vitamin D 12.6
  inside:  haemoglobin 12.8, TSH 2.1, creatinine 0.8
Bio-AI, with the report's own labels: type 2 diabetes 72 High Risk, cardiac health 48 Increased Risk, fatty liver 12 Healthy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_unified_health import bio, blood, m  # noqa: E402

from app.biomarkers.unified_overview import build_unified_overview, prepare, urgent_threshold_hit  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline.unified_wording import rules_wording  # noqa: E402

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}

MEENA = [
    m("HbA1c", 5.9, 4.0, 5.7, "%"),
    m("Fasting Blood Glucose", 104, 70, 99, "mg/dL"),
    m("LDL Cholesterol", 142, 0, 100, "mg/dL"),
    m("HDL Cholesterol", 38, 50, 200, "mg/dL"),
    m("Triglycerides", 168, 0, 150, "mg/dL"),
    m("Vitamin D", 12.6, 30, 100, "ng/mL"),
    m("Haemoglobin", 12.8, 12, 15, "g/dL"),
    m("TSH", 2.1, 0.4, 4.0, "mIU/L"),
    m("Creatinine", 0.8, 0.6, 1.1, "mg/dL"),
]
MEENA_RISKS = [("type_2_diabetes", "High Risk", 72), ("cardiac_health", "Increased Risk", 48), ("nafld", "Healthy", 12)]


def meena():
    return prepare(blood(MEENA), bio(MEENA_RISKS))


def cards_by_id():
    cards, _parts, _prov = meena()
    return {c.id: c for c in cards}


# 1. Counts -----------------------------------------------------------------------------------------

def test_summary_counts_markers_not_areas():
    cards = cards_by_id()
    outside = sum(c.measured.outside_range for c in cards.values())
    within = sum(c.measured.within_range for c in cards.values())
    assert (outside, within, outside + within) == (6, 3, 9)
    # Areas are a different count from markers: sugar, heart and vitamins hold the six outside markers.
    areas_with_outside_markers = {cid for cid, c in cards.items() if c.measured.outside_range}
    assert areas_with_outside_markers == {"blood_sugar_metabolism", "heart_circulation", "vitamins_nutrition"}


def test_the_heart_risk_sits_with_the_heart_blood_tests():
    cards = cards_by_id()
    assert cards["heart_circulation"].risks.assessed == 1
    assert cards["blood_sugar_metabolism"].risks.assessed == 1


# 2. Prioritisation is not magnitude -----------------------------------------------------------------

def test_distance_from_the_range_does_not_change_a_status():
    slight = prepare(blood([m("SGPT (ALT)", 58, 7, 56)]), None)[0][0]
    far = prepare(blood([m("SGPT (ALT)", 300, 7, 56)]), None)[0][0]
    assert slight.status == far.status == "worth_attention"


def test_connected_evidence_not_distance_raises_the_sugar_area():
    cards = cards_by_id()
    # Vitamin D is the furthest from its range, yet only the area with a blood result and a raised risk together escalates.
    assert cards["vitamins_nutrition"].status == "worth_attention"
    assert cards["blood_sugar_metabolism"].status == "needs_closer_attention"


def test_a_guideline_urgent_threshold_raises_status_for_a_reason_that_is_named():
    overview = blood([m("HbA1c", 6.7, 4.0, 5.7, "%")])
    card = prepare(overview, None)[0][0]
    assert card.status == "needs_closer_attention"
    item = overview.results[0]
    assert urgent_threshold_hit(item) is True


def test_priority_order_is_tier_then_registry_order_and_the_model_cannot_change_it():
    from app.biomarkers.health_categories import category_for

    cards, parts, prov = meena()
    by_id = {c.id: c for c in cards}
    w = rules_wording(cards, parts, prov)
    ids = [p.category_id for p in w.priorities if p.tone == "attention"]
    closer = [i for i in ids if by_id[i].status == "needs_closer_attention"]
    rest = [i for i in ids if by_id[i].status != "needs_closer_attention"]
    assert ids == closer + rest  # the closer attention tier always comes first
    assert closer == sorted(closer, key=lambda c: category_for(c).order)
    assert rest == sorted(rest, key=lambda c: category_for(c).order)
    assert set(closer) == {"blood_sugar_metabolism", "heart_circulation"}  # each has a blood result and a raised risk


# 3. Predicted versus measured ----------------------------------------------------------------------

def test_predicted_risks_are_labelled_as_predictions_never_as_diagnoses():
    ov = build_unified_overview(blood(MEENA), bio(MEENA_RISKS))
    risks = [f for c in ov.categories for f in c.important_findings if f.source_type == "predicted_risk"]
    assert risks
    for f in risks:
        assert f.source_type == "predicted_risk"
        assert "diagnos" not in f.status_label.lower()
    cards, parts, prov = meena()
    w = rules_wording(cards, parts, prov, detail=True)
    text = " ".join(str(v) for entry in w.categories.values() for v in entry.values()).lower()
    for phrase in ("you have diabetes", "you have heart disease", "you are diabetic", "% chance"):
        assert phrase not in text


def test_the_raw_bio_ai_score_is_kept_with_its_classification():
    ov = build_unified_overview(blood(MEENA), bio(MEENA_RISKS))
    risk = next(f for c in ov.categories for f in c.important_findings if f.id == "risk:type_2_diabetes")
    assert risk.score == 72 and risk.classification == "High Risk"


# 4. Values, units and ranges are preserved -------------------------------------------------------------

def test_findings_carry_exact_values_units_ranges_and_dates():
    from app.biomarkers.unified_overview import build_category_detail

    detail = build_category_detail("vitamins_nutrition", blood(MEENA), bio(MEENA_RISKS))
    vit = next(f for f in detail.findings if f.source_type == "measured")
    assert (vit.value, vit.unit, vit.reference_low, vit.reference_high) == (12.6, "ng/mL", 30, 100)
    assert vit.measured_on is not None
    assert vit.status_label == "Well below range"


def test_blood_and_bio_ai_dates_are_kept_separate():
    _cards, _parts, prov = meena()
    assert prov.reports_linked is False
    assert str(prov.blood_report_date) == "2026-08-21" and str(prov.bio_ai_report_date) == "2026-08-25"
    assert prov.dates_differ is True


# 5. Chat: context, dates and honesty ---------------------------------------------------------------------

def _ask(message, conversation_id=None):
    body = {"message": message, **({"conversation_id": conversation_id} if conversation_id else {})}
    return client.post("/api/v1/chat", headers=H, json=body).json()


def test_a_follow_up_keeps_the_trusted_value_and_context():
    first = _ask("What is my vitamin D?")
    second = _ask("Why is it low?", first["conversation_id"])
    assert "12.6" in second["answer"] and "ng/mL" in second["answer"]
    fact = second["experience"]["key_facts"][0]
    assert (fact["canonical_key"], fact["value"], fact["unit"]) == ("vitamin_d", "12.6", "ng/mL")
    assert fact["source_date"] and fact["source_id"]


def test_a_follow_up_never_wraps_the_question_in_a_nonsense_template():
    first = _ask("What is my vitamin D?")
    second = _ask("Is it serious?", first["conversation_id"])
    for item in second["follow_ups"]:
        assert "mean in everyday terms" not in item["text"]


def test_a_date_with_no_report_is_said_plainly():
    answer = _ask("What is my HbA1c on 2020-01-01?")["answer"]
    assert "I don't have a result from 2020-01-01" in answer


def test_a_glucose_question_is_read_together_with_hba1c():
    answer = _ask("Is my fasting glucose ok?")["answer"]
    assert "HbA1c" in answer and "Fasting" in answer


def test_a_single_marker_answer_has_a_next_step_or_says_none_is_needed():
    answer = _ask("Is my ALT high?")["answer"].lower()
    assert "no action is needed because of" in answer or "doctor" in answer or "retest" in answer


# 6. Safety wording ------------------------------------------------------------------------------------

def test_no_unsupported_reassurance_for_a_high_ldl():
    answer = _ask("Is my LDL a problem?")["answer"].lower()
    assert "settle on" not in answer and "nothing that needs action" not in answer


def test_an_in_range_answer_does_not_claim_everything_is_fine():
    answer = _ask("Is my ALT high?")["answer"].lower()
    assert "nothing that needs action" not in answer and "everything is fine" not in answer


def test_low_vitamin_d_has_a_reasoned_next_step_not_a_generic_referral():
    answer = _ask("What is my latest Vitamin D?")["answer"].lower()
    assert "at your next visit" not in answer
    assert "whether you need treatment" in answer


def test_follow_ups_never_fall_back_to_stock_questions_for_a_person_with_results():
    from app.pipeline.followup_generator import FALLBACK

    stock = set(FALLBACK["none"])
    first = _ask("What is my vitamin D?")
    cid = first["conversation_id"]
    for question in ("Why is it low?", "Is it serious?", "Will sunlight help?"):
        turn = _ask(question, cid)
        shown = [item["text"] for item in turn["follow_ups"]]
        assert not stock.intersection(shown), (question, shown)
        assert len(shown) == len(set(shown)) and len(shown) <= 4


# 7. The report's own category labels (Bio-AI knowledge base, section 3.1) ----------------------------------

@pytest.mark.parametrize("label,raised", [
    ("Healthy", False), ("Increased Risk", True), ("High Risk", True), ("Very High Risk", True),
    ("healthy", False), ("increased", True), ("high", True), ("very high", True),
])
def test_report_labels_and_short_words_are_classified_the_same_way(label, raised):
    from app.biomarkers.risk_overview import _level

    assert (_level(label) == "raised") is raised


def test_a_high_risk_label_alone_needs_closer_attention_and_increased_risk_does_not():
    high = prepare(None, bio([("type_2_diabetes", "High Risk", 72)]))[0][0]
    increased = prepare(None, bio([("type_2_diabetes", "Increased Risk", 48)]))[0][0]
    assert high.status == "needs_closer_attention"
    assert increased.status == "worth_attention"


def test_increased_risk_is_the_lowest_raised_band_when_ordering_risks():
    from app.biomarkers.risk_overview import build_risk_overview  # noqa: F401  (ordering is read from the registry)
    from app.contracts.risk_status import risk_status_key
    import json
    from pathlib import Path

    order = json.loads((Path(__file__).resolve().parents[2] / "app/biomarkers/data/risk_registry_v1.json").read_text())["status_order"]
    assert order.index("very high") < order.index("high") < order.index("increased")
    assert risk_status_key("Very High Risk") == "very high"
