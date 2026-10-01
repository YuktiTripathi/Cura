"""UI-facing summary of the user's own records for the home dashboard and marker panel.

Derived from PersonalHealthSnapshot. Carries display labels and dates only: no report, assessment
or document ids.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MarkerStatus = Literal["low", "high", "critical", "normal", "unknown"]


class MarkerPoint(BaseModel):
    date: str
    value: float
    status: MarkerStatus = "unknown"


class MarkerOverview(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    status: MarkerStatus = "unknown"
    measured_on: str | None = None
    previous_value: float | None = None
    previous_on: str | None = None
    # Movement relative to the reference range since the previous result.
    trend: Literal["toward_range", "away_from_range", "steady", "in_range"] | None = None
    history: list[MarkerPoint] = Field(default_factory=list)


class InsightOverview(BaseModel):
    title: str
    summary: str
    marker_key: str | None = None


class ScoreOverview(BaseModel):
    name: str
    score: float | None = None
    status: str | None = None


class ReportOverview(BaseModel):
    title: str
    date: str


class HealthOverview(BaseModel):
    available: bool = True
    latest_report_date: str | None = None
    markers: list[MarkerOverview] = Field(default_factory=list)
    insights: list[InsightOverview] = Field(default_factory=list)
    scores: list[ScoreOverview] = Field(default_factory=list)
    reports: list[ReportOverview] = Field(default_factory=list)
