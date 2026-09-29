from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class JevIntent(str, Enum):
    casual_conversation = "casual_conversation"
    personal_profile_lookup = "personal_profile_lookup"
    lab_result_lookup = "lab_result_lookup"
    lab_result_interpretation = "lab_result_interpretation"
    bio_ai_report_lookup = "bio_ai_report_lookup"
    bio_ai_report_interpretation = "bio_ai_report_interpretation"
    health_trend_analysis = "health_trend_analysis"
    questionnaire_lookup = "questionnaire_lookup"
    questionnaire_interpretation = "questionnaire_interpretation"
    uploaded_document_query = "uploaded_document_query"
    nutrition_question = "nutrition_question"
    lifestyle_question = "lifestyle_question"
    fitness_question = "fitness_question"
    general_health_question = "general_health_question"
    medication_question = "medication_question"
    symptom_question = "symptom_question"
    preventive_health_question = "preventive_health_question"
    medical_risk_question = "medical_risk_question"
    general_information = "general_information"
    unsupported = "unsupported"
    clarification = "clarification"


class JevSource(str, Enum):
    profile = "profile"
    assessment = "assessment"
    questionnaire = "questionnaire"
    blood_reports = "blood_reports"
    lab_results = "lab_results"
    bio_ai_report = "bio_ai_report"
    bio_ai_trends = "bio_ai_trends"
    health_metrics = "health_metrics"
    uploaded_documents = "uploaded_documents"
    nutrition = "nutrition"
    none = "none"
    multiple_sources = "multiple_sources"


class JevOperation(str, Enum):
    none = "none"
    lookup = "lookup"
    retrieve_and_explain = "retrieve_and_explain"
    trend = "trend"
    compare = "compare"
    summarize = "summarize"
    interpret = "interpret"
    general_answer = "general_answer"
    clarify = "clarify"


class JevTimeRange(str, Enum):
    none = "none"
    latest = "latest"
    previous = "previous"
    historical = "historical"
    three_months = "3_months"
    six_months = "6_months"
    twelve_months = "12_months"
    custom = "custom"


class JevRoutingState(BaseModel):
    current_message: str
    previous_user_message: str | None = None
    previous_intent: str | None = None
    previous_personal_data_used: bool = False
    current_topic: str | None = None
    prior_source_mode: str | None = None
    selected_document_count: int = 0
    uploaded_document_available: bool = False
    supported_capabilities: list[str] = Field(default_factory=list)


class JevNoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: float = Field(ge=0, le=1)


class JevChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)


JevAnswer = Annotated[JevNoulAnswer | JevChoiceAnswer, Field(discriminator="type")]


class JevUsage(BaseModel):
    cost: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class JevDecisionsResponse(BaseModel):
    answers: dict[str, JevAnswer]
    id: str | None = None
    model: str | None = None
    provider: str | None = None
    usage: JevUsage = Field(default_factory=JevUsage)


class JevDecision(BaseModel):
    intent: JevIntent
    source: JevSource = JevSource.none
    operation: JevOperation = JevOperation.none
    requires_personal_data: bool = False
    requires_historical_data: bool = False
    requires_document_search: bool = False
    requires_clarification: bool = False
    requested_entities: list[str] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    time_range: JevTimeRange = JevTimeRange.none
    confidence: float | None = None
    field_confidences: dict[str, float] = Field(default_factory=dict)
    clarification_question: str | None = None

    @property
    def requires_retrieval(self) -> bool:
        return self.requires_personal_data or self.requires_document_search


class JevTrace(BaseModel):
    called: bool = False
    fallback: bool = False
    fallback_reason: str | None = None
    latency_ms: int | None = None
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    decision: JevDecision | None = None
    validated: bool = False
    validation_error: str | None = None
    overridden: bool = False
