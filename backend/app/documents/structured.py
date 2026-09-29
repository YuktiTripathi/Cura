"""One-shot structured extraction from already-parsed PDF chunks. Never invents values."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any  # chunks may be ORM rows or ChunkDraft

from pydantic import BaseModel, Field

from app.db.models import Document
from app.documents.value_extraction import extract_marker_from_text, find_report_date
from app.pipeline.lab_parameters import PARAMETERS, display_name_for

logger = logging.getLogger("cura.documents")


class ExtractedBiomarker(BaseModel):
    name: str
    normalized_name: str
    original_field: str | None = None
    value: float | None = None
    unit: str | None = None
    reference_range: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    flag: str | None = None
    source_page: int | None = None
    excerpt: str | None = None
    confidence: str = "low"


class ExtractedRisk(BaseModel):
    name: str
    normalized_name: str
    value: float | None = None
    unit: str | None = None
    source_page: int | None = None


class ExtractedHealthDocument(BaseModel):
    document_id: str
    document_type: str | None = None
    report_date: date | None = None
    biomarkers: list[ExtractedBiomarker] = Field(default_factory=list)
    bio_ai_metrics: list[ExtractedRisk] = Field(default_factory=list)
    extraction_method: str = "deterministic"
    extracted_once: bool = True


def extract_structured_from_chunks(
    document_id: str,
    chunks: list[Any],
) -> ExtractedHealthDocument:
    biomarkers: list[ExtractedBiomarker] = []
    seen: set[str] = set()
    report_date: date | None = None
    for chunk in chunks:
        text = chunk.text or ""
        report_date = report_date or find_report_date(text)
        for param in PARAMETERS:
            if param.key == "cholesterol" and re.search(r"\b(ldl|hdl)\s+cholesterol\b", text, re.I):
                if not re.search(r"\btotal cholesterol\b", text, re.I):
                    continue
            extracted = extract_marker_from_text(text, param.key, page=chunk.page_start)
            if not extracted or extracted.value is None:
                continue
            existing = next((b for b in biomarkers if b.normalized_name == param.key), None)
            if existing:
                if existing.reference_low is None and extracted.reference_low is not None:
                    existing.reference_low = extracted.reference_low
                    existing.reference_high = extracted.reference_high
                continue
            seen.add(param.key)
            biomarkers.append(
                ExtractedBiomarker(
                    name=extracted.name or display_name_for(param.key),
                    normalized_name=param.key,
                    value=extracted.value,
                    unit=extracted.unit,
                    reference_low=extracted.reference_low,
                    reference_high=extracted.reference_high,
                    source_page=extracted.page or chunk.page_start,
                    excerpt=(extracted.source_text or "")[:200],
                    confidence=extracted.confidence,
                )
            )
    return ExtractedHealthDocument(
        document_id=document_id,
        document_type="blood_report" if biomarkers else None,
        report_date=report_date,
        biomarkers=biomarkers,
        extraction_method="deterministic",
        extracted_once=True,
    )


def extract_health_document(document_id: str, chunks: list[Any]) -> ExtractedHealthDocument:
    deterministic = extract_structured_from_chunks(document_id, chunks)
    try:
        from app.documents.llm_extract import extract_structured_with_llm

        llm_doc = extract_structured_with_llm(document_id, chunks)
    except Exception:
        logger.warning("llm_pdf_extract_failed document_id=%s", document_id)
        return deterministic
    if llm_doc is None:
        return deterministic
    if not llm_doc.biomarkers and deterministic.biomarkers:
        llm_doc = llm_doc.model_copy(
            update={
                "biomarkers": deterministic.biomarkers,
                "extraction_method": "llm_fallback_deterministic",
            }
        )
    return llm_doc


def store_structured(row: Document, extracted: ExtractedHealthDocument) -> None:
    payload: dict[str, Any] = {}
    if row.metadata_json:
        try:
            payload = json.loads(row.metadata_json)
        except json.JSONDecodeError:
            payload = {}
    payload["structured_health"] = extracted.model_dump(mode="json")
    row.metadata_json = json.dumps(payload)


def load_structured(row: Document) -> ExtractedHealthDocument | None:
    if not row.metadata_json:
        return None
    try:
        payload = json.loads(row.metadata_json)
    except json.JSONDecodeError:
        return None
    raw = payload.get("structured_health")
    if not isinstance(raw, dict):
        return None
    try:
        return ExtractedHealthDocument.model_validate(raw)
    except Exception:
        logger.debug("structured_health_invalid document_id=%s", row.id)
        return None
