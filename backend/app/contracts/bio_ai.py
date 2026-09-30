from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BioAIRisk(BaseModel):
    code: str
    name: str
    score: float | None = None
    status: str | None = None
    percentile: float | None = None
    lifestyle_contribution: float | None = None
    contributing_factors: list[str] = Field(default_factory=list)
    source: str = "supershyft"
    report_id: str | None = None
    measured_at: date | datetime | None = None
    assessment_instance_id: str | None = None


class BioAIReport(BaseModel):
    report_id: str
    report_date: date
    source_line: Literal["bio_ai", "advanced_bio_ai"]
    metabolic_age: float | None = None
    metabolic_score: float | None = None
    risks: list[BioAIRisk] = Field(default_factory=list)
    assessment_instance_id: str | None = None
    engagement_id: str | None = None
    report_url: str | None = None
    completed_at: date | datetime | None = None
