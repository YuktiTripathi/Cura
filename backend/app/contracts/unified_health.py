"""One health picture: measured blood results and predicted Bio-AI risks in the same categories.

Every number, unit, range, score, classification and date is copied from the verified report
data by the backend. The model only writes the wording (summary, interpretation, actions,
follow ups). Measured results and predicted risks sit in one findings list, told apart by
`source_type`, and are never treated as the same kind of evidence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator, BaseModel, Field

CategoryStatus = Literal["looking_good", "worth_attention", "needs_closer_attention", "not_assessed"]
Completeness = Literal["complete", "partial", "none"]
SourceType = Literal["measured", "predicted_risk"]
# How the two kinds of evidence sit together in this category (scenarios A to H).
Scenario = Literal[
    "both_reassuring",  # A
    "blood_out_risk_ok",  # B
    "blood_ok_risk_up",  # C
    "both_out",  # D
    "blood_only",  # E
    "risk_only",  # F
    "incomplete",  # G
    "none",
]
FindingStatus = Literal[
    "within_range", "above_range", "below_range", "critical", "no_range", "no_value", "risk_healthy", "risk_raised", "risk_unknown"
]


class EducationNote(BaseModel):
    """Reviewed plain-language text about a test. General education, never a reading of this result."""

    name: str
    what_it_is: str
    definition_points: list[str] = Field(default_factory=list)
    if_high: str = ""
    if_low: str = ""
    next_step: str = ""
    common_factors: str = ""
    why_it_matters: str = ""
    body: str = ""
    limitations: str = ""
    factors: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    related_markers: list[str] = Field(default_factory=list)
    content_version: str = ""
    review_status: str = ""
    content_source: str = ""


class Finding(BaseModel):
    id: str
    source_type: SourceType
    name: str
    medical_name: str = ""
    explain: str = ""
    status: FindingStatus
    status_label: str
    # Measured
    value: float | None = None
    status_source: Literal["report_flag", "reference_range", "none"] | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    how_far: Literal["slightly", "moderately", "clearly"] | None = None
    # Predicted risk
    score: float | None = None
    classification: str | None = None
    measured_on: str | None = None
    report_id: str | None = None
    previous_score: float | None = None
    previous_value: float | None = None
    previous_on: str | None = None
    important: bool = False
    marker_code: str | None = None
    education: EducationNote | None = None
    # How far this finding can be relied on. It follows from what the report supplied, never from a guess.
    data_quality: Literal["verified", "reference_unavailable", "unavailable"] = "verified"

    @model_validator(mode="after")
    def _derive_quality(self):
        if self.status in {"no_range"}:
            self.data_quality = "reference_unavailable"
        elif self.status in {"no_value", "risk_unknown"}:
            self.data_quality = "unavailable"
        return self


class MeasuredCounts(BaseModel):
    total: int = 0
    within_range: int = 0
    outside_range: int = 0
    no_range: int = 0
    unavailable: int = 0


class RiskCounts(BaseModel):
    assessed: int = 0
    raised: int = 0


class Provenance(BaseModel):
    blood_report_id: str | None = None
    blood_report_date: str | None = None
    bio_ai_report_id: str | None = None
    bio_ai_report_date: str | None = None
    # True only when report metadata ties the two together. Different dates are never assumed linked.
    reports_linked: bool = False
    dates_differ: bool = False


class PrimaryAction(BaseModel):
    label: str
    question: str


class ActionItem(BaseModel):
    title: str
    detail: str = ""
    icon: str = "check"
    action_id: str | None = None
    # Every action comes from the library; evidence_status records how it was checked.
    evidence_status: str = "rule_based_unreviewed"


class CategoryCard(BaseModel):
    id: str
    name: str
    icon: str
    description: str = ""
    status: CategoryStatus
    status_label: str
    completeness: Completeness
    scenario: Scenario
    summary: str
    important_findings: list[Finding] = Field(default_factory=list)
    measured: MeasuredCounts = Field(default_factory=MeasuredCounts)
    risks: RiskCounts = Field(default_factory=RiskCounts)
    count_line: str = ""
    detail_line: str = ""
    primary_action: PrimaryAction
    risk_highlight: Literal["increased", "very_high"] | None = None


class Relationship(BaseModel):
    """An approved association or contrast between findings. It never states a cause."""

    relationship_id: str
    category: str
    finding_ids: list[str] = Field(default_factory=list)
    relationship_type: Literal["supports", "consistent_with", "contextualizes", "potentially_related", "discordant", "independent", "temporal_change"]
    interpretation: str
    causal_claim: Literal[False] = False
    evidence_status: str = "rule_based_unreviewed"
    rule_id: str
    rationale: str = ""
    rules_version: str = ""


class SelfReportedFactor(BaseModel):
    source_type: Literal["self_reported"] = "self_reported"
    source: Literal["questionnaire", "profile"] = "questionnaire"
    key: str
    label: str
    value: str
    unit: str | None = None
    recorded_at: str | None = None


class CategoryStory(BaseModel):
    understand_body: str
    bio_ai_limitations: str
    risk_explanations: dict[str, str]
    influences: list[str]
    self_reported: list[SelfReportedFactor]
    biomarker_meanings: dict[str, str]
    improvement_plan: list[ActionItem]
    monitoring: list[str]
    questions: list[str]


class GuidancePoint(BaseModel):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    basis: str = ""
    purpose: str = ""


class CategoryGuidance(BaseModel):
    influencing_factors: list[GuidancePoint] = Field(default_factory=list)
    health_guidance: list[GuidancePoint] = Field(default_factory=list)


class CategoryDetail(CategoryCard):
    story: CategoryStory | None = None
    guidance: CategoryGuidance | None = None
    about: str = ""
    findings: list[Finding] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    insight: str = ""
    actions: list[ActionItem] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    caveat: str | None = None
    relationships: list[Relationship] = Field(default_factory=list)


class Priority(BaseModel):
    category_id: str
    title: str
    detail: str
    icon: str
    tone: Literal["attention", "good"]


class OverviewTotals(BaseModel):
    blood_within: int = 0
    blood_outside: int = 0
    blood_no_range: int = 0
    blood_unavailable: int = 0
    risks_assessed: int = 0
    risks_raised: int = 0
    metabolic_age: float | None = None


class UnifiedOverview(BaseModel):
    available: bool = False
    state: Literal["ready", "no_reports"] = "no_reports"
    opening: str = ""
    totals: OverviewTotals = Field(default_factory=OverviewTotals)
    priorities: list[Priority] = Field(default_factory=list)
    categories: list[CategoryCard] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    overall_question: str = "Help me understand my overall health"
    disclaimer: str = "Blood tests measure your current health. Bio-AI estimates future health risks. Neither alone gives a complete picture of your health."
    registry_version: str = "1"
    insights_source: Literal["model", "rules"] = "rules"
    # What this overview could not say, and which rule sets produced it.
    limitations: list[str] = Field(default_factory=list)
    versions: dict[str, str] = Field(default_factory=dict)
