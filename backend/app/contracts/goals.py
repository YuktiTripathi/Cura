from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.contracts.facts import ProvenancedFact

ALLOWED_GOAL_CODES = (
    "improve_cholesterol",
    "improve_lipids",
    "improve_metabolic_health",
    "improve_fitness",
    "improve_nutrition",
    "weight_management",
    "improve_energy",
    "improve_sleep",
    "improve_blood_sugar",
    "improve_iron_status",
    "improve_vitamin_d",
    "healthy_aging",
    "reduce_cardiovascular_risk",
    "general_preventive_health",
)

GOAL_LABELS = {
    "improve_cholesterol": "Improve cholesterol",
    "improve_lipids": "Improve lipids",
    "improve_metabolic_health": "Improve metabolic health",
    "improve_fitness": "Improve fitness",
    "improve_nutrition": "Improve nutrition",
    "weight_management": "Weight management",
    "improve_energy": "Improve energy",
    "improve_sleep": "Improve sleep",
    "improve_blood_sugar": "Improve blood sugar",
    "improve_iron_status": "Improve iron status",
    "improve_vitamin_d": "Improve Vitamin D",
    "healthy_aging": "Healthy aging",
    "reduce_cardiovascular_risk": "Reduce cardiovascular risk",
    "general_preventive_health": "General preventive health",
}

GOAL_METRICS = {
    "improve_cholesterol": ("ldl", "hdl", "triglycerides", "cholesterol"),
    "improve_lipids": ("ldl", "hdl", "triglycerides", "cholesterol"),
    "improve_metabolic_health": (
        "hba1c",
        "fasting_blood_glucose",
        "glucose",
        "triglycerides",
        "hdl",
        "bmi",
        "waist",
    ),
    "improve_fitness": ("bmi", "waist"),
    "improve_nutrition": ("vitamin_d", "vitamin_b12", "iron", "ferritin"),
    "weight_management": ("bmi", "waist", "triglycerides", "hdl"),
    "improve_energy": ("hemoglobin", "ferritin", "iron", "vitamin_b12", "vitamin_d", "tsh"),
    "improve_sleep": (),
    "improve_blood_sugar": ("hba1c", "fasting_blood_glucose", "glucose"),
    "improve_iron_status": ("hemoglobin", "mcv", "mch", "iron", "ferritin", "tibc", "transferrin"),
    "improve_vitamin_d": ("vitamin_d",),
    "healthy_aging": ("hba1c", "ldl", "egfr", "tsh", "vitamin_d"),
    "reduce_cardiovascular_risk": ("ldl", "hdl", "triglycerides", "hba1c", "blood_pressure", "crp"),
    "general_preventive_health": ("hba1c", "ldl", "tsh", "vitamin_d", "hemoglobin"),
}

GOAL_PHRASES = (
    ("improve_energy", ("improving energy", "better energy", "more energy", "less fatigue", "less tired")),
    ("improve_metabolic_health", ("metabolic health", "better metabolic")),
    ("improve_sleep", ("improve sleep", "better sleep", "sleeping better")),
    ("improve_iron_status", ("iron status", "iron stores", "iron levels")),
    ("improve_vitamin_d", ("vitamin d",)),
    ("improve_blood_sugar", ("blood sugar", "glucose control", "hba1c")),
    ("improve_lipids", ("cholesterol", "lipids")),
    ("improve_cholesterol", ("improve cholesterol",)),
    ("weight_management", ("lose weight", "weight management", "weight loss")),
    ("improve_fitness", ("improve fitness", "get fitter")),
    ("improve_nutrition", ("improve nutrition", "eat better")),
    ("reduce_cardiovascular_risk", ("heart health", "cardiovascular risk")),
    ("healthy_aging", ("healthy aging", "ageing")),
    ("general_preventive_health", ("stay healthy", "preventive health")),
)


class HealthGoal(BaseModel):
    id: str | None = None
    subject_id: str
    goal_code: str
    label: str
    status: str = "active"
    created_at: datetime | str | None = None
    source: str = "user_goal"
    target_metrics: list[str] = Field(default_factory=list)
    review_interval: str | None = None


class GoalProgress(BaseModel):
    goal_code: str
    label: str
    status: str = "active"
    direction: str | None = None
    summary: str
    metrics: list[ProvenancedFact] = Field(default_factory=list)
    sufficient_history: bool = False
    improving: list[str] = Field(default_factory=list)
    stable: list[str] = Field(default_factory=list)
    worsening: list[str] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)


class GoalListRequest(BaseModel):
    goals: list[str] = Field(default_factory=list)


class GoalListResponse(BaseModel):
    subject_id: str
    goals: list[HealthGoal] = Field(default_factory=list)
    progress: list[GoalProgress] = Field(default_factory=list)
