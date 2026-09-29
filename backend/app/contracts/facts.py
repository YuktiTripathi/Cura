from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class FactKind(str, Enum):
    measured_data = "MEASURED_DATA"
    user_provided_data = "USER_PROVIDED_DATA"
    medical_evidence = "MEDICAL_EVIDENCE"
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
