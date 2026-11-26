"""Deterministic metabolic-age comparison for the My Health card.

Profile age is the current whole-year age. There is no date of birth, so the age
used for comparison is that age minus the completed years between the Bio-AI
assessment and today. The Bio-AI value is never recalculated from biomarkers.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class MetabolicAgeInsight(BaseModel):
    actual_age_years: int
    metabolic_age_years: int
    difference_years: int
    direction: str
    comparison: str
    assessed_on: str


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _completed_years(start: date, end: date) -> int:
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return years


def _years(value: float) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in {float("inf"), float("-inf")}:
        return None
    years = int(round(float(value)))
    if years < 1 or years > 120:
        return None
    return years


def comparison_text(direction: str, difference: int) -> str:
    if direction == "equal":
        return "Your metabolic age estimate matches your actual age. Let's see what this tells us about your metabolic health."
    word = "year" if difference == 1 else "years"
    if direction == "higher":
        return (
            f"Your metabolic age is estimated to be {difference} {word} above your actual age. "
            "Curious about what this means for your health?"
        )
    return (
        f"Your metabolic age is estimated to be {difference} {word} below your actual age. "
        "Let's explore what this means for your health."
    )


def build_metabolic_age_insight(*, actual_age, metabolic_age, assessed_on, today: date | None = None) -> MetabolicAgeInsight | None:
    current = _years(actual_age)
    metabolic = _years(metabolic_age)
    assessed = _as_date(assessed_on)
    day = today or date.today()
    if current is None or metabolic is None or assessed is None or assessed > day:
        return None
    elapsed = _completed_years(assessed, day)
    if elapsed < 0:
        return None
    at_assessment = current - elapsed
    if at_assessment < 1 or at_assessment > 120:
        return None
    difference = metabolic - at_assessment
    direction = "higher" if difference > 0 else "lower" if difference < 0 else "equal"
    return MetabolicAgeInsight(
        actual_age_years=at_assessment,
        metabolic_age_years=metabolic,
        difference_years=abs(difference),
        direction=direction,
        comparison=comparison_text(direction, abs(difference)),
        assessed_on=assessed.isoformat(),
    )
