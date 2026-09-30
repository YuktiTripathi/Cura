from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contracts.facts import ProvenancedFact


class QuestionnaireAnswer(BaseModel):
    response_id: str
    assessment_instance_id: str
    question_id: str
    question_key: str
    question: str
    value: str | float | None = None
    unit: str | None = None
    response_type: str
    category_keys: list[str] = Field(default_factory=list)
    recorded_at: date | datetime | str | None = None
    source: str = "questionnaire"
    provenance: str = "SuperShyft"
    subject_id: str
    is_carried_forward: bool = False

    def as_fact(self) -> ProvenancedFact:
        from app.contracts.facts import FactKind

        return ProvenancedFact(
            fact=self.question_key,
            value=self.value,
            unit=self.unit,
            source="questionnaire",
            report_id=self.assessment_instance_id,
            measured_at=self.recorded_at,
            fact_type=FactKind.questionnaire_response,
            subject_id=self.subject_id,
            notes=[
                f"question={self.question}",
                f"response_type={self.response_type}",
                f"provenance={self.provenance}",
            ],
            question_id=self.question_id,
            questionnaire_id=self.assessment_instance_id,
            response_id=self.response_id,
            response_type=self.response_type,
            source_type="supershyft_questionnaire",
            source_id=self.response_id,
        )


class QuestionnaireInstance(BaseModel):
    assessment_instance_id: str
    subject_id: str
    package_id: str | None = None
    package_code: str | None = None
    status: str | None = None
    recorded_at: date | datetime | str | None = None
    answers: list[QuestionnaireAnswer] = Field(default_factory=list)


class LifestyleSummary(BaseModel):
    activity_level: ProvenancedFact | None = None
    sleep_pattern: ProvenancedFact | None = None
    dietary_pattern: ProvenancedFact | None = None
