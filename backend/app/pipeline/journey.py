"""Backend DTO for a future health-journey view."""

from __future__ import annotations

from app.contracts.goals import GOAL_METRICS
from app.contracts.health_context import HealthContext
from app.contracts.personalization import GoalProgressDetail, HealthJourney, LongitudinalClass
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.lab_parameters import display_name_for


def build_health_journey(context: HealthContext) -> HealthJourney:
    story = context.health_story
    improving = [display_name_for(key) for key in (story.improving if story else [])]
    stable = list(story.stable_reassuring if story else [])
    attention = []
    if story:
        for pattern in story.persistent_patterns:
            attention.append(pattern.domain.replace("_", " "))
        attention.extend(display_name_for(key) for key in story.worsening)
        attention.extend(story.new_findings)
    goal_rows: list[GoalProgressDetail] = []
    for progress in context.goal_progress or []:
        goal_rows.append(
            GoalProgressDetail(
                goal_code=progress.goal_code,
                improving=list(progress.improving or []),
                stable=list(progress.stable or []),
                worsening=list(progress.worsening or []),
                missing_metrics=list(progress.missing_metrics or []),
                insufficient_history=[] if progress.sufficient_history else list(GOAL_METRICS.get(progress.goal_code, ())),
            )
        )
    focus = []
    if context.personalization and context.personalization.primary_health_goal:
        focus.append(context.personalization.primary_health_goal.replace("_", " "))
    focus.extend(attention[:3])
    missing = list(story.important_missing if story else [])
    return HealthJourney(
        current_focus=list(dict.fromkeys(focus))[:6],
        improving=improving[:6],
        stable=stable[:6],
        needs_attention=list(dict.fromkeys(attention))[:6],
        missing_information=missing[:6],
        goal_progress=goal_rows,
    )


def domain_label(key: str) -> str:
    domain = domain_for_entity(key)
    return domain.code.replace("_", " ") if domain else display_name_for(key)
