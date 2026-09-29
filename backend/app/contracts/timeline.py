from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contracts.facts import ProvenancedFact


class TimelineEvent(BaseModel):
    event_type: str
    occurred_at: date | datetime | str | None = None
    source: str
    report_id: str | None = None
    document_id: str | None = None
    title: str
    facts: list[ProvenancedFact] = Field(default_factory=list)


class PersonalHealthTimeline(BaseModel):
    subject_id: str
    events: list[TimelineEvent] = Field(default_factory=list)
