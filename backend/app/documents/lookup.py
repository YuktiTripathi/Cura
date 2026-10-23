"""Deterministic lookups over DocumentHealthFacts. No PageIndex, no LLM math."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.contracts.uploaded_document import DocumentHealthFact, UploadedDocumentContext
from app.pipeline.dev_trace import trace
from app.pipeline.lab_parameters import (
    FAMILY_QUERY_KEYS,
    aliases_for,
    display_name_for,
    related_keys_ordered,
    resolve_biomarker,
)


FOUND = "FOUND"
MISSING = "MISSING"
AMBIGUOUS = "AMBIGUOUS"


@dataclass
class EntityCoverage:
    code: str
    display_name: str
    status: str
    facts: list[DocumentHealthFact] = field(default_factory=list)


_CALCULATED_PANEL = {"egfr", "egfr_cystatin"}


def lookup_facts(
    contexts: list[UploadedDocumentContext],
    *,
    keys: list[str] | None = None,
    statuses: set[str] | None = None,
    include_calculated: bool = False,
    include_historical: bool = False,
) -> list[DocumentHealthFact]:
    wanted = {item.lower() for item in (keys or []) if item}
    if "glucose" in wanted:
        wanted |= {"fasting_blood_glucose", "postprandial_glucose"}
    out: list[DocumentHealthFact] = []
    for ctx in contexts:
        for fact in ctx.structured_facts:
            if fact.value is None:
                continue
            if (fact.resolution_status or "verified") != "verified":
                continue
            code = (fact.canonical_code or "").lower()
            kind = fact.measurement_kind or "measured"
            if kind == "calculated" and code not in _CALCULATED_PANEL and not include_calculated:
                continue
            if (fact.temporal_scope or "current") == "historical" and not include_historical:
                continue
            if wanted and code not in wanted:
                continue
            if statuses and (fact.status or "").lower() not in statuses:
                continue
            out.append(fact)
    return out


def _requested_page(message: str) -> int | None:
    import re

    match = re.search(r"\bpage\s+(\d+)\b", message or "", re.I)
    if not match:
        return None
    return int(match.group(1))


def _for_panel(hits: list[DocumentHealthFact], panel: str | None) -> list[DocumentHealthFact]:
    """Keep observations from the requested section. Do not pick one by page order."""
    if not panel:
        return hits
    # A combined cystatin-C GFR is its own panel, not the kidney function section.
    if panel == "kidney_function":
        hits = [item for item in hits if "cystatin" not in (item.section or "").lower()]
    aliases = [alias.lower() for alias in aliases_for(panel) if len(alias) > 3]
    matched = [
        item
        for item in hits
        if any(alias in (item.section or "").lower() for alias in aliases)
    ]
    return matched or hits


def cover_requested_entities(
    contexts: list[UploadedDocumentContext],
    keys: list[str],
    message: str = "",
) -> list[EntityCoverage]:
    import re

    include_calculated = bool(re.search(r"\b(calculated|estimated|average glucose|eag)\b", message or "", re.I))
    include_historical = bool(re.search(r"\b(previous|prior|histor\w*|compar\w*|versus|\bvs\b)\b", message or "", re.I))
    rows: list[EntityCoverage] = []
    codes: list[str] = []
    panel_for: dict[str, str] = {}
    for raw in keys:
        matched = resolve_biomarker(raw)
        code = (matched.canonical_code if matched else raw).lower()
        if code in FAMILY_QUERY_KEYS:
            for member in related_keys_ordered(code):
                codes.append(member)
                panel_for.setdefault(member, code)
        else:
            codes.append(code)
    for code in list(dict.fromkeys(codes)):
        name = display_name_for(code) or code
        hits = lookup_facts(
            contexts,
            keys=[code],
            include_calculated=include_calculated,
            include_historical=include_historical,
        )
        if not hits:
            rows.append(EntityCoverage(code=code, display_name=name, status=MISSING))
            continue
        page = _requested_page(message)
        if page is not None:
            on_page = [item for item in hits if item.page_number == page]
            hits = on_page
        chosen = _for_panel(hits, panel_for.get(code))
        conflicting = [item for item in chosen if item.conflict_group]
        if len(chosen) > 1 and (conflicting or len({_value_sig(item) for item in chosen}) > 1):
            rows.append(EntityCoverage(code=code, display_name=name, status=AMBIGUOUS, facts=chosen))
        else:
            rows.append(EntityCoverage(code=code, display_name=name, status=FOUND, facts=chosen))
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
            for fact in row.facts[:4]:
                unit = f" {fact.unit}" if fact.unit else ""
                value = f"{fact.value:g}" if isinstance(fact.value, float) else fact.value
                status = _status_label(fact, row)
                ref = _reference_span(fact)
                when = " previous" if (fact.temporal_scope or "") == "historical" else ""
                page = f" page {fact.page_number}" if fact.page_number else ""
                extra = f"   {status}" if status else ""
                extra = f"{extra}   {ref}" if ref else extra
                lines.append(f"{row.display_name.ljust(width)}   {value}{unit}{when}{page}{extra}".rstrip())
            if row.status == AMBIGUOUS and len(row.facts) > 1 and any(item.conflict_group for item in row.facts):
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
    if row.status == AMBIGUOUS and fact.conflict_group:
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
