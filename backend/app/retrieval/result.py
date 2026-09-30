from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.evidence import EvidenceRecord
from app.contracts.lifestyle import LifestyleContext
from app.contracts.operations import SourceOutcome, SourceOutcomeStatus
from app.contracts.questionnaire import QuestionnaireInstance
from app.documents.structured import ExtractedHealthDocument


@dataclass
class HealthRetrievalResult:
    invoked: bool = False
    ihr_called: bool = False
    documents_called: bool = False
    used_stored_document_extraction: bool = False
    reparsed_pdf: bool = False
    blood_reports: list[BloodReport] = field(default_factory=list)
    bio_ai_reports: list[BioAIReport] = field(default_factory=list)
    lifestyle: LifestyleContext | None = None
    documents: list[ExtractedHealthDocument] = field(default_factory=list)
    questionnaire_instances: list[QuestionnaireInstance] = field(default_factory=list)
    questionnaire_called: bool = False
    document_evidence: list[EvidenceRecord] = field(default_factory=list)
    skipped_reason: str | None = None
    source_names: list[str] = field(default_factory=list)
    status: str = "not_required"
    error_reason: str | None = None
    source_outcomes: list[SourceOutcome] = field(default_factory=list)

    def record_outcome(self, source: str, *, requested: bool, records: int = 0, unavailable: bool = False, unauthorized: bool = False) -> None:
        if not requested:
            status = SourceOutcomeStatus.not_requested
        elif unauthorized:
            status = SourceOutcomeStatus.unauthorized
        elif unavailable:
            status = SourceOutcomeStatus.unavailable
        elif records:
            status = SourceOutcomeStatus.retrieved
        else:
            status = SourceOutcomeStatus.empty
        self.source_outcomes.append(SourceOutcome(source=source, status=status, record_count=records))

    def has_health_values(self) -> bool:
        if any(r.markers for r in self.blood_reports):
            return True
        if any(r.risks or r.metabolic_age is not None for r in self.bio_ai_reports):
            return True
        if any(ev.value is not None for ev in self.document_evidence):
            return True
        if any(instance.answers for instance in self.questionnaire_instances):
            return True
        return False

    def finalize_status(self) -> str:
        if self.status in {"provider_unavailable", "unauthorized", "extraction_failed", "error"}:
            return self.status
        if not self.invoked:
            self.status = "not_required"
            return self.status
        if self.has_health_values():
            self.status = "success"
            return self.status
        self.status = "no_data"
        return self.status
