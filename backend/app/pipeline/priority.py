"""Presentation ranking for broad summaries. Not a health score."""

from __future__ import annotations

from app.contracts.common import MarkerFlag
from app.contracts.goals import GOAL_METRICS
from app.contracts.health_context import HealthContext
from app.contracts.personalization import LongitudinalClass
from app.pipeline.health_domains import domain_for_entity

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical, "low", "high", "critical"}
_SEVERITY = {"critical": 3, "high": 2, "low": 2, "unknown": 1, "normal": 0, "missing": 0}


def goal_keys(context: HealthContext) -> set[str]:
    codes = []
    if context.personalization and context.personalization.primary_health_goal:
        codes.append(context.personalization.primary_health_goal)
    codes.extend(goal.goal_code for goal in context.goals or [])
    keys: set[str] = set()
    for code in codes:
        keys.update(GOAL_METRICS.get(code, ()))
    return keys


def theme_priority_score(
    *,
    code: str,
    abnormal_count: int,
    flags: list[str],
    context: HealthContext,
    persistent: bool,
    missing: int,
    question_hit: bool,
) -> int:
    goal = goal_keys(context)
    domain_entities = []
    from app.pipeline.health_domains import domain_for_code

    domain = domain_for_code(code)
    if domain:
        domain_entities = list(domain.primary_entities) + list(domain.supporting_entities)
    goal_hit = 1 if goal and (goal & set(domain_entities)) else 0
    severity = max((_SEVERITY.get(str(flag), 0) for flag in flags), default=0)
    clinical = 6 if code in {"glycemic_health", "red_cell_anaemia_health"} and severity >= 2 else 0
    change = 0
    for item in context.baselines or []:
        if item.entity in domain_entities and item.classification in {
            LongitudinalClass.newly_abnormal,
            LongitudinalClass.worsened,
            LongitudinalClass.improved_but_still_abnormal,
        }:
            change = 1
            break
    return (
        4 * goal_hit
        + 3 * severity
        + 2 * (1 if persistent else 0)
        + 2 * min(abnormal_count, 3)
        + 2 * change
        + missing
        + (1 if question_hit else 0)
    )


def entity_goal_relevant(key: str, context: HealthContext) -> bool:
    return key in goal_keys(context) or (
        (domain := domain_for_entity(key)) is not None and bool(goal_keys(context) & set(domain.primary_entities))
    )
