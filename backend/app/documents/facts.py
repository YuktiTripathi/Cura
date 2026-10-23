"""Canonical DocumentHealthFacts from extracted pages. Reuses lab ontology; does not merge conflicts."""

from __future__ import annotations

import re

from app.contracts.uploaded_document import DocumentHealthFact
from app.documents.extraction import ExtractedPage
from app.documents.structured import ExtractedBiomarker, ExtractedHealthDocument
from app.documents.value_extraction import extract_known_observations, extract_unknown_observations, find_report_date
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.lab_parameters import canonicalize_marker_name, display_name_for, resolve_biomarker


def confidence_score(raw: str | None) -> float | None:
    if raw == "high":
        return 0.9
    if raw == "low":
        return 0.4
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def infer_status(value: float | None, low: float | None, high: float | None, flag: str | None) -> str | None:
    if flag:
        return str(flag).lower()
    if value is None or (low is None and high is None):
        return None
    # One-sided ranges ("< 100", "> 40") are common on lipid and inflammation panels.
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def facts_from_extracted(extracted: ExtractedHealthDocument) -> list[DocumentHealthFact]:
    facts: list[DocumentHealthFact] = []
    for marker in extracted.biomarkers:
        verified = (getattr(marker, "resolution_status", None) or "verified") == "verified"
        matched = resolve_biomarker(marker.normalized_name or marker.name or marker.original_field or "") if verified else None
        code = None if not verified else (
            (matched.canonical_code if matched else None)
            or canonicalize_marker_name(marker.normalized_name or marker.name or "")
            or marker.normalized_name
        )
        domain = domain_for_entity(code) if code else None
        facts.append(
            DocumentHealthFact(
                canonical_code=code,
                display_name=display_name_for(code or "") or marker.name,
                raw_name=marker.original_field or marker.name,
                value=marker.value,
                unit=marker.unit,
                original_value=marker.value,
                original_unit=marker.unit,
                reference_low=marker.reference_low,
                reference_high=marker.reference_high,
                reference_text=marker.reference_range,
                status=infer_status(marker.value if isinstance(marker.value, (int, float)) else None, marker.reference_low, marker.reference_high, marker.flag),
                category=domain.code if domain else None,
                report_date=getattr(marker, "collection_date", None) or extracted.report_date,
                page_number=marker.source_page,
                source_document_id=extracted.document_id,
                extraction_method=marker.extraction_method or "text",
                extraction_confidence=confidence_score(marker.confidence),
                mapping_confidence=matched.confidence if matched else confidence_score(marker.confidence),
                provenance_text=marker.excerpt,
                measurement_kind=getattr(marker, "measurement_kind", None) or "measured",
                section=getattr(marker, "section", None),
                specimen=getattr(marker, "specimen", None),
                method=getattr(marker, "method", None),
                temporal_scope=getattr(marker, "temporal_scope", None) or "current",
                resolution_status=getattr(marker, "resolution_status", None) or "verified",
                resolution_reason=getattr(marker, "resolution_reason", None),
                raw_value=getattr(marker, "raw_value", None),
            )
        )
    return attach_conflicts(dedupe_identical(facts))


def extract_facts_from_pages(document_id: str, pages: list[ExtractedPage]) -> ExtractedHealthDocument:
    biomarkers: list[ExtractedBiomarker] = []
    report_date = None
    for page in pages:
        text = page.text or ""
        report_date = report_date or find_report_date(text)
        method = page.method or "text"
        observations = [
            *extract_known_observations(text, page.page_number),
            *extract_unknown_observations(text, page.page_number),
        ]
        for extracted in observations:
            if extracted.value is None:
                continue
            code = extracted.parameter if extracted.resolution_status == "verified" else (extracted.surface_name or extracted.name)
            same = [
                item
                for item in biomarkers
                if item.normalized_name == code
                and item.measurement_kind == extracted.measurement_kind
                and item.resolution_status == extracted.resolution_status
                and _close(item.value, extracted.value)
                and item.source_page == (extracted.page or page.page_number)
                and (item.collection_date or None) == extracted.date
                and (item.temporal_scope or "current") == extracted.temporal_scope
            ]
            if same:
                continue
            biomarkers.append(
                ExtractedBiomarker(
                    name=extracted.surface_name or extracted.name or display_name_for(extracted.parameter),
                    normalized_name=code,
                    original_field=extracted.surface_name or extracted.name,
                    measurement_kind=extracted.measurement_kind,
                    value=extracted.value if extracted.raw_value and extracted.raw_value in (extracted.source_text or "") else None,
                    unit=extracted.unit,
                    reference_range=extracted.reference_text,
                    reference_low=extracted.reference_low,
                    reference_high=extracted.reference_high,
                    flag=infer_status(extracted.value, extracted.reference_low, extracted.reference_high, None) if extracted.resolution_status == "verified" else None,
                    source_page=extracted.page or page.page_number,
                    source_line=extracted.line,
                    excerpt=(extracted.source_text or "")[:240],
                    confidence="low" if method in {"ocr", "vision"} or extracted.resolution_status != "verified" else extracted.confidence,
                    extraction_method=method if method in {"text", "table", "vision", "ocr"} else "text",
                    resolution_status=extracted.resolution_status,
                    resolution_reason=extracted.resolution_reason,
                    raw_value=extracted.raw_value,
                    section=extracted.section,
                    specimen=extracted.specimen,
                    method=extracted.method,
                    collection_date=extracted.date,
                    temporal_scope=extracted.temporal_scope,
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


def _unit_sig(unit: str | None) -> str:
    return re.sub(r"\s+", "", (unit or "").lower())


def observation_key(fact: DocumentHealthFact) -> tuple:
    return (
        (fact.canonical_code or fact.display_name or "").lower(),
        _sig(fact.value),
        _unit_sig(fact.unit),
        str(fact.report_date or ""),
        (fact.specimen or "").lower(),
        (fact.method or "").lower(),
        (fact.section or "").lower(),
        fact.temporal_scope or "current",
        fact.resolution_status or "verified",
    )


def dedupe_identical(facts: list[DocumentHealthFact]) -> list[DocumentHealthFact]:
    """Merge repeated summary/detail copies of the same observation."""
    grouped: dict[tuple, list[DocumentHealthFact]] = {}
    for fact in facts:
        grouped.setdefault(observation_key(fact), []).append(fact)
    out: list[DocumentHealthFact] = []
    for group in grouped.values():
        keep = min(group, key=lambda item: (item.page_number or 10**6, item.display_name or ""))
        out.append(keep)
    return out


def attach_conflicts(facts: list[DocumentHealthFact]) -> list[DocumentHealthFact]:
    by_code: dict[str, list[DocumentHealthFact]] = {}
    for fact in facts:
        key = "|".join(
            [
                fact.canonical_code or fact.display_name or "",
                fact.measurement_kind or "measured",
                str(fact.report_date or ""),
                fact.specimen or "",
                fact.method or "",
                fact.section or "",
                fact.temporal_scope or "current",
            ]
        )
        by_code.setdefault(key, []).append(fact)
    out: list[DocumentHealthFact] = []
    for key, group in by_code.items():
        values = { _sig(item.value) for item in group if item.value is not None }
        if len(values) > 1:
            for item in group:
                out.append(
                    item.model_copy(
                        update={
                            "conflict_group": key,
                            "status": item.status or "CONFLICTING_OBSERVATIONS",
                        }
                    )
                )
        else:
            out.extend(group)
    return out


def conflict_groups(facts: list[DocumentHealthFact]) -> list[list[DocumentHealthFact]]:
    grouped: dict[str, list[DocumentHealthFact]] = {}
    for fact in facts:
        if not fact.conflict_group:
            continue
        grouped.setdefault(fact.conflict_group, []).append(fact)
    return [items for items in grouped.values() if len(items) > 1]


def _close(left, right) -> bool:
    try:
        return abs(float(left) - float(right)) < 0.0001
    except (TypeError, ValueError):
        return left == right


def _sig(value) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)
