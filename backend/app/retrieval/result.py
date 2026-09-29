from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.evidence import EvidenceRecord
from app.contracts.lifestyle import LifestyleContext
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
    document_evidence: list[EvidenceRecord] = field(default_factory=list)
    skipped_reason: str | None = None
    source_names: list[str] = field(default_factory=list)
    status: str = "not_required"
    error_reason: str | None = None

    def has_health_values(self) -> bool:
        if any(r.markers for r in self.blood_reports):
            return True
        if any(r.risks or r.metabolic_age is not None for r in self.bio_ai_reports):
            return True
        if any(ev.value is not None for ev in self.document_evidence):
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
