"""Answer-operation and source-outcome contracts. Jev still classifies; CURA executes."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class AnswerOperation(str, Enum):
    lookup = "LOOKUP"
    explain = "EXPLAIN"
    personal_interpretation = "PERSONAL_INTERPRETATION"
    trend = "TREND"
    compare = "COMPARE"
    summarize = "SUMMARIZE"
    cross_source_analysis = "CROSS_SOURCE_ANALYSIS"
    recommend = "RECOMMEND"
    provenance = "PROVENANCE"
    safety_escalation = "SAFETY_ESCALATION"
    assess_goal_progress = "ASSESS_GOAL_PROGRESS"
    prepare_clinician_discussion = "PREPARE_CLINICIAN_DISCUSSION"


class SourceOutcomeStatus(str, Enum):
    retrieved = "retrieved"
    empty = "empty"
    unavailable = "unavailable"
    unauthorized = "unauthorized"
    not_requested = "not_requested"


class SourceOutcome(BaseModel):
    source: str
    status: SourceOutcomeStatus = SourceOutcomeStatus.not_requested
    record_count: int = 0
    detail: str | None = None


class PremiseCheck(BaseModel):
    claim: str
    verified: bool | None = None
    note: str | None = None
    previous_value: float | None = None
    current_value: float | None = None
    previous_date: date | None = None
    current_date: date | None = None
    previous_report_id: str | None = None
    current_report_id: str | None = None


class QualityGateResult(BaseModel):
    passed: bool = True
    flags: list[str] = Field(default_factory=list)
    repairs: list[str] = Field(default_factory=list)
