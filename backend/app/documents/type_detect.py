"""Detect PDF kind (text/scanned/mixed) and medical subtype from extracted pages."""

from __future__ import annotations

import re

from app.contracts.uploaded_document import DocumentKind, DocumentSubtype
from app.core.config import settings
from app.documents.extraction import ExtractedPage

_SUBTYPES: list[tuple[DocumentSubtype, re.Pattern[str]]] = [
    (DocumentSubtype.radiology_report, re.compile(r"\b(radiolog|impression|ct scan|mri|ultrasound|x-?ray)\b", re.I)),
    (DocumentSubtype.pathology_report, re.compile(r"\b(patholog|microscopy|histolog|biopsy|cytolog)\b", re.I)),
    (DocumentSubtype.genetic_report, re.compile(r"\b(genetic|genomic|variant|allele|sequencing)\b", re.I)),
    (DocumentSubtype.discharge_summary, re.compile(r"\b(discharge summary|hospital course|admitted)\b", re.I)),
    (DocumentSubtype.prescription, re.compile(r"\b(prescription|sig:|rx\b|take \d+)\b", re.I)),
    (DocumentSubtype.health_assessment, re.compile(r"\b(health assessment|executive health|wellness report)\b", re.I)),
    (
        DocumentSubtype.lab_report,
        re.compile(r"\b(ldl|hdl|hba1c|tsh|creatinine|hemoglobin|reference range|lipid profile)\b", re.I),
    ),
]


def detect_document_kind(pages: list[ExtractedPage]) -> DocumentKind:
    if not pages:
        return DocumentKind.scanned
    sparse = [page for page in pages if page.character_count < settings.document_sparse_page_chars]
    ocr_pages = [page for page in pages if (page.method or "") == "ocr"]
    if len(sparse) == len(pages):
        return DocumentKind.scanned
    if sparse or ocr_pages:
        if len(sparse) > len(pages) / 2 or len(ocr_pages) > len(pages) / 2:
            return DocumentKind.scanned
        return DocumentKind.mixed
    return DocumentKind.text_based


def detect_document_subtype(pages: list[ExtractedPage]) -> DocumentSubtype:
    blob = "\n".join((page.text or "")[:2000] for page in pages[:8])
    for subtype, pattern in _SUBTYPES:
        if pattern.search(blob):
            return subtype
    return DocumentSubtype.other_medical_document
