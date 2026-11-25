from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    # Set only by an explicit entry point. Message text must not infer this.
    entry_point: Literal["blood_report_overview", "risk_explainer", "health_area"] | None = None
    category_id: str | None = Field(default=None, max_length=64)
    finding_id: str | None = Field(default=None, max_length=128)
    snapshot_version: str | None = Field(default=None, max_length=64)
    # Which suggested question was tapped, and which sections the person had already seen on the screen.
    # These are labels only. Personal values are never accepted from the browser; the server looks them up.
    suggested_question_id: str | None = Field(default=None, max_length=64)
    displayed_sections: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("displayed_sections")
    @classmethod
    def _known_sections(cls, value: list[str]) -> list[str]:
        allowed = {"what_it_is", "inside_body", "your_result", "reference_range", "why_it_matters", "limitations", "previous_result", "related_results", "assessment", "score"}
        return [item for item in value if item in allowed]

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
