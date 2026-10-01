"""Canonical DocumentHealthFacts from extracted pages. Reuses lab ontology; does not merge conflicts."""

from __future__ import annotations

import re

from app.contracts.uploaded_document import DocumentHealthFact
from app.documents.extraction import ExtractedPage
from app.documents.structured import ExtractedBiomarker, ExtractedHealthDocument
from app.documents.value_extraction import extract_marker_from_text, find_report_date
from app.pipeline.health_domains import domain_for_entity
from app.pipeline.lab_parameters import PARAMETERS, canonicalize_marker_name, display_name_for, resolve_biomarker


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
        matched = resolve_biomarker(marker.normalized_name or marker.name or marker.original_field or "")
        code = (matched.canonical_code if matched else None) or canonicalize_marker_name(
            marker.normalized_name or marker.name or ""
        ) or marker.normalized_name
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
                report_date=extracted.report_date,
                page_number=marker.source_page,
                source_document_id=extracted.document_id,
                extraction_method=marker.extraction_method or "text",
                extraction_confidence=confidence_score(marker.confidence),
                mapping_confidence=matched.confidence if matched else confidence_score(marker.confidence),
                provenance_text=marker.excerpt,
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
        for param in PARAMETERS:
            extracted = extract_marker_from_text(text, param.key, page=page.page_number)
            if not extracted or extracted.value is None:
                continue
            same = [
                item
                for item in biomarkers
                if item.normalized_name == param.key and _close(item.value, extracted.value)
            ]
            if same:
                continue
            conflict = any(item.normalized_name == param.key for item in biomarkers)
            biomarkers.append(
                ExtractedBiomarker(
                    name=extracted.name or display_name_for(param.key),
                    normalized_name=param.key,
                    original_field=extracted.name,
                    value=extracted.value,
                    unit=extracted.unit,
                    reference_range=extracted.reference_text,
                    reference_low=extracted.reference_low,
                    reference_high=extracted.reference_high,
                    flag=infer_status(extracted.value, extracted.reference_low, extracted.reference_high, None),
                    source_page=extracted.page or page.page_number,
                    source_line=extracted.line,
                    excerpt=(extracted.source_text or "")[:200],
                    confidence="low" if method in {"ocr", "vision"} else extracted.confidence,
                    extraction_method=method if method in {"text", "table", "vision", "ocr"} else "text",
                )
            )
            if conflict:
                biomarkers[-1] = biomarkers[-1].model_copy(update={"confidence": "low"})
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
        key = fact.canonical_code or fact.display_name
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
