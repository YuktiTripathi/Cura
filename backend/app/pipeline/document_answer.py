"""Answer uploaded-document questions: structured facts first, PageIndex for narrative."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.contracts.chat import EvidenceItem
from app.contracts.query import QueryPlan
from app.contracts.uploaded_document import (
    DocumentHealthFact,
    PageIndexHit,
    PageIndexStatus,
    UploadedDocumentContext,
)
from app.contracts.followup import FollowUpSuggestion
from app.core.copy import DOCUMENT_NO_MATCH
from app.db.models import Document
from app.documents.lookup import cover_requested_entities, format_coverage, format_fact, format_fact_list, lookup_facts
from app.documents.pageindex import PageIndexTree, retrieve_pageindex
from app.documents.query_policy import (
    mixed_document_query,
    wants_all_extracted,
    wants_document_narrative,
    wants_document_structured,
    wants_document_summary,
)
from app.documents.uploaded_context import context_from_row
from app.pipeline.dev_trace import trace
from app.pipeline.lab_parameters import display_name_for, match_lab_keys, primary_lab_key

NARRATIVE_PENDING = (
    "I've extracted the key measurements. I'm still processing the report's detailed narrative sections."
)


@dataclass
class DocumentAnswer:
    answer: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    follow_ups: list[FollowUpSuggestion] = field(default_factory=list)
    status: str = "document_retrieved"
    used_structured: bool = False
    used_pageindex: bool = False
    still_indexing: bool = False


def answer_uploaded_document(
    db: Session,
    *,
    user_id: str,
    plan: QueryPlan,
    message: str,
    document_ids: list[str],
) -> DocumentAnswer | None:
    rows = (
        db.query(Document)
        .filter(
            Document.user_id == user_id,
            Document.id.in_(document_ids),
            Document.upload_status != "deleted",
        )
        .all()
    )
    if not rows:
        return None
    contexts = [context_from_row(row) for row in rows]
    if wants_all_extracted(message):
        facts = lookup_facts(contexts)
        if facts:
            return DocumentAnswer(
                answer=format_fact_list(facts, headline="All extracted measurements from your uploaded report:"),
                evidence=[_fact_evidence(item) for item in facts[:8]],
                used_structured=True,
            )
        return DocumentAnswer(answer=DOCUMENT_NO_MATCH, status="document_no_match", used_structured=True)
    if wants_document_summary(message) or "DOCUMENT_SUMMARY" in {str(item).upper() for item in (plan.operations or [])}:
        return _summary_answer(rows, contexts, message)
    structured = wants_document_structured(message, plan)
    narrative = wants_document_narrative(message, plan)
    mixed = mixed_document_query(message, plan)
    selectors = {str(item).upper() for item in (plan.selectors or [])}
    keys = list(
        dict.fromkeys(
            [
                *(plan.requested_metrics or []),
                *match_lab_keys(message),
                *([plan.topic] if plan.topic else []),
            ]
        )
    )
    keys = [key for key in keys if key]
    trace("USER QUERY", message=message)
    trace(
        "REQUESTED ENTITIES",
        rows=[f"{display_name_for(key)} → {key}" for key in keys],
    )
    if not keys:
        primary = primary_lab_key(message)
        if primary:
            keys = [primary]

    if structured and not narrative:
        facts = _select_facts(contexts, keys, selectors)
        if keys:
            return _structured_answer(facts, keys, selectors, contexts)
        if facts:
            return _structured_answer(facts, keys, selectors, contexts)
        return DocumentAnswer(answer=DOCUMENT_NO_MATCH, status="document_no_match", used_structured=True)

    hits: list[PageIndexHit] = []
    pending = any(ctx.pageindex_status == PageIndexStatus.building for ctx in contexts)
    ready = [ctx for ctx in contexts if ctx.pageindex_status == PageIndexStatus.ready]
    if narrative or mixed:
        if pending and not ready:
            facts = lookup_facts(contexts, keys=keys or None) if structured or keys else []
            extra = ""
            if facts:
                extra = " " + format_fact(facts[0])
            return DocumentAnswer(
                answer=NARRATIVE_PENDING + extra,
                status="document_indexing",
                used_structured=bool(facts),
                still_indexing=True,
            )
        for ctx in ready:
            from app.documents.metadata import load_meta

            row = next(item for item in rows if item.id == ctx.document_id)
            raw = load_meta(row).get("pageindex")
            tree = PageIndexTree.model_validate(raw) if isinstance(raw, dict) else None
            hits.extend(retrieve_pageindex(tree, message))
        if hits:
            structured_bits = []
            if mixed or keys:
                if keys:
                    structured_bits.append(format_coverage(cover_requested_entities(contexts, keys)))
                else:
                    facts = _select_facts(contexts, keys, selectors)
                    if facts:
                        structured_bits.append(format_fact(facts[0]))
            return DocumentAnswer(
                answer=_narrative_answer(hits, structured_bits),
                evidence=[_hit_evidence(rows[0], hit) for hit in hits[:3]],
                used_structured=bool(structured_bits),
                used_pageindex=True,
            )
        if structured or keys:
            facts = _select_facts(contexts, keys, selectors)
            if keys or facts:
                return _structured_answer(facts, keys, selectors, contexts)
        return DocumentAnswer(answer=DOCUMENT_NO_MATCH, status="document_no_match")

    facts = _select_facts(contexts, keys, selectors)
    if keys or facts:
        return _structured_answer(facts, keys, selectors, contexts)
    return None


def _select_facts(
    contexts: list[UploadedDocumentContext],
    keys: list[str],
    selectors: set[str],
) -> list[DocumentHealthFact]:
    statuses = set()
    if "HIGH" in selectors:
        statuses.add("high")
    if "LOW" in selectors:
        statuses.add("low")
    if "ABNORMAL" in selectors:
        statuses.update({"high", "low", "critical"})
    if "NORMAL" in selectors:
        statuses.add("normal")
    use_keys = None if (selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and not keys) else keys
    return lookup_facts(contexts, keys=use_keys, statuses=statuses or None)


def _structured_answer(
    facts: list[DocumentHealthFact],
    keys: list[str],
    selectors: set[str],
    contexts: list[UploadedDocumentContext] | None = None,
) -> DocumentAnswer:
    if keys:
        coverage = cover_requested_entities(contexts or [], keys)
        if any(row.status != "MISSING" for row in coverage) or coverage:
            evidence_facts = [item for row in coverage for item in row.facts][:8]
            return DocumentAnswer(
                answer=format_coverage(coverage),
                evidence=[_fact_evidence(item) for item in evidence_facts],
                used_structured=True,
                status="document_retrieved" if evidence_facts else "document_no_match",
            )
    if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} or len(facts) > 1:
        headline = "These are the extracted values from your uploaded report:"
        if "HIGH" in selectors:
            headline = "High values in the uploaded report:"
        elif "LOW" in selectors:
            headline = "Low values in the uploaded report:"
        elif "ABNORMAL" in selectors:
            headline = "Values outside the report's reference range:"
        return DocumentAnswer(
            answer=format_fact_list(facts, headline=headline),
            evidence=[_fact_evidence(item) for item in facts[:8]],
            used_structured=True,
        )
    return DocumentAnswer(
        answer=format_fact(facts[0]),
        evidence=[_fact_evidence(facts[0])],
        used_structured=True,
    )


def _summary_answer(rows: list[Document], contexts: list[UploadedDocumentContext], _message: str) -> DocumentAnswer:
    facts: list[DocumentHealthFact] = []
    for ctx in contexts:
        facts.extend(ctx.structured_facts)
    attention = [item for item in facts if (item.status or "").lower() in {"high", "low", "critical"}]
    reassuring = [item for item in facts if (item.status or "").lower() == "normal"]
    pending = any(ctx.pageindex_status == PageIndexStatus.building for ctx in contexts)
    hits: list[PageIndexHit] = []
    ready = [ctx for ctx in contexts if ctx.pageindex_status == PageIndexStatus.ready]
    for ctx in ready:
        from app.documents.metadata import load_meta

        row = next(item for item in rows if item.id == ctx.document_id)
        raw = load_meta(row).get("pageindex")
        tree = PageIndexTree.model_validate(raw) if isinstance(raw, dict) else None
        hits.extend(retrieve_pageindex(tree, "impression findings conclusion recommendation diagnosis"))
    if not facts and pending and not hits:
        return DocumentAnswer(answer=NARRATIVE_PENDING, status="document_indexing", still_indexing=True)
    lines = ["I read your uploaded report. Here is the overall picture.", "", "Overall picture"]
    if attention:
        names = ", ".join((item.display_name or item.canonical_code or "a marker") for item in attention[:4])
        lines.append(f"The report flags {names} outside the printed reference range.")
    elif facts:
        lines.append("Extracted measurements are mostly within the ranges printed on the report.")
    else:
        lines.append("I could not extract a full measurement table from this document.")
    key_items = attention[:4] if attention else facts[:4]
    if key_items:
        lines.extend(["", "Key findings"])
        for item in key_items:
            unit = f" {item.unit}" if item.unit else ""
            page = f" · page {item.page_number}" if item.page_number else ""
            lines.append(f"- {item.display_name}: {item.value}{unit}{page}")
    if attention:
        lines.extend(["", "Findings worth attention"])
        for item in attention[:5]:
            unit = f" {item.unit}" if item.unit else ""
            page = f" (page {item.page_number})" if item.page_number else ""
            lines.append(f"- {item.display_name}: {item.value}{unit}, flagged {item.status}{page}")
    if reassuring:
        lines.extend(["", "Reassuring areas"])
        for item in reassuring[:4]:
            unit = f" {item.unit}" if item.unit else ""
            lines.append(f"- {item.display_name}: {item.value}{unit}, within the report range")
    unclear = [item for item in facts if item.conflict_group]
    if unclear or pending:
        lines.extend(["", "Important missing or unclear information"])
        if unclear:
            lines.append("- The same test appears more than once with different values; they were not merged.")
        if pending:
            lines.append("- Detailed narrative sections are still being processed.")
        ocr = [item for item in facts if item.extraction_method in {"ocr", "vision"} or (item.extraction_confidence or 1) < 0.6]
        if ocr:
            lines.append("- Some values were read with lower confidence and should be checked on the original page.")
    if hits:
        lead = hits[0]
        heading = lead.heading or "this section"
        lines.extend(
            [
                "",
                "What the report explicitly says",
                f"The {heading} says: {lead.text.strip()[:400]}",
            ]
        )
    lines.extend(
        [
            "",
            "That is what the document states. Cura interpretation is separate and is not a diagnosis.",
            "Source: Uploaded report",
        ]
    )
    if attention:
        lines.append("Questions worth discussing: the out-of-range values above, with a clinician who has the original report.")
    evidence = [_fact_evidence(item) for item in (attention or facts)[:6]]
    if hits:
        evidence.append(_hit_evidence(rows[0], hits[0]))
    return DocumentAnswer(
        answer="\n".join(lines),
        evidence=evidence,
        follow_ups=[
            FollowUpSuggestion(
                text="View all extracted results",
                category="document_results",
                requires_personal_context=True,
                source="user_uploaded",
                knowledge_scope="personal",
                handling_path="LOOKUP",
            )
        ],
        used_structured=bool(facts),
        used_pageindex=bool(hits),
        still_indexing=pending,
    )


def _narrative_answer(hits: list[PageIndexHit], structured_bits: list[str]) -> str:
    parts = list(structured_bits)
    lead = hits[0]
    heading = lead.heading or "this section"
    parts.append(f"The report's {heading} says: {lead.text.strip()}")
    parts.append("That is what the document states. It is not a diagnosis from Cura.")
    if lead.page_start:
        parts.append(f"Source: Uploaded report · {heading} · page {lead.page_start}")
    return " ".join(part for part in parts if part)


def _fact_evidence(fact: DocumentHealthFact) -> EvidenceItem:
    rng = None
    if fact.reference_low is not None and fact.reference_high is not None:
        rng = f"{fact.reference_low:g}–{fact.reference_high:g} {fact.unit or ''}".strip()
    return EvidenceItem(
        evidence_id=f"ev-{uuid4().hex[:8]}",
        report_id=fact.source_document_id,
        report_type="user_uploaded",
        report_date=fact.report_date or date.today(),
        source="user_uploaded",
        document_id=fact.source_document_id,
        filename=None,
        page_start=fact.page_number,
        excerpt=(fact.provenance_text or "")[:240],
        marker=fact.display_name,
        value=fact.value if isinstance(fact.value, (int, float)) else None,
        unit=fact.unit,
        reference_range=rng,
    )


def _hit_evidence(row: Document, hit: PageIndexHit) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=hit.node_id or f"ev-{uuid4().hex[:8]}",
        report_id=row.id,
        report_type="user_uploaded",
        report_date=date.today(),
        source="user_uploaded",
        document_id=row.id,
        filename=row.original_filename,
        page_start=hit.page_start,
        page_end=hit.page_end,
        excerpt=(hit.text or "")[:240],
    )
