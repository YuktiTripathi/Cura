"""Attach personalization overlays to HealthContext after retrieval."""

from __future__ import annotations

from app.contracts.blood import BloodReport
from app.contracts.conversation_state import ConversationState
from app.contracts.health_context import HealthContext
from app.pipeline.baselines import build_baselines
from app.pipeline.clinician_handoff import build_clinician_handoff
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.health_story import build_health_story
from app.pipeline.journey import build_health_journey
from app.pipeline.longitudinal import compact_longitudinal
from app.pipeline.personalization_context import build_personalization_context, session_goal
from app.pipeline.proactive_insights import build_proactive_insights
from app.pipeline.quiet_mode import decide_quiet


def attach_personalization_layer(
    context: HealthContext,
    *,
    message: str = "",
    conversation_state: ConversationState | None = None,
    blood_reports: list[BloodReport] | None = None,
) -> HealthContext:
    if context.knowledge_scope.value != "personal" and not context.markers:
        return context
    perso = build_personalization_context(context, message=message, conversation_state=conversation_state)
    context.personalization = perso
    if perso.primary_health_goal and not any(goal.goal_code == perso.primary_health_goal for goal in context.goals or []):
        extra = session_goal(context.profile.subject_id if context.profile else "session", perso.primary_health_goal)
        if extra:
            context.goals = list(context.goals or []) + [extra]
            context.goal_progress = compute_goal_progress(context.goals, blood_reports or [])
    keys = [m.key for m in context.markers or [] if m.key]
    if perso.primary_health_goal:
        from app.contracts.goals import GOAL_METRICS

        keys = list(dict.fromkeys([*keys, *GOAL_METRICS.get(perso.primary_health_goal, ())]))
    context.baselines = build_baselines(blood_reports, keys)
    perso.personal_baselines = {item.entity: item for item in context.baselines}
    perso.compact_longitudinal = compact_longitudinal(blood_reports, keys=keys, baselines=context.baselines)
    perso.recent_trends = list(perso.compact_longitudinal.trend_summary)
    context.health_story = build_health_story(context, context.baselines)
    perso.reassuring_domains = list(context.health_story.stable_reassuring)
    perso.stable_domains = list(context.health_story.stable_reassuring)
    perso.improved_domains = list(context.health_story.improving)
    context.quiet = decide_quiet(context, message)
    context.health_journey = build_health_journey(context)
    context.clinician_handoff = build_clinician_handoff(context)
    context.proactive_insights = build_proactive_insights(context, conversation_state=conversation_state)
    return context
