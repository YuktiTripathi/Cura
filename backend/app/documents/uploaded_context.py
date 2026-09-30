"""Build UploadedDocumentContext from a stored document row."""

from __future__ import annotations

from app.contracts.uploaded_document import (
    DocumentKind,
    DocumentSubtype,
    PageIndexStatus,
    ProcessingStatus,
    UploadedDocumentContext,
)
from app.db.models import Document
from app.documents.facts import conflict_groups, facts_from_extracted
from app.documents.metadata import load_meta
from app.documents.pageindex import PageIndexTree, narrative_facts_from_tree
from app.documents.structured import load_structured


def context_from_row(row: Document) -> UploadedDocumentContext:
    meta = load_meta(row)
    extracted = load_structured(row)
    facts = facts_from_extracted(extracted) if extracted else []
    tree = None
    raw_tree = meta.get("pageindex")
    if isinstance(raw_tree, dict):
        try:
            tree = PageIndexTree.model_validate(raw_tree)
        except Exception:
            tree = None
    narrative = narrative_facts_from_tree(tree) if tree else []
    kind = meta.get("document_kind")
    subtype = meta.get("document_subtype") or (extracted.document_type if extracted else None)
    pageindex = meta.get("pageindex_status") or PageIndexStatus.not_started.value
    processing = meta.get("processing_status")
    if not processing:
        if row.extraction_status == "failed":
            processing = ProcessingStatus.failed.value
        elif row.extraction_status in {"not_started", "processing"}:
            processing = ProcessingStatus.parsing.value
        elif pageindex == PageIndexStatus.ready.value:
            processing = ProcessingStatus.ready.value
        elif facts:
            processing = ProcessingStatus.structured_facts_ready.value
        else:
            processing = ProcessingStatus.parsing.value
    return UploadedDocumentContext(
        document_id=row.id,
        document_name=row.original_filename,
        document_kind=DocumentKind(kind) if kind in {item.value for item in DocumentKind} else None,
        document_type=_subtype(subtype),
        report_date=extracted.report_date if extracted else None,
        structured_facts=facts,
        narrative_sections=narrative,
        conflicts=conflict_groups(facts),
        pageindex_status=PageIndexStatus(pageindex) if pageindex in {item.value for item in PageIndexStatus} else PageIndexStatus.not_started,
        processing_status=ProcessingStatus(processing) if processing in {item.value for item in ProcessingStatus} else ProcessingStatus.parsing,
    )


def _subtype(value: str | None) -> DocumentSubtype | None:
    if not value:
        return None
    mapped = {
        "blood_report": DocumentSubtype.lab_report.value,
        "lab": DocumentSubtype.lab_report.value,
    }.get(value, value)
    try:
        return DocumentSubtype(mapped)
    except ValueError:
        return DocumentSubtype.other_medical_document
