from datetime import date

from app.biomarkers.metabolic_age_insight import build_metabolic_age_insight


TODAY = date(2026, 11, 26)


def test_higher_lower_and_equal():
    higher = build_metabolic_age_insight(actual_age=28, metabolic_age=34, assessed_on="2026-08-01", today=TODAY)
    assert higher is not None and higher.direction == "higher" and higher.difference_years == 6
    assert "6 years above" in higher.comparison
    lower = build_metabolic_age_insight(actual_age=40, metabolic_age=39, assessed_on="2026-08-01", today=TODAY)
    assert lower is not None and lower.direction == "lower" and "1 year below" in lower.comparison
    same = build_metabolic_age_insight(actual_age=33, metabolic_age=33.2, assessed_on="2026-08-01", today=TODAY)
    assert same is not None and same.direction == "equal" and same.comparison.startswith("Your metabolic age estimate matches")


def test_missing_or_invalid_ages_hide_the_card():
    assert build_metabolic_age_insight(actual_age=None, metabolic_age=34, assessed_on="2026-08-01", today=TODAY) is None
    assert build_metabolic_age_insight(actual_age=28, metabolic_age=None, assessed_on="2026-08-01", today=TODAY) is None
    assert build_metabolic_age_insight(actual_age=0, metabolic_age=34, assessed_on="2026-08-01", today=TODAY) is None
    assert build_metabolic_age_insight(actual_age=28, metabolic_age=0, assessed_on="2026-08-01", today=TODAY) is None
    assert build_metabolic_age_insight(actual_age=28, metabolic_age=34, assessed_on=None, today=TODAY) is None
    assert build_metabolic_age_insight(actual_age=28, metabolic_age=34, assessed_on="2027-01-01", today=TODAY) is None


def test_historical_assessment_uses_age_at_that_date():
    insight = build_metabolic_age_insight(actual_age=30, metabolic_age=34, assessed_on="2024-08-01", today=TODAY)
    assert insight is not None
    assert insight.actual_age_years == 28
    assert insight.difference_years == 6


def test_age_would_not_have_been_born_yet():
    assert build_metabolic_age_insight(actual_age=1, metabolic_age=20, assessed_on="2020-01-01", today=TODAY) is None
