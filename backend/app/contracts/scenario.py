from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.evidence import EvidenceRecord
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.lifestyle import LifestyleContext


class ScenarioItem(BaseModel):
    code: str
    title: str
    detail: str
    source: str
    evidence_ids: list[str] = Field(default_factory=list)


class ScenarioTrend(BaseModel):
    code: str
    name: str
    direction: str
    previous_value: float | None = None
    current_value: float | None = None
    unit: str | None = None


class HealthScenario(BaseModel):
    going_well: list[ScenarioItem] = Field(default_factory=list)
    needs_attention: list[ScenarioItem] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    risk_drivers: list[ScenarioItem] = Field(default_factory=list)
    trends: list[ScenarioTrend] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)


class ScenarioContext(BaseModel):
    blood_reports: list[BloodReport] = Field(default_factory=list)
    bio_ai_reports: list[BioAIReport] = Field(default_factory=list)
    lifestyle: LifestyleContext | None = None
    questionnaire_notes: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
