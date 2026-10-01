"""Canonical uploaded-document facts. Distinct from SuperShyft blood records."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocumentKind(str, Enum):
    text_based = "TEXT_BASED"
    scanned = "SCANNED"
    mixed = "MIXED"


class DocumentSubtype(str, Enum):
    lab_report = "LAB_REPORT"
    radiology_report = "RADIOLOGY_REPORT"
    pathology_report = "PATHOLOGY_REPORT"
    health_assessment = "HEALTH_ASSESSMENT"
    genetic_report = "GENETIC_REPORT"
    discharge_summary = "DISCHARGE_SUMMARY"
    prescription = "PRESCRIPTION"
    other_medical_document = "OTHER_MEDICAL_DOCUMENT"


class ProcessingStatus(str, Enum):
    uploaded = "UPLOADED"
    parsing = "PARSING"
    structured_facts_ready = "STRUCTURED_FACTS_READY"
    pageindex_building = "PAGEINDEX_BUILDING"
    ready = "READY"
    partial_failure = "PARTIAL_FAILURE"
    failed = "FAILED"


class PageIndexStatus(str, Enum):
    not_started = "NOT_STARTED"
    building = "BUILDING"
    ready = "READY"
    failed = "FAILED"
    skipped = "SKIPPED"


class ExtractionMethod(str, Enum):
    text = "text"
    table = "table"
    vision = "vision"
    ocr = "ocr"


class DocumentHealthFact(BaseModel):
    canonical_code: str | None = None
    display_name: str
    raw_name: str | None = None
    value: float | str | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    reference_text: str | None = None
    status: str | None = None
    category: str | None = None
    section: str | None = None
    report_date: date | None = None
    page_number: int | None = None
    source_document_id: str
    source_type: str = "uploaded_document"
    extraction_method: str = ExtractionMethod.text.value
    extraction_confidence: float | None = None
    provenance_text: str | None = None
    conflict_group: str | None = None
    mapping_confidence: float | None = None
    original_value: float | str | None = None
    original_unit: str | None = None
    specimen: str | None = None


class DocumentNarrativeFact(BaseModel):
    category: str
    heading: str | None = None
    text: str
    page_start: int | None = None
    page_end: int | None = None
    source_document_id: str
    source_type: str = "uploaded_document"


class PageIndexHit(BaseModel):
    heading: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    text: str
    score: float = 0.0
    node_id: str | None = None


class UploadedDocumentContext(BaseModel):
    document_id: str
    document_name: str | None = None
    document_kind: DocumentKind | None = None
    document_type: DocumentSubtype | None = None
    report_date: date | None = None
    structured_facts: list[DocumentHealthFact] = Field(default_factory=list)
    narrative_sections: list[DocumentNarrativeFact] = Field(default_factory=list)
    conflicts: list[list[DocumentHealthFact]] = Field(default_factory=list)
    pageindex_status: PageIndexStatus = PageIndexStatus.not_started
    processing_status: ProcessingStatus = ProcessingStatus.uploaded
    source_type: str = "uploaded_document"
