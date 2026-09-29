from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.contracts.facts import ProvenancedFact

ALLOWED_GOAL_CODES = (
    "improve_cholesterol",
    "improve_metabolic_health",
    "improve_fitness",
    "improve_nutrition",
    "weight_management",
)

GOAL_LABELS = {
    "improve_cholesterol": "Improve cholesterol",
    "improve_metabolic_health": "Improve metabolic health",
    "improve_fitness": "Improve fitness",
    "improve_nutrition": "Improve nutrition",
    "weight_management": "Weight management",
}

GOAL_METRICS = {
    "improve_cholesterol": ("ldl", "hdl", "triglycerides", "cholesterol"),
    "improve_metabolic_health": ("hba1c", "fasting_blood_glucose", "triglycerides"),
    "improve_fitness": (),
    "improve_nutrition": (),
    "weight_management": (),
}


class HealthGoal(BaseModel):
    id: str | None = None
    subject_id: str
    goal_code: str
    label: str
    status: str = "active"
    created_at: datetime | str | None = None


class GoalProgress(BaseModel):
    goal_code: str
    label: str
    status: str = "active"
    direction: str | None = None
    summary: str
    metrics: list[ProvenancedFact] = Field(default_factory=list)
    sufficient_history: bool = False


class GoalListRequest(BaseModel):
    goals: list[str] = Field(default_factory=list)


class GoalListResponse(BaseModel):
    subject_id: str
    goals: list[HealthGoal] = Field(default_factory=list)
    progress: list[GoalProgress] = Field(default_factory=list)
