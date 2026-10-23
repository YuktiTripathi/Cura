"""Complexity selects the tier. A verified lookup does not call a model."""

from app.contracts.common import AnswerModelTier
from app.pipeline.query_planner import build_query_plan
from app.routing.model_tier import apply_answer_model_routing


def _tier(message: str) -> AnswerModelTier:
    plan = apply_answer_model_routing(build_query_plan(message))
    return plan.answer_model_tier


def test_simple_explanation_can_stay_fast():
    plan = apply_answer_model_routing(build_query_plan("What does the word calorie mean in everyday language?"))
    assert plan.answer_model_tier == AnswerModelTier.fast_reasoning
    assert "complexity_score_fast" in (plan.model_selection_reasons or [])


def test_multi_part_explanation_is_not_forced_deep():
    tier = _tier("Why do people feel thirsty after salty food? Explain the mechanism in two steps.")
    assert tier in {AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical}


def test_uncertainty_across_several_factors_reaches_deep():
    plan = apply_answer_model_routing(
        build_query_plan(
            "How could sleep, activity, and diet interact over a month, and what would be uncertain without measurements?"
        )
    )
    assert plan.answer_model_tier == AnswerModelTier.deep_medical_reasoning
    assert any(
        reason in (plan.model_selection_reasons or [])
        for reason in ("complexity_score_deep", "deep_medical_complexity")
    )


def test_direct_marker_lookup_stays_deterministic():
    plan = apply_answer_model_routing(build_query_plan("What is my fasting glucose?"))
    assert plan.answer_model_tier == AnswerModelTier.deterministic
    assert plan.reasoning_required is False
