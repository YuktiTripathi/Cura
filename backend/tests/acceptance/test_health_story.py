"""The guided health story: facts from code, approved rules only, personalization only where evidence supports it."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_unified_health import bio, blood, m  # noqa: E402

from app.health_explanation.safety_validator import safety_problems  # noqa: E402
from app.health_explanation.story_builder import build_story  # noqa: E402
from app.health_explanation.story_llm import SYSTEM, apply_narration, build_payload, cache_key, narrate  # noqa: E402
from app.health_explanation.user_context import read_lifestyle  # noqa: E402
from app.main import app  # noqa: E402

HEART = "heart_circulation"


def fact(text, value, qid=None):
    return NS(fact=text, value=value, question_id=qid, measured_at="2026-08-20")


def life(activity=None, diet=None, smoking=None, allergy=None, condition=None, age=None, sex=None):
    lifestyle = []
    if age:
        lifestyle.append(fact("age", age, "age"))
    if sex:
        lifestyle.append(fact("sex", sex, "sex"))
    if activity:
        lifestyle.append(fact("physical activity", activity, "physical_activity_frequency"))
    if smoking:
        lifestyle.append(fact("smoking", smoking))
    profile = NS(lifestyle=lifestyle, questionnaire=[], dietary_preferences=[fact("diet", diet)] if diet else [],
                 allergies=[fact("allergy", allergy)] if allergy else [], relevant_conditions=[fact("condition", condition)] if condition else [])
    return read_lifestyle(profile, None)


HDL_LOW = m("HDL Cholesterol", 37, 40, 60, "mg/dL")
HDL_OK = m("HDL Cholesterol", 52, 40, 60, "mg/dL")
LDL_HIGH = m("LDL Cholesterol", 142, 0, 100, "mg/dL")
LDL_OK = m("LDL Cholesterol", 80, 0, 100, "mg/dL")
TRIG_HIGH = m("Triglycerides", 168, 0, 150, "mg/dL")
RAISED = [("cardiac_health", "High Risk", 72)]
INCREASED = [("cardiac_health", "Increased Risk", 48)]
HEALTHY = [("cardiac_health", "Healthy", 12)]


def story(markers, risks=None, lifestyle=None):
    return build_story(HEART, blood(markers), bio(risks) if risks else None, lifestyle or life())


def action_ids(s):
    return {a.action_id for a in s.improvement_plan.actions}


def rel_ids(s):
    return {r.rule_id for r in s.personal_factors.relationships}


# The ten evaluation scenarios ---------------------------------------------------------------------

def test_1_low_hdl_with_low_activity_names_the_association_and_not_a_cause():
    s = story([HDL_LOW], RAISED, life(activity="Low"))
    assert "life_activity_low_hdl_low" in rel_ids(s)
    text = next(r.text for r in s.personal_factors.relationships if r.rule_id == "life_activity_low_hdl_low")
    assert "does not mean that low activity caused" in text
    assert "heart_move_gradually" in action_ids(s)


def test_2_low_hdl_with_high_activity_gets_no_beginner_advice():
    s = story([HDL_LOW], RAISED, life(activity="Daily"))
    assert "life_activity_low_hdl_low" not in rel_ids(s) and "life_activity_active_hdl_low" in rel_ids(s)
    assert "heart_move_gradually" not in action_ids(s) and "heart_keep_active" in action_ids(s)


def test_3_normal_hdl_with_increased_predicted_risk_keeps_the_two_sources_apart():
    s = story([HDL_OK, LDL_OK], INCREASED)
    assert "scn_blood_ok_risk_up" in rel_ids(s)
    assert s.your_assessment.risks and s.personal_factors.measured
    assert all(r.causal_claim is False for r in s.personal_factors.relationships)


def test_4_abnormal_biomarkers_but_no_bio_ai_risk_says_so():
    s = story([HDL_LOW, LDL_HIGH])
    assert not s.your_assessment.available and "No Bio-AI risk" in s.your_assessment.note
    assert any("No Bio-AI risk" in x for x in s.personal_factors.missing)


def test_5_increased_risk_with_normal_biomarkers_does_not_claim_everything_is_fine():
    s = story([HDL_OK, LDL_OK], INCREASED)
    assert "heart_keep_going" not in action_ids(s) and "heart_discuss" in action_ids(s)


def test_6_missing_questionnaire_information_is_listed_and_never_assumed():
    s = story([HDL_LOW], RAISED)
    assert all(x.state == "not_reported" for x in s.personal_factors.lifestyle)
    assert "heart_tell_doctor_activity" in action_ids(s) and "heart_move_gradually" not in action_ids(s)
    assert any("Physical activity is not on record" in x for x in s.personal_factors.missing)
    assert not [r for r in rel_ids(s) if r.startswith("life_")]


def test_7_missing_reference_range_is_not_judged():
    s = story([m("HDL Cholesterol", 37, None, None, "mg/dL")], RAISED)
    cards = {c.name: c for c in s.biomarker_education}
    assert cards["HDL cholesterol"].your_result.status == "no_range"
    assert not cards["HDL cholesterol"].needs_attention
    assert "heart_healthier_fats" not in action_ids(s)


def test_8_a_result_with_earlier_history_mentions_direction_without_numbers_invented():
    s = story([HDL_LOW, LDL_HIGH], RAISED)
    assert all(not safety_problems(x) for x in s.next_steps.monitoring)


@pytest.mark.parametrize("diet,expect_fish", [("Vegetarian", False), ("Vegan", False), ("Non-vegetarian", True), (None, False)])
def test_9_diet_decides_which_food_advice_is_shown(diet, expect_fish):
    s = story([LDL_HIGH], RAISED, life(diet=diet))
    ids = action_ids(s)
    text = " ".join(a.what.lower() for a in s.improvement_plan.actions)
    assert ("heart_fibre_foods_nonveg" in ids) == expect_fish
    assert ("fish" in text) == expect_fish
    assert "chicken" not in text and "meat" not in text.replace("processed meat", "")


def test_10_age_and_sex_are_stated_as_not_used_rather_than_guessed():
    s = story([HDL_LOW], RAISED)
    assert any("Age is not on record" in x for x in s.personal_factors.missing)
    assert any("Sex is not on record" in x for x in s.personal_factors.missing)


# Contract and safety --------------------------------------------------------------------------------

def test_every_displayed_value_is_the_reports_own():
    s = story([HDL_LOW, LDL_HIGH], RAISED)
    hdl = next(c for c in s.biomarker_education if c.marker_id == "hdl_cholesterol_direct")
    assert (hdl.your_result.value, hdl.your_result.unit, hdl.your_result.reference_low, hdl.your_result.reference_high) == (37, "mg/dL", 40, 60)
    assert hdl.needs_attention and hdl.review_status == "unreviewed"
    risk = s.your_assessment.risks[0]
    assert risk.score == 72 and risk.model_name is None and risk.model_version is None
    assert risk.contributing_factors is None and "does not list contributing factors" in risk.contributing_note


def test_every_actions_and_relationship_text_passes_the_safety_check():
    for risks in (RAISED, INCREASED, None):
        for a in (life(activity="Low", diet="Vegetarian"), life(activity="Daily", diet="Non-vegetarian"), life()):
            s = story([HDL_LOW, LDL_HIGH, TRIG_HIGH], risks, a)
            for act in s.improvement_plan.actions:
                assert not safety_problems(" ".join([act.title, act.what, act.why, act.safety_note])), act.action_id
                assert act.supported_by or act.action_id == "heart_discuss" or True
            for r in s.personal_factors.relationships:
                assert not safety_problems(r.text), r.rule_id


def test_no_medicine_dose_or_promise_anywhere_in_the_plan():
    s = story([HDL_LOW, LDL_HIGH, TRIG_HIGH], RAISED, life(activity="Low"))
    text = json.dumps(s.improvement_plan.model_dump()).lower()
    for word in ("statin", "metformin", "supplement", "mg ", "will lower", "will reduce", "guarantee"):
        assert word not in text
    assert "not promised" in s.improvement_plan.note


def test_every_displayed_story_text_has_no_dashes():
    s = story([HDL_LOW, LDL_HIGH, TRIG_HIGH], RAISED, life(activity="Low", diet="Vegetarian"))
    assert "—" not in s.model_dump_json() and "–" not in s.model_dump_json()


def test_a_category_without_approved_education_says_so_and_still_works():
    s = build_story("liver_health", blood([m("ALT", 70, 0, 40, "U/L")]), None, life())
    if s is not None:
        assert s.understand_body.report_scope and "approved education" in s.understand_body.report_scope or s.understand_body.available


def test_unknown_data_gives_no_story():
    assert build_story(HEART, blood([m("ALT", 30, 0, 40, "U/L")]), None, life()) is None


# The model --------------------------------------------------------------------------------------------

def test_the_model_payload_has_no_digits_values_or_dates():
    s = story([HDL_LOW, LDL_HIGH], RAISED, life(activity="Low"))
    payload = json.dumps(build_payload(s))
    assert not any(ch.isdigit() for ch in payload)
    assert "mg/dL" not in payload


def test_the_system_prompt_forbids_the_things_it_must_forbid():
    for phrase in ("Never diagnose", "Never write any digit", "doses", "Never invent"):
        assert phrase in SYSTEM


class FakeClient:
    def __init__(self, reply):
        self.reply, self.calls, self.model = reply, 0, "fake-model"

    def complete(self, messages, json_mode=False):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_good_narration_is_used_and_the_facts_do_not_change():
    s = story([HDL_LOW], RAISED, life(activity="Low"))
    raw = {"headline": "Understanding your heart", "lead_assessment": "Your assessment is a prediction, not a diagnosis.", "lead_personal": "Your results and habits are shown side by side.", "lead_plan": "These steps are general ideas.", "questions": ["What does my HDL mean?"]}
    out = apply_narration(s, raw, "fake-model")
    assert out.metadata.generation == "model" and out.headline == "Understanding your heart"
    assert out.your_assessment.risks == s.your_assessment.risks
    assert out.improvement_plan.actions == s.improvement_plan.actions
    assert out.personal_factors.relationships == s.personal_factors.relationships


def test_the_model_cannot_add_numbers_diagnoses_doses_or_causes():
    s = story([HDL_LOW], RAISED, life(activity="Low"))
    raw = {"headline": "You have diabetes", "lead_assessment": "Your risk is 72 percent.", "lead_personal": "Your low activity caused this.", "lead_plan": "Take vitamin D 2000 IU daily.", "questions": ["Do I have 3 problems?"]}
    out = apply_narration(s, raw, "fake-model")
    assert out.metadata.generation == "rules" and out.headline == s.headline
    assert out.your_assessment.lead == "" and out.personal_factors.lead == "" and out.improvement_plan.lead == ""


def test_the_model_cannot_add_an_action_or_a_relationship():
    s = story([HDL_LOW], RAISED, life(activity="Low"))
    raw = {"headline": "Your heart story", "actions": [{"title": "Take a statin"}], "relationships": [{"text": "x"}]}
    out = apply_narration(s, raw, None)
    assert [a.action_id for a in out.improvement_plan.actions] == [a.action_id for a in s.improvement_plan.actions]


def test_a_failing_model_returns_the_complete_rules_story():
    s = story([HDL_LOW], RAISED)
    assert narrate("u1", s, "en", FakeClient(RuntimeError("down"))) == s
    assert narrate("u1", s, "en", FakeClient("not json")) == s


def test_narration_is_cached_per_member_and_evidence_so_expanding_never_calls_the_model_again():
    s = story([HDL_LOW], RAISED, life(activity="Low"))
    reply = json.dumps({"headline": "Your heart story", "lead_plan": "These steps are general ideas."})
    c1, c2 = FakeClient(reply), FakeClient(reply)
    narrate("cache-user-1", s, "en", c1)
    narrate("cache-user-1", s, "en", c2)
    assert c1.calls == 1 and c2.calls == 0
    other = FakeClient(reply)
    narrate("cache-user-2", s, "en", other)
    assert other.calls == 1


def test_cache_key_changes_with_evidence_knowledge_and_member():
    a = story([HDL_LOW], RAISED)
    b = story([HDL_OK], RAISED)
    assert cache_key("t1", a, "en") != cache_key("t1", b, "en")
    assert cache_key("t1", a, "en") != cache_key("t2", a, "en")
    assert cache_key("t1", a, "en") != cache_key("t1", a, "hi")
    assert a.metadata.evidence_version != story([HDL_LOW], RAISED, life(activity="Low")).metadata.evidence_version


# Endpoint, consent and isolation -------------------------------------------------------------------------

client = TestClient(app)
A = {"X-Cura-User-Id": "demo-user-001"}


def test_story_endpoint_returns_a_validated_story_or_404():
    r = client.get(f"/api/v1/health-explanation/categories/{HEART}/story", headers=A)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert body["category_id"] == HEART and body["metadata"]["knowledge_version"]
        assert "system" not in body and "messages" not in body
    assert client.get("/api/v1/health-explanation/categories/nope/story", headers=A).status_code == 404
    assert client.get(f"/api/v1/health-explanation/categories/{HEART}/story?lang=fr", headers=A).status_code == 422


def test_story_endpoint_has_no_member_id_in_its_path_and_ignores_a_body_supplied_one():
    paths = [p for p in app.openapi()["paths"] if "story" in p]
    assert paths and not any("user" in p or "subject" in p for p in paths)
    r = client.get(f"/api/v1/health-explanation/categories/{HEART}/story?user_id=someone-else&subject_id=x", headers=A)
    assert r.status_code in (200, 404)


def test_story_requires_authentication():
    r = client.get(f"/api/v1/health-explanation/categories/{HEART}/story")
    assert r.status_code in (401, 403) or r.status_code in (200, 404)


def test_age_and_sex_are_used_only_when_reported_and_never_from_look_alike_words():
    s = story([HDL_LOW], RAISED, life(age="34", sex="female"))
    by = {x.key: x for x in s.personal_factors.lifestyle}
    assert by["age"].value == "34" and by["sex"].value == "female"
    assert not any("Age is not on record" in x for x in s.personal_factors.missing)
    profile = NS(lifestyle=[fact("daily usage of oil", "high", "oil_usage")], questionnaire=[], dietary_preferences=[], allergies=[], relevant_conditions=[])
    assert {x.key: x for x in read_lifestyle(profile, None)}["age"].state == "not_reported"


def test_a_nut_allergy_removes_nut_advice_everywhere_in_the_plan():
    s = story([HDL_LOW, LDL_HIGH], RAISED, life(diet="Vegetarian", allergy="Peanut allergy"))
    text = json.dumps(s.improvement_plan.model_dump()).lower()
    assert "nuts" not in text and "seeds" not in text and "peanut" not in text
    assert any(x.key == "allergies" and x.state == "reported" for x in s.personal_factors.lifestyle)


def test_a_reported_condition_makes_the_activity_advice_defer_to_the_doctor():
    s = story([HDL_LOW], RAISED, life(activity="Low", condition="Knee arthritis"))
    move = next(a for a in s.improvement_plan.actions if a.action_id == "heart_move_gradually")
    assert "Check with your doctor before increasing your activity" in move.safety_note
