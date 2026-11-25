"""Server snapshot and the frontend health view derived from it.

Personal numbers are copied from provider DTOs. Educational text is copied from
the content registry. Missing fields stay empty.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.unified_health import CategoryDetail, Finding, UnifiedOverview

SnapshotState = Literal["ready", "partial", "unavailable"]


class SourceAvailability(BaseModel):
    blood: Literal["ready", "empty", "unavailable"] = "empty"
    bio_ai: Literal["ready", "empty", "unavailable"] = "empty"
    lifestyle: Literal["ready", "empty", "unavailable"] = "empty"
    questionnaire: Literal["ready", "empty", "unavailable"] = "empty"
    profile: Literal["ready", "empty", "unavailable"] = "empty"


class ReportRef(BaseModel):
    report_id: str
    report_date: str | None = None


class MemberSnapshot(BaseModel):
    schema_version: str
    registry_version: str
    snapshot_version: str
    built_at: datetime
    state: SnapshotState
    availability: SourceAvailability
    profile_display_name: str | None = None
    latest_blood: ReportRef | None = None
    previous_blood: ReportRef | None = None
    latest_bio_ai: ReportRef | None = None
    previous_bio_ai: ReportRef | None = None
    metabolic_age: float | None = None
    source_ids: list[str] = Field(default_factory=list)
    overview: UnifiedOverview
    categories: dict[str, CategoryDetail] = Field(default_factory=dict)
    findings: dict[str, Finding] = Field(default_factory=dict)
    related_keys: dict[str, list[str]] = Field(default_factory=dict)
    # Counts only. Raw questionnaire answers stay off the health view.
    questionnaire_count: int = 0
    lifestyle_present: bool = False


class HealthView(BaseModel):
    """Frontend exploration payload. No raw questionnaire and no provider metadata."""

    state: SnapshotState
    snapshot_version: str
    schema_version: str
    registry_version: str
    built_at: datetime
    availability: SourceAvailability
    display_name: str | None = None
    latest_blood_date: str | None = None
    previous_blood_date: str | None = None
    latest_bio_ai_date: str | None = None
    previous_bio_ai_date: str | None = None
    metabolic_age: float | None = None
    measured_count: int = 0
    risk_count: int = 0
    overview: UnifiedOverview
    categories: dict[str, CategoryDetail] = Field(default_factory=dict)
    findings: dict[str, Finding] = Field(default_factory=dict)
    related_keys: dict[str, list[str]] = Field(default_factory=dict)
    suggested_questions: dict[str, list[str]] = Field(default_factory=dict)
