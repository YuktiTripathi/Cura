"""The same result with different habits gives a different personal context, and the result itself is unchanged."""

from app.pipeline.prompt_builder import PromptBuilder
from tests.unit.test_answer_quality import _context


def _user(message, answers):
    ctx = _context(message, answers)
    return ctx, PromptBuilder().build(ctx, "", message)[1]["content"]


def test_same_lipid_result_with_low_and_high_activity():
    message = "How does my physical activity relate to my cholesterol?"
    low_ctx, low = _user(message, {"physical_activity_frequency": "Rarely", "exercise_frequency_week": "0-1 days"})
    high_ctx, high = _user(message, {"physical_activity_frequency": "Daily", "exercise_frequency_week": "5-6 days"})
    assert {(m.key, m.value) for m in low_ctx.markers} == {(m.key, m.value) for m in high_ctx.markers}
    assert "Rarely" in low and "Rarely" not in high
    assert "Daily" in high and "Daily" not in low


def test_same_b12_result_with_vegetarian_and_non_vegetarian_diet():
    message = "Why is my Vitamin B12 low?"
    _veg_ctx, veg = _user(message, {"diet_preference": "Vegetarian"})
    _non_ctx, non = _user(message, {"diet_preference": "Non vegetarian"})
    assert "Vegetarian" in veg and "Non vegetarian" not in veg
    assert "Non vegetarian" in non
