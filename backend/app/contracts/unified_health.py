"""One health picture: measured blood results and predicted Bio-AI risks in the same categories.

Every number, unit, range, score, classification and date is copied from the verified report
data by the backend. The model only writes the wording (summary, interpretation, actions,
follow ups). Measured results and predicted risks sit in one findings list, told apart by
`source_type`, and are never treated as the same kind of evidence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    if_high: str = ""
    if_low: str = ""
    next_step: str = ""


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
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    how_far: Literal["slightly", "moderately", "clearly"] | None = None
    # Predicted risk
    score: float | None = None
    classification: str | None = None
    measured_on: str | None = None
    report_id: str | None = None
    important: bool = False
    education: EducationNote | None = None


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


class CategoryCard(BaseModel):
    id: str
    name: str
    icon: str
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


class CategoryDetail(CategoryCard):
    about: str = ""
    findings: list[Finding] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    insight: str = ""
    actions: list[ActionItem] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    caveat: str | None = None


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
