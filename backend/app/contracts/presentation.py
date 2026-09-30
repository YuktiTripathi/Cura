"""User-facing response presentation. Separate from retrieval and medical reasoning."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.diagnostics import TestingOption


class ResponseMode(str, Enum):
    single_value = "SINGLE_VALUE"
    result_list = "RESULT_LIST"
    domain_summary = "DOMAIN_SUMMARY"
    interpretation = "INTERPRETATION"
    comparison = "COMPARISON"
    trend = "TREND"
    health_overview = "HEALTH_OVERVIEW"
    safety = "SAFETY"
    personal_interpretation = "PERSONAL_INTERPRETATION"
    narrative_health_summary = "NARRATIVE_HEALTH_SUMMARY"
    goal_progress = "GOAL_PROGRESS"
    clinician_handoff = "CLINICIAN_HANDOFF"
    acute_health_guidance = "ACUTE_HEALTH_GUIDANCE"
    package_recommendation = "PACKAGE_RECOMMENDATION"
    quiet_update = "QUIET_UPDATE"


class SummaryStyle(str, Enum):
    raw_health_snapshot = "RAW_HEALTH_SNAPSHOT"
    narrative_health_summary = "NARRATIVE_HEALTH_SUMMARY"


class ThemePriority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ThemeStatus(str, Enum):
    needs_attention = "needs_attention"
    monitor = "monitor"
    reassuring = "reassuring"
    uncertain = "uncertain"


class PresentedFinding(BaseModel):
    label: str
    value: str | None = None
    unit: str | None = None
    status: str | None = None
    source_type: str | None = None
    source_date: str | None = None
    source_id: str | None = None
    source_label: str | None = None
    canonical_key: str | None = None


class HealthTheme(BaseModel):
    title: str
    priority: ThemePriority = ThemePriority.medium
    status: ThemeStatus = ThemeStatus.monitor
    supporting_fact_ids: list[str] = Field(default_factory=list)
    interpretation: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    next_step: str | None = None
    related_findings: list[PresentedFinding] = Field(default_factory=list)


class StructuredResponse(BaseModel):
    mode: ResponseMode = ResponseMode.single_value
    headline: str | None = None
    summary: str | None = None
    findings: list[PresentedFinding] = Field(default_factory=list)
    interpretation: str | None = None
    uncertainties: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    follow_up: str | None = None
    display_entities: list[str] = Field(default_factory=list)
    reasoning_context: list[str] = Field(default_factory=list)
    summary_style: SummaryStyle | None = None
    overall_summary: str | None = None
    themes: list[HealthTheme] = Field(default_factory=list)
    raw_findings: list[PresentedFinding] = Field(default_factory=list)
    testing_option: TestingOption | None = None
    personal_relevance: str | None = None
    clinician_handoff: dict | None = None
    quiet_mode: bool = False
    proactive_insights: list[dict] = Field(default_factory=list)
    structured_next_steps: list[dict] = Field(default_factory=list)
    health_journey: dict | None = None
