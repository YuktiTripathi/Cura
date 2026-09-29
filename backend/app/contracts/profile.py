from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.facts import ProvenancedFact


class PersonalHealthProfile(BaseModel):
    subject_id: str
    display_name: str | None = None
    health_goals: list[ProvenancedFact] = Field(default_factory=list)
    dietary_preferences: list[ProvenancedFact] = Field(default_factory=list)
    lifestyle: list[ProvenancedFact] = Field(default_factory=list)
    relevant_conditions: list[ProvenancedFact] = Field(default_factory=list)
    medications: list[ProvenancedFact] = Field(default_factory=list)
    allergies: list[ProvenancedFact] = Field(default_factory=list)
    questionnaire: list[ProvenancedFact] = Field(default_factory=list)
    preferences: list[ProvenancedFact] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
