"""Deterministic lookups over DocumentHealthFacts. No PageIndex, no LLM math."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts.uploaded_document import DocumentHealthFact, UploadedDocumentContext
from app.pipeline.dev_trace import trace
from app.pipeline.lab_parameters import display_name_for, related_keys, resolve_biomarker


FOUND = "FOUND"
MISSING = "MISSING"
AMBIGUOUS = "AMBIGUOUS"


@dataclass
class EntityCoverage:
    code: str
    display_name: str
    status: str
    facts: list[DocumentHealthFact] = field(default_factory=list)


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


def cover_requested_entities(
    contexts: list[UploadedDocumentContext],
    keys: list[str],
) -> list[EntityCoverage]:
    rows: list[EntityCoverage] = []
    for raw in keys:
        matched = resolve_biomarker(raw)
        code = (matched.canonical_code if matched else raw).lower()
        name = display_name_for(code) or raw
        hits = lookup_facts(contexts, keys=[code])
        if not hits:
            rows.append(EntityCoverage(code=code, display_name=name, status=MISSING))
            continue
        conflicting = [item for item in hits if item.conflict_group]
        if conflicting and len({_value_sig(item) for item in hits}) > 1:
            rows.append(EntityCoverage(code=code, display_name=name, status=AMBIGUOUS, facts=hits))
        else:
            rows.append(EntityCoverage(code=code, display_name=name, status=FOUND, facts=hits[:1]))
    candidates = [
        f"{item.raw_name or item.display_name}→{item.canonical_code}={item.value}{(' ' + item.unit) if item.unit else ''}"
        for ctx in contexts
        for item in ctx.structured_facts[:20]
    ]
    trace("DOCUMENT CANDIDATES", rows=candidates)
    trace(
        "RESOLUTION",
        rows=[f"{row.code}→{row.status}" for row in rows],
    )
    trace(
        "COVERAGE",
        requested=len(keys),
        resolved=sum(1 for row in rows if row.status == FOUND),
        missing=sum(1 for row in rows if row.status == MISSING),
        ambiguous=sum(1 for row in rows if row.status == AMBIGUOUS),
    )
    return rows


def format_coverage(rows: list[EntityCoverage]) -> str:
    found = [row for row in rows if row.status in {FOUND, AMBIGUOUS} and row.facts]
    missing = [row for row in rows if row.status == MISSING]
    if not found and not missing:
        return ""
    lines: list[str] = []
    if found:
        lines.append("Your results")
        lines.append("")
        width = max(len(row.display_name) for row in found)
        for row in found:
            fact = row.facts[0]
            unit = f" {fact.unit}" if fact.unit else ""
            value = f"{fact.value:g}" if isinstance(fact.value, float) else fact.value
            status = _status_label(fact, row)
            ref = _reference_span(fact)
            extra = f"   {status}" if status else ""
            extra = f"{extra}   {ref}" if ref else extra
            lines.append(f"{row.display_name.ljust(width)}   {value}{unit}{extra}".rstrip())
            if row.status == AMBIGUOUS and len(row.facts) > 1:
                extras = "; ".join(
                    f"{item.value}{(' ' + item.unit) if item.unit else ''}"
                    for item in row.facts[1:3]
                    if item.value is not None
                )
                if extras:
                    lines.append(f"Conflicting values also present: {extras}. They were not merged.")
    if missing:
        names = [row.display_name for row in missing]
        found_names = [row.display_name.lower() for row in found]
        if found and len(missing) == 1:
            lines.append("")
            lines.append(
                f"I found your {found_names[0]} result, but I couldn't find "
                f"{'an' if names[0][:1].lower() in 'aeiou' else 'a'} {names[0]} result in this uploaded report."
            )
        elif found:
            lines.append("")
            lines.append(
                "I couldn't find "
                + ", ".join(names)
                + " in this uploaded report."
            )
        else:
            lines.append(
                "I couldn't find "
                + ", ".join(names)
                + " in this uploaded report."
            )
    lines.append("")
    lines.append("Source: Uploaded blood report")
    answer = "\n".join(lines).strip()
    trace("RESPONSE", answer=answer)
    return answer


def format_fact(fact: DocumentHealthFact) -> str:
    coverage = EntityCoverage(
        code=fact.canonical_code or "",
        display_name=fact.display_name or display_name_for(fact.canonical_code or ""),
        status=FOUND,
        facts=[fact],
    )
    return format_coverage([coverage])


def format_fact_list(facts: list[DocumentHealthFact], *, headline: str) -> str:
    if not facts:
        return ""
    rows = [
        EntityCoverage(
            code=item.canonical_code or item.display_name,
            display_name=item.display_name or display_name_for(item.canonical_code or ""),
            status=FOUND,
            facts=[item],
        )
        for item in facts[:20]
    ]
    body = format_coverage(rows)
    if headline and not headline.startswith("Your results"):
        return f"{headline}\n\n{body}"
    return body


def uploaded_caption(fact: DocumentHealthFact) -> str:
    parts = ["Uploaded report"]
    if fact.section:
        parts.append(fact.section)
    if fact.page_number:
        parts.append(f"page {fact.page_number}")
    return " · ".join(parts)


def _reference_span(fact: DocumentHealthFact) -> str:
    if fact.reference_low is not None and fact.reference_high is not None:
        return f"{fact.reference_low:g}-{fact.reference_high:g}"
    if fact.reference_text:
        return fact.reference_text
    return ""


def _status_label(fact: DocumentHealthFact, row: EntityCoverage) -> str:
    if row.status == AMBIGUOUS:
        return "Conflicting"
    status = (fact.status or "").lower()
    if status == "normal":
        return "In range"
    if status in {"high", "low", "critical"}:
        return status.capitalize()
    return ""


def _value_sig(fact: DocumentHealthFact) -> str:
    try:
        return f"{float(fact.value):.4f}|{(fact.unit or '').lower()}"
    except (TypeError, ValueError):
        return f"{fact.value}|{(fact.unit or '').lower()}"
