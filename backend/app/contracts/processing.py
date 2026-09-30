"""User-facing processing stages. Not internal debug traces."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProcessingStage(str, Enum):
    request_received = "REQUEST_RECEIVED"
    planning = "PLANNING"
    fetching_personal_data = "FETCHING_PERSONAL_DATA"
    fetching_blood_data = "FETCHING_BLOOD_DATA"
    fetching_bioai_data = "FETCHING_BIOAI_DATA"
    fetching_questionnaire = "FETCHING_QUESTIONNAIRE"
    fetching_history = "FETCHING_HISTORY"
    reading_document = "READING_DOCUMENT"
    retrieving_document_section = "RETRIEVING_DOCUMENT_SECTION"
    checking_medical_evidence = "CHECKING_MEDICAL_EVIDENCE"
    comparing_results = "COMPARING_RESULTS"
    analyzing_trends = "ANALYZING_TRENDS"
    personalizing = "PERSONALIZING"
    reasoning = "REASONING"
    checking_safety = "CHECKING_SAFETY"
    composing_response = "COMPOSING_RESPONSE"
    complete = "COMPLETE"


class RequestFamily(str, Enum):
    blood = "blood"
    bioai = "bioai"
    questionnaire = "questionnaire"
    document = "document"
    general = "general"
    trend = "trend"
    cross = "cross"
    package = "package"
    followup = "followup"
    priority = "priority"
    personal = "personal"


class ProcessingEvent(BaseModel):
    stage: ProcessingStage
    message_key: str
    family: RequestFamily = RequestFamily.personal
    follow_up: bool = False
    elapsed_ms: int | None = None


class TimingReport(BaseModel):
    planning_ms: int | None = None
    database_retrieval_ms: int | None = None
    context_build_ms: int | None = None
    document_retrieval_ms: int | None = None
    reasoner_ms: int | None = None
    validation_ms: int | None = None
    response_compose_ms: int | None = None
    total_ms: int | None = None
    llm_calls: int = 0
    db_queries: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    marks: dict[str, int] = Field(default_factory=dict)
