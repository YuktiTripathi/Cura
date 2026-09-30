from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.facts import ProvenancedFact
from app.contracts.goals import GoalProgress, HealthGoal
from app.contracts.health_context import Comparison
from app.contracts.insights import InsightCandidate
from app.contracts.personalization import HealthJourney, PersonalizationContext
from app.contracts.profile import PersonalHealthProfile
from app.contracts.questionnaire import LifestyleSummary
from app.contracts.timeline import PersonalHealthTimeline


class SnapshotReport(BaseModel):
    report_id: str
    report_date: str | None = None
    source: str
    title: str


class PersonalHealthSnapshot(BaseModel):
    subject_id: str
    available: bool = False
    latest_biomarkers: list[BloodMarker] = Field(default_factory=list)
    recent_changes: list[Comparison] = Field(default_factory=list)
    bio_ai_scores: list[BioAIRisk] = Field(default_factory=list)
    health_goals: list[HealthGoal] = Field(default_factory=list)
    goal_progress: list[GoalProgress] = Field(default_factory=list)
    recent_reports: list[SnapshotReport] = Field(default_factory=list)
    notable_trends: list[Comparison] = Field(default_factory=list)
    profile: PersonalHealthProfile | None = None
    timeline: PersonalHealthTimeline | None = None
    lifestyle_summary: LifestyleSummary | None = None
    facts: list[ProvenancedFact] = Field(default_factory=list)
    insight_candidates: list[InsightCandidate] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    health_journey: HealthJourney | None = None
    personalization: PersonalizationContext | None = None
