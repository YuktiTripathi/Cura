from pydantic import BaseModel, Field


class LifestyleContext(BaseModel):
    subject_id: str
    activity_level: str | None = None
    sleep_quality: str | None = None
    notes: list[str] = Field(default_factory=list)
    dietary_preference: str | None = None
    allergies: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)


class HabitsSummary(BaseModel):
    activity_level: str | None = None
    sleep_quality: str | None = None
    dietary_preference: str | None = None
    goals: list[str] = Field(default_factory=list)
    available: bool = False
