from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.evidence import EvidenceRecord
from app.contracts.facts import ProvenancedFact
from app.contracts.goals import GoalProgress, HealthGoal
from app.contracts.lifestyle import LifestyleContext
from app.contracts.profile import PersonalHealthProfile
from app.contracts.recommendation import ApprovedRecommendation
from app.contracts.scenario import HealthScenario
from app.contracts.timeline import PersonalHealthTimeline


class Comparison(BaseModel):
    topic: str
    previous_value: float | None = None
    current_value: float | None = None
    previous_report_id: str | None = None
    current_report_id: str | None = None
    previous_date: date | None = None
    current_date: date | None = None
    absolute_delta: float | None = None
    percentage_change: float | None = None
    direction: str | None = None


class InRangeSummary(BaseModel):
    in_range: int = 0
    out_of_range: int = 0
    missing: int = 0


class MissingItem(BaseModel):
    key: str
    name: str
    reason: str = "not_present"


class DisambiguationCandidate(BaseModel):
    report_id: str
    report_date: date
    source_line: str | None = None
    label: str | None = None


class ContextMeta(BaseModel):
    sources: list[str] = Field(default_factory=list)
    report_ids: list[str] = Field(default_factory=list)
    minimal_context: bool = True
    token_budget: int = 4000
    cache_hit: bool = False


class CrossSourceValue(BaseModel):
    source: str
    value: float | None = None
    unit: str | None = None
    measured_at: date | None = None
    report_id: str | None = None
    document_id: str | None = None
    page: int | None = None
    confidence: str = "high"


class CrossSourceFinding(BaseModel):
    parameter: str
    name: str
    values: list[CrossSourceValue] = Field(default_factory=list)
    difference: float | None = None
    direction: str | None = None
    notes: list[str] = Field(default_factory=list)


class HealthContext(BaseModel):
    intent: IntentType
    answer_depth: AnswerDepth
    knowledge_scope: KnowledgeScope = KnowledgeScope.general
    data_source: str = "general"
    resolved_topic: str | None = None
    resolved_topic_name: str | None = None
    status: str = "ok"
    markers: list[BloodMarker] = Field(default_factory=list)
    bio_ai_risks: list[BioAIRisk] = Field(default_factory=list)
    comparisons: list[Comparison] = Field(default_factory=list)
    in_range_summary: InRangeSummary | None = None
    missing: list[MissingItem] = Field(default_factory=list)
    disambiguation: list[DisambiguationCandidate] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    metabolic_age: float | None = None
    metabolic_score: float | None = None
    display_name: str | None = None
    notes: list[str] = Field(default_factory=list)
    medical_passages: list[str] = Field(default_factory=list)
    lifestyle: LifestyleContext | None = None
    profile: PersonalHealthProfile | None = None
    timeline: PersonalHealthTimeline | None = None
    facts: list[ProvenancedFact] = Field(default_factory=list)
    goals: list[HealthGoal] = Field(default_factory=list)
    goal_progress: list[GoalProgress] = Field(default_factory=list)
    scenario: HealthScenario | None = None
    recommendations: list[ApprovedRecommendation] = Field(default_factory=list)
    context_version: str = "health-context-v2"
    meta: ContextMeta = Field(default_factory=ContextMeta)
    cross_source: CrossSourceFinding | None = None
