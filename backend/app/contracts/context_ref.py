from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ContextRef(BaseModel):
    type: Literal[
        "blood_marker",
        "blood_report",
        "bio_ai_risk",
        "bio_ai_report",
        "health_scenario",
        "nutrition_item",
        "uploaded_document",
    ]
    source: Literal["supershyft", "user_uploaded"]
    marker_code: str | None = Field(default=None, max_length=128)
    risk_code: str | None = Field(default=None, max_length=128)
    report_id: str | None = Field(default=None, max_length=128)
    document_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def validate_identifiers(self) -> "ContextRef":
        if self.type == "blood_marker" and not self.marker_code:
            raise ValueError("blood_marker context requires marker_code")
        if self.type == "bio_ai_risk" and not self.risk_code:
            raise ValueError("bio_ai_risk context requires risk_code")
        if self.type == "uploaded_document" and not self.document_id:
            raise ValueError("uploaded_document context requires document_id")
        if self.source == "user_uploaded" and not self.document_id:
            raise ValueError("user_uploaded context requires document_id")
        return self
