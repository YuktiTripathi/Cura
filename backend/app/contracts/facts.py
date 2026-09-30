from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class FactKind(str, Enum):
    measured_data = "MEASURED_DATA"
    measured_personal_fact = "MEASURED_PERSONAL_FACT"
    user_provided_data = "USER_PROVIDED_DATA"
    user_stated_health_information = "USER_STATED_HEALTH_INFORMATION"
    questionnaire_response = "QUESTIONNAIRE_RESPONSE"
    bio_ai_assessment = "BIO_AI_ASSESSMENT"
    medical_evidence = "MEDICAL_EVIDENCE"
    general_medical_knowledge = "GENERAL_MEDICAL_KNOWLEDGE"
    model_interpretation = "MODEL_INTERPRETATION"
    user_preference = "USER_PREFERENCE"
    model_recommendation = "MODEL_RECOMMENDATION"


class ProvenancedFact(BaseModel):
    fact: str
    value: float | str | None = None
    unit: str | None = None
    source: str
    report_id: str | None = None
    document_id: str | None = None
    measured_at: date | datetime | str | None = None
    fact_type: FactKind
    subject_id: str | None = None
    status: str | None = None
    notes: list[str] = Field(default_factory=list)
    question_id: str | None = None
    questionnaire_id: str | None = None
    response_id: str | None = None
    response_type: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    page: int | None = None
    confidence: str | None = None
