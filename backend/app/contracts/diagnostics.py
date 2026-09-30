"""Diagnostic testing DTOs. Catalog fields come from SuperShyft, never from prompts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class HealthGapType(str, Enum):
    relevant_test_missing = "RELEVANT_TEST_MISSING"
    stale_relevant_data = "STALE_RELEVANT_DATA"
    previous_abnormality_needs_follow_up = "PREVIOUS_ABNORMALITY_NEEDS_FOLLOW_UP"
    goal_tracking_data_insufficient = "GOAL_TRACKING_DATA_INSUFFICIENT"
    domain_assessment_incomplete = "DOMAIN_ASSESSMENT_INCOMPLETE"
    user_explicitly_asks_what_to_test = "USER_EXPLICITLY_ASKS_WHAT_TO_TEST"


class TestingRelevance(str, Enum):
    none = "NONE"
    optional = "OPTIONAL"
    useful = "USEFUL"
    clinician_led = "CLINICIAN_LED"


class PackageRelevance(str, Enum):
    high = "HIGH_RELEVANCE"
    moderate = "MODERATE_RELEVANCE"
    optional = "OPTIONAL"
    not_recommended_now = "NOT_RECOMMENDED_NOW"


class TestingUrgency(str, Enum):
    none = "none"
    routine = "routine"
    clinician_led = "clinician_led"


class CatalogItemKind(str, Enum):
    package = "package"
    test_group = "test_group"


class PackageActionType(str, Enum):
    open_package = "OPEN_PACKAGE"
    compare_with_existing = "COMPARE_WITH_EXISTING_RESULTS"


class HealthGap(BaseModel):
    gap_type: HealthGapType
    domain: str | None = None
    missing_entities: list[str] = Field(default_factory=list)
    stale_entities: list[str] = Field(default_factory=list)
    supporting_entities: list[str] = Field(default_factory=list)
    reason: str
    last_measured_on: str | None = None


class TestNeed(BaseModel):
    recommended_test_entities: list[str] = Field(default_factory=list)
    reason: str = ""
    urgency: TestingUrgency = TestingUrgency.none
    testing_relevance: TestingRelevance = TestingRelevance.none
    medical_rationale: str = ""
    lead_gap_type: HealthGapType | None = None


class DiagnosticCatalogItem(BaseModel):
    catalog_id: str
    kind: CatalogItemKind
    display_name: str
    provider: str | None = None
    included_tests: list[str] = Field(default_factory=list)
    included_test_labels: dict[str, str] = Field(default_factory=dict)
    price: float | None = None
    currency: str = "INR"
    status: str = "active"
    gender_suitability: str | None = None
    collection_type: str | None = None
    extra_test_count: int = 0


class PackageCoverage(BaseModel):
    requested: int = 0
    matched: int = 0
    coverage_score: float = 0.0
    matched_entities: list[str] = Field(default_factory=list)
    missing_entities: list[str] = Field(default_factory=list)


class PackageCandidate(BaseModel):
    item: DiagnosticCatalogItem
    coverage: PackageCoverage
    available: bool = True


class CatalogPackageRef(BaseModel):
    id: str
    name: str
    kind: CatalogItemKind = CatalogItemKind.package


class PackageAction(BaseModel):
    type: PackageActionType
    label: str
    package_id: str | None = None
    catalog_kind: CatalogItemKind | None = None


class ExistingResult(BaseModel):
    key: str
    label: str
    measured_on: str | None = None


class PackageComparison(BaseModel):
    included: list[str] = Field(default_factory=list)
    already_have: list[ExistingResult] = Field(default_factory=list)
    adds_information: list[str] = Field(default_factory=list)
    timing_note: str | None = None
    recently_available: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    new_information: list[str] = Field(default_factory=list)


class TestingOption(BaseModel):
    """Patient-facing package recommendation. Metadata is catalog-authored."""

    type: str = "package_recommendation"
    relevance: PackageRelevance = PackageRelevance.optional
    headline: str = ""
    package: CatalogPackageRef
    reason: str = ""
    helps_answer: str = ""
    relevant_tests: list[str] = Field(default_factory=list)
    already_recent: list[str] = Field(default_factory=list)
    primary_action: PackageAction
    secondary_action: PackageAction | None = None
    comparison: PackageComparison = Field(default_factory=PackageComparison)
    catalog_id: str = ""
    kind: CatalogItemKind = CatalogItemKind.package
    display_name: str = ""
    provider: str | None = None
    included_matched_tests: list[str] = Field(default_factory=list)
    included_matched_labels: list[str] = Field(default_factory=list)
    price: float | None = None
    currency: str = "INR"
    medical_rationale: str = ""
    match_reason: str = ""
    cta_label: str = ""
    invitation: str = ""


class DiagnosticsTrace(BaseModel):
    gaps: list[dict] = Field(default_factory=list)
    test_need: dict | None = None
    package_lookup: list[dict] = Field(default_factory=list)
    policy_allowed: bool | None = None
    policy_reason: str | None = None
    package_suggestion_allowed: bool = True
    relevance: str | None = None
    surfaced: dict | None = None
