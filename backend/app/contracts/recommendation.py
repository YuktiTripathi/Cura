from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RecommendationCategory = Literal[
    "foods_to_include",
    "foods_to_limit",
    "meal_patterns",
    "lifestyle_actions",
    "hydration",
    "activity",
    "sleep",
    "stress",
]


class RecommendationCandidate(BaseModel):
    category: RecommendationCategory
    text: str
    rationale: str | None = None
    evidence_codes: list[str] = Field(default_factory=list)


class ApprovedRecommendation(RecommendationCandidate):
    policy_status: Literal["approved"] = "approved"
    reason: str | None = None
    supporting_fact_ids: list[str] = Field(default_factory=list)
    urgency: str = "routine"
    personal_relevance: str | None = None


class RecommendationResult(BaseModel):
    approved: list[ApprovedRecommendation] = Field(default_factory=list)
    rejected_count: int = 0
    flags: list[str] = Field(default_factory=list)
