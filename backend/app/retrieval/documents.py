"""Retrieve already-extracted PDF health facts. Does not re-parse the PDF bytes."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.contracts.evidence import EvidenceRecord
from app.contracts.query import QueryPlan
from app.db.models import Document, DocumentChunk
from app.documents.structured import (
    ExtractedHealthDocument,
    extract_health_document,
    load_structured,
    store_structured,
)
from app.documents.value_extraction import extract_marker_from_text
from app.pipeline.lab_parameters import primary_lab_key, related_keys


def retrieve_structured_documents(
    db: Session,
    principal: AuthenticatedPrincipal,
    plan: QueryPlan,
    document_ids: list[str] | None = None,
) -> tuple[list[ExtractedHealthDocument], list[EvidenceRecord], bool]:
    """Return stored extraction for the authenticated user. Never uses another user's rows."""
    q = db.query(Document).filter(
        Document.user_id == principal.subject_id,
        Document.upload_status != "deleted",
        Document.extraction_status == "completed",
    )
    if document_ids:
        q = q.filter(Document.id.in_(document_ids))
    rows = q.all()
    extracted: list[ExtractedHealthDocument] = []
    evidence: list[EvidenceRecord] = []
    used_stored = False
    topic = plan.topic or primary_lab_key(plan.raw_message)
    why = "why" in (plan.raw_message or "").lower()
    wanted = {topic} if topic and not why else (related_keys(topic) | ({topic} if topic else set()))
    if topic in {"glucose", "fasting_blood_glucose", "postprandial_glucose"}:
        wanted = related_keys(topic) | {topic, "fasting_blood_glucose"}
    if why and topic in {"ldl", "hdl", "cholesterol", "triglycerides"}:
        wanted |= {"ldl", "hdl", "cholesterol", "triglycerides"}
    for row in rows:
        if row.user_id != principal.subject_id:
            continue
        structured = load_structured(row)
        if structured is None:
            chunks = (
                db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id == row.id,
                    DocumentChunk.user_id == principal.subject_id,
                )
                .all()
            )
            structured = extract_health_document(row.id, chunks)
            store_structured(row, structured)
            db.commit()
        else:
            used_stored = True
        extracted.append(structured)
        for marker in structured.biomarkers:
            if wanted and marker.normalized_name not in wanted:
                continue
            if marker.value is None:
                continue
            rng = None
            if marker.reference_low is not None and marker.reference_high is not None:
                rng = f"{marker.reference_low:g}–{marker.reference_high:g} {marker.unit or ''}".strip()
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"ev-{uuid4().hex[:8]}",
                    report_id=row.id,
                    report_type="user_uploaded",
                    report_date=structured.report_date or date.today(),
                    marker=marker.name,
                    source="user_uploaded",
                    document_id=row.id,
                    filename=row.original_filename,
                    page_start=marker.source_page,
                    excerpt=marker.excerpt,
                    value=marker.value,
                    unit=marker.unit,
                    reference_range=rng,
                )
            )
        if wanted and not any(m.normalized_name in wanted and m.value is not None for m in structured.biomarkers):
            fallback = _rag_marker(db, principal.subject_id, row.id, topic)
            if fallback:
                evidence.append(fallback)
    fasting = [e for e in evidence if "fasting" in (e.marker or "").lower()]
    if fasting and topic in {"glucose", "fasting_blood_glucose", None}:
        evidence = fasting[:1]
    elif topic and not why:
        evidence = evidence[:1]
    return extracted, evidence, used_stored


def _rag_marker(db: Session, user_id: str, document_id: str, topic: str | None) -> EvidenceRecord | None:
    if not topic:
        return None
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id, DocumentChunk.user_id == user_id)
        .all()
    )
    for chunk in chunks:
        extracted = extract_marker_from_text(chunk.text, topic, page=chunk.page_start)
        if extracted and extracted.value is not None:
            return EvidenceRecord(
                evidence_id=chunk.id,
                report_id=document_id,
                report_type="user_uploaded",
                report_date=extracted.date or date.today(),
                marker=extracted.name,
                source="user_uploaded",
                document_id=document_id,
                chunk_id=chunk.id,
                page_start=extracted.page or chunk.page_start,
                excerpt=extracted.source_text,
                value=extracted.value,
                unit=extracted.unit,
            )
    return None
