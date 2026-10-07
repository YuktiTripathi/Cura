"""Answer director: understand broadly, select narrowly.

Covers questionnaire-as-reasoning-context, information budgets, the evidence payload that
replaces the full record dump, presentation policy, and a 0-20 response-quality score.
"""

import json
import re

import pytest

from app.auth.models import AuthenticatedPrincipal
from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse
from app.contracts.questionnaire import QuestionnaireAnswer, QuestionnaireInstance
from app.pipeline.answer_evidence import BUDGETS, build_answer_evidence, prioritize_findings
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.presentation_policy import apply_presentation_policy
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan
from app.pipeline.questionnaire_relevance import (
    LEVER,
    SUPPORTIVE,
    relevant_questionnaire_keys,
    select_questionnaire_context,
    should_enrich_with_questionnaire,
    stance_for,
)
from app.providers.registry import build_registry

DEMO = AuthenticatedPrincipal(subject_id="demo-user-001")

SEDENTARY = {
    "sleeping_hours": "6-7 hours",
    "physical_activity_frequency": "Rarely",
    "exercise_level": "Light",
    "exercise_frequency_week": "0-1 days",
    "daily_active_duration": "Less than 30 minutes",
    "sitting_hours": "More than 8 hours",
    "diet_preference": "Vegetarian",
    "food_groups": "Mostly refined grains",
    "healthy_breakfast_frequency": "Rarely",
    "fresh_fruit_frequency": "Weekly",
    "fresh_vegetable_frequency": "Daily",
    "alcohol_frequency": "Never",
    "tobacco_frequency": "Never",
}
ACTIVE = {
    **SEDENTARY,
    "physical_activity_frequency": "Daily",
    "exercise_level": "Moderate",
    "exercise_frequency_week": "5-6 days",
    "daily_active_duration": "More than 60 minutes",
}


def _questionnaire(answers: dict, recorded_at: str = "2026-09-01") -> list[QuestionnaireInstance]:
    rows = [
        QuestionnaireAnswer(
            response_id=f"r{i}", assessment_instance_id="qa", question_id=f"q{i}", question_key=key,
            question=key.replace("_", " "), value=value, response_type="text", recorded_at=recorded_at,
            subject_id="demo-user-001",
        )
        for i, (key, value) in enumerate(answers.items())
    ]
    return [QuestionnaireInstance(assessment_instance_id="qa", subject_id="demo-user-001", recorded_at=recorded_at, answers=rows)]


def _context(message: str, answers: dict | None = None):
    plan = build_query_plan(message)
    ctx = ContextBuilder(build_registry()).build(DEMO, plan)
    if answers is not None:
        ctx.questionnaire = _questionnaire(answers)
    return ctx


def _evidence(message: str, answers: dict | None = None, recent: list[str] | None = None):
    ctx = _context(message, answers)
    if recent:
        ctx.recent_user_messages = recent
    return ctx, build_answer_evidence(ctx, message)


# ------------------------------------------------------------ questionnaire relevance


def test_hba1c_guidance_uses_activity_questionnaire_when_relevant():
    selection = select_questionnaire_context(
        "Why is my HbA1c high?", entities=["hba1c"], questionnaire=_questionnaire(SEDENTARY)
    )
    assert any(key in selection.selected_keys for key in ("physical_activity_frequency", "exercise_frequency_week", "sitting_hours"))
    assert len(selection.selected_keys) <= 4


def test_triglyceride_guidance_considers_alcohol_activity_and_diet():
    keys = relevant_questionnaire_keys(["triglycerides"])
    assert keys[0] == "alcohol_frequency"
    assert "physical_activity_frequency" in keys or "exercise_frequency_week" in keys
    assert "food_groups" in keys or "diet_preference" in keys


def test_vitamin_d_lookup_does_not_fetch_or_display_questionnaire():
    assert relevant_questionnaire_keys(["vitamin_d"]) == []
    assert not should_enrich_with_questionnaire(
        "What is my Vitamin D?", personal=True, entities=["vitamin_d"], domains=[]
    )
    _, evidence = _evidence("What is my Vitamin D?", SEDENTARY)
    assert evidence.questionnaire_facts == []
    assert len(evidence.primary_facts) == 1


def test_simple_value_lookup_never_sends_questionnaire():
    assert not should_enrich_with_questionnaire("What is my HbA1c?", personal=True, entities=["hba1c"], domains=[])
    assert should_enrich_with_questionnaire("Why is my HbA1c high?", personal=True, entities=["hba1c"], domains=[])


def test_already_exercising_user_is_not_told_to_start_exercising():
    selection = select_questionnaire_context(
        "Why are my triglycerides high?", entities=["triglycerides"], questionnaire=_questionnaire(ACTIVE)
    )
    activity = [s for s in selection.signals if s.label == "physical activity"]
    assert activity and activity[0].stance == SUPPORTIVE
    assert "do not tell the member to start" in activity[0].for_model()["use"]


def test_sedentary_answers_are_levers_not_causes():
    selection = select_questionnaire_context(
        "Why is my HbA1c high?", entities=["hba1c"], questionnaire=_questionnaire(SEDENTARY)
    )
    levers = [s for s in selection.signals if s.stance == LEVER]
    assert levers
    for signal in levers:
        # The model is told explicitly that a lever is not a cause.
        assert "never say it caused" in signal.for_model()["use"]


def test_recent_user_statement_overrides_stale_questionnaire():
    selection = select_questionnaire_context(
        "Why is my HbA1c high?",
        entities=["hba1c"],
        questionnaire=_questionnaire(SEDENTARY),
        recent_messages=["I work out 5 days a week now"],
    )
    activity = [s for s in selection.signals if s.label == "physical activity"]
    assert activity and activity[0].source == "recent_conversation"
    assert activity[0].stance == SUPPORTIVE
    assert selection.overridden_keys


def test_missing_questionnaire_is_handled_quietly():
    selection = select_questionnaire_context("Why is my HbA1c high?", entities=["hba1c"], questionnaire=None)
    assert selection.signals == []
    _, evidence = _evidence("Why is my HDL low?", answers=None)
    payload = evidence.payload()
    assert "questionnaire" not in json.dumps(payload.get("uncertainty", [])).lower()


def test_questionnaire_selection_is_capped():
    selection = select_questionnaire_context(
        "How am I doing overall?", entities=["hba1c", "triglycerides", "ldl", "nafld"], questionnaire=_questionnaire(SEDENTARY)
    )
    assert 1 <= len(selection.selected_keys) <= 4


@pytest.mark.parametrize(
    ("value", "stance"),
    [("7-8 hours", SUPPORTIVE), ("5-6 hours", LEVER), ("Less than 5 hours", LEVER), ("6-7 hours", "neutral")],
)
def test_sleep_stance_is_number_aware(value, stance):
    assert stance_for("sleeping_hours", value) == stance


def test_occasional_alcohol_is_not_praised():
    assert stance_for("alcohol_frequency", "Occasionally") == "neutral"
    assert stance_for("alcohol_frequency", "Never") == SUPPORTIVE
    assert stance_for("alcohol_frequency", "Daily") == LEVER


# ------------------------------------------------------------ evidence and budgets


def test_lookup_evidence_has_one_primary_fact_and_exact_value():
    ctx, evidence = _evidence("What is my Vitamin D?")
    marker = next(m for m in ctx.markers if m.key == "vitamin_d")
    assert len(evidence.primary_facts) == 1
    fact = evidence.primary_facts[0]
    assert fact["value"] == marker.value and fact["unit"] == marker.unit
    assert evidence.supporting_facts == []


def test_explanation_evidence_respects_budget():
    _, evidence = _evidence("Why is my HDL low?", SEDENTARY)
    budget = BUDGETS[evidence.response_mode]
    assert len(evidence.primary_facts) <= budget.primary
    assert len(evidence.supporting_facts) <= budget.supporting
    assert len(evidence.questionnaire_facts) <= budget.questionnaire
    assert len(evidence.next_action_context) <= budget.next_actions


def test_overview_prioritizes_instead_of_dumping():
    ctx, evidence = _evidence("What should I focus on?", SEDENTARY)
    assert len(evidence.primary_facts) <= BUDGETS[evidence.response_mode].primary
    assert len(evidence.primary_facts) < len(ctx.markers)
    keys = [f.get("code") for f in evidence.primary_facts[:3]]
    assert "ldl" in keys or "triglycerides" in keys


def test_prioritize_findings_puts_abnormal_first():
    ctx = _context("How am I doing overall?")
    ranked = prioritize_findings(ctx.markers, ctx.bio_ai_risks, "improve_metabolic_health")
    flags = [getattr(m.flag, "value", str(m.flag)) for m in ranked[:3]]
    assert all(flag in {"low", "high", "critical"} for flag in flags)


def test_personal_prompt_is_not_a_record_dump():
    ctx = _context("What should I focus on?")
    full = json.dumps([m.model_dump(mode="json") for m in ctx.markers])
    prompt = PromptBuilder().build(ctx, "", "What should I focus on?")[1]["content"]
    assert "ANSWER EVIDENCE JSON:" in prompt
    assert len(prompt) < 8000 < len(full) or len(prompt) < 8000
    normal = [m for m in ctx.markers if getattr(m.flag, "value", str(m.flag)) == "normal"]
    leaked = [m.key for m in normal if f'"code":"{m.key}"' in prompt]
    assert len(leaked) <= 1


def test_evidence_never_changes_measured_values():
    ctx, evidence = _evidence("How am I doing overall?")
    by_key = {m.key: m for m in ctx.markers}
    for fact in [*evidence.primary_facts, *evidence.supporting_facts]:
        if fact.get("code") in by_key and "value" in fact:
            assert fact["value"] == by_key[fact["code"]].value
            assert fact["unit"] == by_key[fact["code"]].unit


def test_system_prompt_has_editing_and_questionnaire_rules():
    ctx = _context("Why is my HDL low?")
    system = PromptBuilder().build(ctx, "", "Why is my HDL low?")[0]["content"]
    assert "CONVERSATIONAL EDITING" in system
    assert "QUESTIONNAIRE PERSONALIZATION" in system
    assert "answer narrowly" in system


# ------------------------------------------------------------ presentation policy


def _finding(key: str) -> PresentedFinding:
    return PresentedFinding(label=key.upper(), value="1", unit="mg/dL", canonical_key=key)


def test_single_visual_owner_and_lookup_has_no_related_results():
    p = StructuredResponse(
        mode=ResponseMode.interpretation,
        findings=[_finding("hdl")],
        related_findings=[_finding("hdl"), _finding("ldl"), _finding("ldl"), _finding("tg"), _finding("glucose")],
    )
    p, _ = apply_presentation_policy(p)
    keys = [f.canonical_key for f in p.related_findings]
    assert "hdl" not in keys and len(keys) == len(set(keys)) <= 2
    lookup = StructuredResponse(mode=ResponseMode.single_value, findings=[_finding("vitamin_d")], related_findings=[_finding("ldl")])
    lookup, _ = apply_presentation_policy(lookup)
    assert lookup.related_findings == []


def test_at_most_one_proactive_element_and_three_chips():
    p = StructuredResponse(
        mode=ResponseMode.interpretation,
        proactive_insights=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
        suggestion_chips=["one", "two", "three", "four", "two"],
        next_steps=["walk", "walk", "sleep", "fibre", "retest"],
    )
    p, trace = apply_presentation_policy(p, follow_up_count=1)
    assert len(p.proactive_insights) == 1
    assert trace["proactive_element_selected"] == "proactive_insight"
    assert len(p.suggestion_chips) + 1 <= 3
    assert p.next_steps == ["walk", "sleep", "fibre"]


def test_lookup_with_personal_relevance_drops_extra_insight():
    p = StructuredResponse(mode=ResponseMode.single_value, personal_relevance="why", proactive_insights=[{"text": "a"}])
    p, _ = apply_presentation_policy(p)
    assert p.proactive_insights == []


# ------------------------------------------------------------ 0-20 response-quality score

_OPENERS = re.compile(r"^(based on your available data|according to your report|here is a breakdown|let's go through)", re.I)


def score_response(answer: str, *, mode: str, evidence_keys: set[str], other_keys: set[str], chips: int, proactive: int) -> int:
    """0-20: directness, focus, length, safety, presentation discipline (4 points each)."""
    words = len(answer.split())
    lo, hi = {"SINGLE_VALUE": (15, 100), "HEALTH_OVERVIEW": (120, 350)}.get(mode, (40, 180))
    lower = answer.lower()
    score = 0
    score += 4 if not _OPENERS.search(answer.strip()) else 0
    mentioned_other = sum(1 for key in other_keys if re.search(rf"\b{re.escape(key)}\b", lower))
    score += max(0, 4 - 2 * mentioned_other)
    score += 4 if lo <= words <= hi else 2 if words <= hi * 1.3 else 0
    score += 0 if re.search(r"\byou have (diabetes|fatty liver|heart disease)\b|\bcaused by your\b", lower) else 4
    score += (2 if chips <= 3 else 0) + (2 if proactive <= 1 else 0)
    return score


GOOD_EXAMPLES = [
    ("SINGLE_VALUE", "Your vitamin D is 12.6 ng/mL, which is below the reference range. A low value like this is common and usually addressed with your clinician.", {"vitamin_d"}),
    (
        "INTERPRETATION",
        "Your triglycerides are 155 mg/dL, a little above the reference range, though lower than the 168 mg/dL on your previous report. "
        "You already report not drinking alcohol, so that is not the lever here. The more useful areas are likely the mostly refined grains "
        "you reported and how little you move during the day: swapping some refined grains for whole grains and adding a short walk after "
        "meals are reasonable places to start. It is worth rechecking with your next report.",
        {"triglycerides"},
    ),
]


@pytest.mark.parametrize(("mode", "answer", "keys"), GOOD_EXAMPLES)
def test_quality_score_meets_target_for_selective_answers(mode, answer, keys):
    score = score_response(answer, mode=mode, evidence_keys=keys, other_keys={"b12", "hemoglobin", "tsh"}, chips=3, proactive=1)
    assert score >= 18


def test_quality_score_penalizes_data_dump():
    dump = "Based on your available data, here is everything: " + " ".join(
        f"{k} is within range." for k in ["b12", "hemoglobin", "tsh", "creatinine", "ldl", "hdl"] * 8
    )
    score = score_response(dump, mode="SINGLE_VALUE", evidence_keys={"vitamin_d"}, other_keys={"b12", "hemoglobin", "tsh"}, chips=6, proactive=3)
    assert score < 16
