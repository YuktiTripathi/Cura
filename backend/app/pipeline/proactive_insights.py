"""Proactive insights with suppression. Not chat spam."""

from __future__ import annotations

from app.contracts.conversation_state import ConversationState
from app.contracts.health_context import HealthContext
from app.contracts.insights import InsightCandidate
from app.contracts.personalization import InsightTrigger, LongitudinalClass, ProactiveInsight
from app.pipeline.lab_parameters import display_name_for
from app.pipeline.priority import goal_keys


def build_proactive_insights(
    context: HealthContext,
    *,
    conversation_state: ConversationState | None = None,
) -> list[ProactiveInsight]:
    dismissed = set(conversation_state.dismissed_insight_keys or []) if conversation_state else set()
    out: list[ProactiveInsight] = []
    if context.quiet and context.quiet.active:
        return []
    goals = goal_keys(context)
    for item in context.baselines or []:
        trigger = _trigger(item.classification)
        if trigger is None:
            continue
        key = f"{trigger.value}:{item.entity}"
        if key in dismissed:
            out.append(
                ProactiveInsight(
                    trigger=trigger,
                    title=_title(trigger),
                    summary=display_name_for(item.entity),
                    entity=item.entity,
                    suppressed=True,
                    suppression_reason="recently_dismissed",
                )
            )
            continue
        if item.observations < 1:
            continue
        if item.classification == LongitudinalClass.stable:
            continue
        if item.absolute_change is not None and abs(item.absolute_change) < 0.05 and item.classification not in {
            LongitudinalClass.newly_abnormal,
            LongitudinalClass.persistently_abnormal,
        }:
            continue
        summary = _summary(item)
        if trigger == InsightTrigger.goal_relevant_change and item.entity not in goals:
            continue
        if item.entity in goals and trigger != InsightTrigger.goal_relevant_change:
            trigger = InsightTrigger.goal_relevant_change
            summary = f"{display_name_for(item.entity)} changed in a way that is relevant to your current goal."
        out.append(
            ProactiveInsight(
                trigger=trigger,
                title=_title(trigger),
                summary=summary,
                entity=item.entity,
            )
        )
    story = context.health_story
    if story and story.important_missing:
        key = f"MISSING:{story.important_missing[0]}"
        if key not in dismissed:
            out.append(
                ProactiveInsight(
                    trigger=InsightTrigger.important_missing_information,
                    title="One missing test could clarify this",
                    summary=f"{story.important_missing[0]} remains unavailable.",
                    entity=str(story.important_missing[0]).lower().replace(" ", "_"),
                )
            )
    if context.source_conflicts:
        out.append(
            ProactiveInsight(
                trigger=InsightTrigger.new_cross_source_contradiction,
                title="Sources do not fully agree",
                summary="Available sources report this measurement differently.",
            )
        )
    return [item for item in out if not item.suppressed][:4]


def as_insight_candidates(insights: list[ProactiveInsight]) -> list[InsightCandidate]:
    return [
        InsightCandidate(
            insight_type=item.trigger.value.lower(),
            topic=item.entity or item.trigger.value,
            summary=item.summary,
            delivery="on_request",
            trigger=item.trigger.value,
            title=item.title,
            suppressed=item.suppressed,
        )
        for item in insights
    ]


def _trigger(classification: LongitudinalClass) -> InsightTrigger | None:
    return {
        LongitudinalClass.newly_abnormal: InsightTrigger.newly_abnormal,
        LongitudinalClass.persistently_abnormal: InsightTrigger.persistently_abnormal,
        LongitudinalClass.improved_but_still_abnormal: InsightTrigger.improved_but_still_abnormal,
        LongitudinalClass.returned_to_range: InsightTrigger.returned_to_range,
        LongitudinalClass.worsened: InsightTrigger.significant_change,
        LongitudinalClass.improved: InsightTrigger.significant_change,
    }.get(classification)


def _title(trigger: InsightTrigger) -> str:
    return {
        InsightTrigger.newly_abnormal: "Something changed",
        InsightTrigger.persistently_abnormal: "This has stayed outside range",
        InsightTrigger.improved_but_still_abnormal: "Something changed",
        InsightTrigger.returned_to_range: "Something changed",
        InsightTrigger.significant_change: "Something changed",
        InsightTrigger.important_missing_information: "One missing test could clarify this",
        InsightTrigger.goal_relevant_change: "This relates to your goal",
        InsightTrigger.test_duplication_risk: "You may not need another test yet",
        InsightTrigger.new_cross_source_contradiction: "Sources do not fully agree",
    }[trigger]


def _summary(item) -> str:
    name = display_name_for(item.entity)
    if item.classification == LongitudinalClass.improved_but_still_abnormal:
        return f"{name} improved but remains {item.latest_flag}."
    if item.classification == LongitudinalClass.persistently_abnormal:
        return f"{name} remains abnormal across reports."
    if item.classification == LongitudinalClass.newly_abnormal:
        return f"{name} is newly outside the reported range."
    if item.classification == LongitudinalClass.returned_to_range:
        return f"{name} has returned to the reported range."
    return f"{name} changed since the previous measurement."
