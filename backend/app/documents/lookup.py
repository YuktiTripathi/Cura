"""Deterministic lookups over DocumentHealthFacts. No PageIndex, no LLM math."""

from __future__ import annotations

from app.contracts.uploaded_document import DocumentHealthFact, UploadedDocumentContext
from app.pipeline.lab_parameters import display_name_for, related_keys


def lookup_facts(
    contexts: list[UploadedDocumentContext],
    *,
    keys: list[str] | None = None,
    statuses: set[str] | None = None,
) -> list[DocumentHealthFact]:
    wanted = {item.lower() for item in (keys or []) if item}
    expanded: set[str] = set()
    for key in wanted:
        expanded.add(key)
        if key in {"glucose", "fasting_blood_glucose", "postprandial_glucose"}:
            expanded.update(related_keys(key) or {key})
    out: list[DocumentHealthFact] = []
    for ctx in contexts:
        for fact in ctx.structured_facts:
            if fact.value is None:
                continue
            code = (fact.canonical_code or "").lower()
            if expanded and code not in expanded:
                continue
            if statuses and (fact.status or "").lower() not in statuses:
                continue
            out.append(fact)
    return out


def format_fact(fact: DocumentHealthFact) -> str:
    name = fact.display_name or display_name_for(fact.canonical_code or "")
    unit = f" {fact.unit}" if fact.unit else ""
    value = fact.value
    if isinstance(value, float):
        value = f"{value:g}"
    parts = [f"Your {name} is {value}{unit}."]
    if fact.status and fact.status not in {"normal", "unknown"}:
        parts.append(f"The report flags it {fact.status}.")
    elif fact.reference_low is not None and fact.reference_high is not None:
        unit_txt = fact.unit or ""
        parts.append(
            f"The reference range shown on your report is {fact.reference_low:g}–{fact.reference_high:g} {unit_txt}".strip()
            + "."
        )
    source = uploaded_caption(fact)
    if source:
        parts.append(f"Source: {source}")
    if fact.conflict_group:
        parts.append("Another value for the same test is also present in this report; they were not merged.")
    return " ".join(parts)


def format_fact_list(facts: list[DocumentHealthFact], *, headline: str) -> str:
    if not facts:
        return ""
    lines = [headline]
    for fact in facts[:20]:
        name = fact.display_name or display_name_for(fact.canonical_code or "")
        unit = f" {fact.unit}" if fact.unit else ""
        value = f"{fact.value:g}" if isinstance(fact.value, float) else fact.value
        status = f" ({fact.status})" if fact.status else ""
        page = f" · page {fact.page_number}" if fact.page_number else ""
        lines.append(f"{name}: {value}{unit}{status}{page}")
    lines.append("Source: Uploaded report")
    return "\n".join(lines)


def uploaded_caption(fact: DocumentHealthFact) -> str:
    parts = ["Uploaded report"]
    if fact.section:
        parts.append(fact.section)
    if fact.page_number:
        parts.append(f"page {fact.page_number}")
    return " · ".join(parts)
