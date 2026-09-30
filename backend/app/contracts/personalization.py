"""Personalization overlays. Summaries of existing profile/labs, not a second store."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CommunicationStyle(str, Enum):
    quick = "QUICK"
    standard = "STANDARD"
    deep = "DEEP"


class LanguageRegister(str, Enum):
    simple = "SIMPLE_LANGUAGE"
    technical = "TECHNICAL"


class GoalSource(str, Enum):
    user_goal = "user_goal"
    questionnaire = "questionnaire"
    conversation = "conversation"
    profile = "profile"


class LongitudinalClass(str, Enum):
    newly_abnormal = "NEWLY_ABNORMAL"
    persistently_abnormal = "PERSISTENTLY_ABNORMAL"
    improved_but_still_abnormal = "IMPROVED_BUT_STILL_ABNORMAL"
    returned_to_range = "RETURNED_TO_RANGE"
    worsened = "WORSENED"
    improved = "IMPROVED"
    stable = "STABLE"
    newly_available = "NEWLY_AVAILABLE"
    no_longitudinal_data = "NO_LONGITUDINAL_DATA"


class InsightTrigger(str, Enum):
    newly_abnormal = "NEWLY_ABNORMAL"
    persistently_abnormal = "PERSISTENTLY_ABNORMAL"
    significant_change = "SIGNIFICANT_CHANGE"
    improved_but_still_abnormal = "IMPROVED_BUT_STILL_ABNORMAL"
    returned_to_range = "RETURNED_TO_RANGE"
    new_cross_source_contradiction = "NEW_CROSS_SOURCE_CONTRADICTION"
    important_missing_information = "IMPORTANT_MISSING_INFORMATION"
    goal_relevant_change = "GOAL_RELEVANT_CHANGE"
    test_duplication_risk = "TEST_DUPLICATION_RISK"


class KnownLifestyle(BaseModel):
    sleep: str | None = None
    activity: str | None = None
    diet: str | None = None
    alcohol: str | None = None
    smoking: str | None = None
    stress: str | None = None
    hydration: str | None = None
    already_supportive: list[str] = Field(default_factory=list)


class RecentContext(BaseModel):
    """Session-level user-stated context. Never treated as laboratory history."""

    symptoms: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    illness: list[str] = Field(default_factory=list)
    travel: list[str] = Field(default_factory=list)
    routine_changes: list[str] = Field(default_factory=list)
    pregnancy: str | None = None
    fasting_status: str | None = None
    notes: list[str] = Field(default_factory=list)
    source: str = "conversation"


class PersonalBaseline(BaseModel):
    entity: str
    latest: float | None = None
    previous: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    direction: str | None = None
    historical_median: float | None = None
    observations: int = 0
    near_personal_baseline: bool | None = None
    newly_abnormal: bool = False
    persistent_abnormality: bool = False
    classification: LongitudinalClass = LongitudinalClass.no_longitudinal_data
    latest_flag: str | None = None
    previous_flag: str | None = None
    unit: str | None = None


class CompactLongitudinal(BaseModel):
    latest: dict[str, float | str] = Field(default_factory=dict)
    important_previous: dict[str, float | str] = Field(default_factory=dict)
    trend_summary: list[str] = Field(default_factory=list)


class HealthStoryPattern(BaseModel):
    domain: str
    supporting_entities: list[str] = Field(default_factory=list)


class HealthStory(BaseModel):
    stable_reassuring: list[str] = Field(default_factory=list)
    persistent_patterns: list[HealthStoryPattern] = Field(default_factory=list)
    improving: list[str] = Field(default_factory=list)
    worsening: list[str] = Field(default_factory=list)
    new_findings: list[str] = Field(default_factory=list)
    important_missing: list[str] = Field(default_factory=list)
    returned_to_range: list[str] = Field(default_factory=list)


class GoalProgressDetail(BaseModel):
    goal_code: str
    improving: list[str] = Field(default_factory=list)
    stable: list[str] = Field(default_factory=list)
    worsening: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    insufficient_history: list[str] = Field(default_factory=list)


class HealthJourney(BaseModel):
    current_focus: list[str] = Field(default_factory=list)
    improving: list[str] = Field(default_factory=list)
    stable: list[str] = Field(default_factory=list)
    needs_attention: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    goal_progress: list[GoalProgressDetail] = Field(default_factory=list)


class NextStep(BaseModel):
    action: str
    reason: str
    supporting_fact_ids: list[str] = Field(default_factory=list)
    urgency: str = "routine"
    personal_relevance: str | None = None


class ClinicianHandoff(BaseModel):
    key_findings: list[str] = Field(default_factory=list)
    longitudinal_changes: list[str] = Field(default_factory=list)
    relevant_context: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    questions_for_clinician: list[str] = Field(default_factory=list)


class ProactiveInsight(BaseModel):
    trigger: InsightTrigger
    title: str
    summary: str
    entity: str | None = None
    domain: str | None = None
    suppressed: bool = False
    suppression_reason: str | None = None


class QuietDecision(BaseModel):
    active: bool = False
    reason: str | None = None


class PersonalizationContext(BaseModel):
    """Compact overlay. Authoritative labs/goals/lifestyle remain on HealthContext."""

    primary_health_goal: str | None = None
    secondary_health_goals: list[str] = Field(default_factory=list)
    goal_source: GoalSource | None = None
    communication_preference: CommunicationStyle = CommunicationStyle.standard
    language_register: LanguageRegister | None = None
    health_literacy_level: str | None = None
    dietary_preferences: list[str] = Field(default_factory=list)
    activity_preferences: list[str] = Field(default_factory=list)
    known_lifestyle: KnownLifestyle = Field(default_factory=KnownLifestyle)
    recent_user_context: RecentContext = Field(default_factory=RecentContext)
    health_focus_areas: list[str] = Field(default_factory=list)
    recurring_concerns: list[str] = Field(default_factory=list)
    personal_baselines: dict[str, PersonalBaseline] = Field(default_factory=dict)
    recent_trends: list[str] = Field(default_factory=list)
    reassuring_domains: list[str] = Field(default_factory=list)
    stable_domains: list[str] = Field(default_factory=list)
    improved_domains: list[str] = Field(default_factory=list)
    compact_longitudinal: CompactLongitudinal = Field(default_factory=CompactLongitudinal)
    session_only: bool = True
