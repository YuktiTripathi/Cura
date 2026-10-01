from pydantic import BaseModel, Field

from app.contracts.starters import StarterQuestionSet


class MeCapabilities(BaseModel):
    has_blood_report: bool = False
    has_bio_ai_report: bool = False
    has_questionnaire: bool = False
    has_nutrition: bool = False
    has_health_scenario: bool = False
    has_health_goals: bool = False
    # Speech-to-text is configured on this deployment (VOICE_ENABLED + STT_PROVIDER).
    voice_input: bool = False


class MeResponse(BaseModel):
    user_id: str | int
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    greeting: str
    profile_available: bool = False
    capabilities: MeCapabilities = Field(default_factory=MeCapabilities)
    starters: StarterQuestionSet = Field(default_factory=StarterQuestionSet)
