from __future__ import annotations

from pydantic import BaseModel, Field


class InsightCandidate(BaseModel):
    """Computed change candidate. Never sent unsolicited in chat."""

    insight_type: str
    topic: str
    summary: str
    direction: str | None = None
    delivery: str = "on_request"
    source: str = "cura_derived"
    report_ids: list[str] = Field(default_factory=list)
