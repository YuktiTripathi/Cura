from pydantic import BaseModel, Field

from app.contracts.recommendation import RecommendationCandidate


class LLMCompletion(BaseModel):
    text: str
    model: str
    provider: str


class LLMClaim(BaseModel):
    text: str
    evidence_codes: list[str] = Field(default_factory=list)


class LLMStructuredOutput(BaseModel):
    answer: str
    claims: list[LLMClaim] = Field(default_factory=list)
    recommendation_candidates: list[RecommendationCandidate] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    escalation: str | None = None
    parse_error: str | None = None
    finish_reason: str | None = None
    truncated: bool = False
    overall_summary: str | None = None
    themes: list[dict] = Field(default_factory=list)
