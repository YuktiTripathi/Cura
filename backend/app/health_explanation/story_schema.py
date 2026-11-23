"""The guided health story contract. Facts are fixed by code. The model may only write the short lead lines."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.unified_health import ActionItem, Finding, Relationship

Review = Literal["unreviewed", "reviewed"]


class Section(BaseModel):
    heading: str
    text: str


class UnderstandBody(BaseModel):
    available: bool = False
    title: str = ""
    sections: list[Section] = Field(default_factory=list)
    report_scope: str = ""
    source: str = "medical_knowledge_base"
    review_status: Review = "unreviewed"
    evidence_ids: list[str] = Field(default_factory=list)


class RiskExplanation(BaseModel):
    finding_id: str
    name: str
    score: float | None = None
    classification: str | None = None
    assessed_on: str | None = None
    # The report does not carry these today. They stay empty rather than invented.
    model_name: str | None = None
    model_version: str | None = None
    what_it_means: str
    what_it_does_not_mean: list[str]
    limitations: list[str]
    contributing_factors: list[str] | None = None
    contributing_note: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class YourAssessment(BaseModel):
    available: bool = False
    lead: str = ""
    risks: list[RiskExplanation] = Field(default_factory=list)
    note: str = ""


class MeasuredFinding(BaseModel):
    finding: Finding
    marker_id: str | None = None
    why_relevant: str = ""
    source: str = "Laboratory report"
    evidence_ids: list[str] = Field(default_factory=list)


class LifestyleFactor(BaseModel):
    key: str
    label: str
    state: Literal["reported", "not_reported"]
    value: str | None = None
    level: str | None = None
    recorded_at: str | None = None
    source: str = "Your questionnaire"
    evidence_ids: list[str] = Field(default_factory=list)


class StoryRelationship(BaseModel):
    relationship_id: str
    text: str
    relationship_type: str
    finding_ids: list[str] = Field(default_factory=list)
    lifestyle_keys: list[str] = Field(default_factory=list)
    rule_id: str
    causal_claim: Literal[False] = False
    evidence_status: str = "rule_based_unreviewed"
    evidence_ids: list[str] = Field(default_factory=list)


class PersonalFactors(BaseModel):
    lead: str = ""
    measured: list[MeasuredFinding] = Field(default_factory=list)
    within_range_count: int = 0
    lifestyle: list[LifestyleFactor] = Field(default_factory=list)
    relationships: list[StoryRelationship] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class YourResult(BaseModel):
    value: float | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    status: str
    status_label: str
    measured_on: str | None = None
    source: str = "Laboratory report"


class BiomarkerCard(BaseModel):
    marker_id: str | None = None
    name: str
    finding_id: str
    measures: str = ""
    body_function: str = ""
    why_it_matters: str = ""
    causes_when_low: list[str] = Field(default_factory=list)
    causes_when_high: list[str] = Field(default_factory=list)
    effects_when_low: str = ""
    effects_when_high: str = ""
    influences: list[str] = Field(default_factory=list)
    practical_steps: list[str] = Field(default_factory=list)
    related_markers: list[str] = Field(default_factory=list)
    age_sex_note: str = ""
    unit_note: str = ""
    your_result: YourResult
    needs_attention: bool = False
    detail_level: Literal["full", "basic"] = "full"
    evidence_ids: list[str] = Field(default_factory=list)
    review_status: Review = "unreviewed"


class PlanAction(BaseModel):
    action_id: str
    title: str
    what: str
    why: str
    supported_by: list[str] = Field(default_factory=list)
    safety_note: str = ""
    evidence_status: str = "rule_based_unreviewed"


class ImprovementPlan(BaseModel):
    lead: str = ""
    actions: list[PlanAction] = Field(default_factory=list)
    note: str = "These steps support heart health in general. They are not promised to change a Bio-AI score or any single result, and they do not replace advice from your doctor."


class RelatedCategory(BaseModel):
    id: str
    name: str
    status_label: str
    icon: str = "marker"


class NextSteps(BaseModel):
    monitoring: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    related_categories: list[RelatedCategory] = Field(default_factory=list)


class StoryMetadata(BaseModel):
    knowledge_version: str
    rules_version: str
    actions_version: str
    prompt_version: str
    evidence_version: str
    generated_at: str
    generation: Literal["rules", "model"] = "rules"
    generation_model: str | None = None
    data_state: Literal["complete", "partial", "empty"] = "partial"


class HealthStory(BaseModel):
    category_id: str
    category_name: str
    icon: str = "marker"
    status: str = "not_assessed"
    status_label: str = ""
    headline: str
    understand_body: UnderstandBody
    your_assessment: YourAssessment
    personal_factors: PersonalFactors
    biomarker_education: list[BiomarkerCard] = Field(default_factory=list)
    improvement_plan: ImprovementPlan
    next_steps: NextSteps
    limitations: list[str] = Field(default_factory=list)
    metadata: StoryMetadata
    disclaimer: str = "This is general education about your results. It is not a diagnosis and does not replace advice from your doctor."
