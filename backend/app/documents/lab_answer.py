from __future__ import annotations

from app.documents.retrieval import DocumentEvidence
from app.documents.value_extraction import ExtractedValue, extract_marker_from_text
from app.pipeline.lab_parameters import display_name_for, primary_lab_key, related_keys_ordered


def extract_lab_hits(hits: list[DocumentEvidence], query: str) -> list[ExtractedValue]:
    key = primary_lab_key(query)
    if not key:
        return []
    keys = related_keys_ordered(key)
    found: list[ExtractedValue] = []
    for hit in hits:
        for k in keys:
            extracted = extract_marker_from_text(hit.text, k, page=hit.page_start)
            if extracted and extracted.value is not None:
                found.append(extracted)
                break
    return found


def distinct_lab_values(values: list[ExtractedValue]) -> list[ExtractedValue]:
    seen: set[tuple[str, float]] = set()
    out: list[ExtractedValue] = []
    for item in values:
        if item.value is None:
            continue
        sig = (item.parameter, round(float(item.value), 4))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def clarification_needed(values: list[ExtractedValue]) -> bool:
    unique = distinct_lab_values(values)
    params = {v.parameter for v in unique}
    if "fasting_blood_glucose" in params and any(p != "fasting_blood_glucose" for p in params) and len(unique) > 1:
        return True
    numbers = {round(float(v.value), 2) for v in unique if v.value is not None}
    return len(numbers) > 1 and len(params) > 1


def render_lab_answer(values: list[ExtractedValue], query: str) -> str | None:
    unique = distinct_lab_values(values)
    if not unique:
        return None
    if clarification_needed(unique):
        names = " and ".join(sorted({display_name_for(v.parameter) for v in unique}))
        return (
            f"Your report lists more than one glucose result ({names}). "
            "Which measurement would you like me to use?"
        )
    preferred = next((v for v in unique if v.parameter == "fasting_blood_glucose"), unique[0])
    unit = preferred.unit or "mg/dL"
    name = preferred.name or display_name_for(preferred.parameter)
    if preferred.parameter == "fasting_blood_glucose":
        label = "fasting blood sugar"
    elif name.upper() == name or name in {"LDL", "HDL", "HbA1c", "TSH", "CRP", "ESR", "ALT", "AST"}:
        label = name
    else:
        label = name
    value = f"{preferred.value:g}"
    parts = [f"Your {label} is {value} {unit}."]
    if preferred.reference_low is not None and preferred.reference_high is not None:
        parts.append(
            f"The reference range shown on your report is {preferred.reference_low:g}–{preferred.reference_high:g} {unit}."
        )
    elif preferred.reference_text:
        parts.append(f"The reference range shown on your report is {preferred.reference_text} {unit}.")
    return " ".join(parts)


def evidence_from_value(hit: DocumentEvidence, value: ExtractedValue):
    from datetime import date

    from app.contracts.chat import EvidenceItem

    rng = None
    if value.reference_low is not None and value.reference_high is not None:
        rng = f"{value.reference_low:g}–{value.reference_high:g} {value.unit or 'mg/dL'}"
    elif value.reference_text:
        rng = f"{value.reference_text} {value.unit or ''}".strip()
    return EvidenceItem(
        evidence_id=hit.chunk_id,
        report_id=hit.document_id,
        report_type="user_uploaded",
        report_date=date.today(),
        source="user_uploaded",
        document_id=hit.document_id,
        chunk_id=hit.chunk_id,
        filename=hit.filename,
        page_start=value.page or hit.page_start,
        page_end=hit.page_end,
        excerpt=(value.source_text or hit.text)[:240],
        marker=value.name,
        value=value.value,
        unit=value.unit,
        reference_range=rng,
    )
