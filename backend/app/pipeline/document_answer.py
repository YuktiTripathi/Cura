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
from app.pipeline.lab_parameters import display_name_for, fuzzy_lab_keys, primary_lab_key, question_clarification

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
    llm_called: bool = False
    llm_mode: str = "deterministic"
    model: str | None = None
    provider: str | None = None
    fallback_reason: str | None = None


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
        return _maybe_explain(_summary_answer(rows, contexts, message), message, plan)
    structured = wants_document_structured(message, plan)
    narrative = wants_document_narrative(message, plan)
    mixed = mixed_document_query(message, plan)
    selectors = {str(item).upper() for item in (plan.selectors or [])}
    named = [key for key in fuzzy_lab_keys(message) if key]
    if not named:
        primary = primary_lab_key(message)
        if primary:
            named = [primary]
    # Named analytes in the current question win over a previous conversation topic
    # (e.g. Vitamin D) so an attached-report lookup cannot return the wrong marker.
    if named:
        keys = list(dict.fromkeys(named))
    elif question_clarification(message):
        return DocumentAnswer(answer=question_clarification(message), status="document_clarification")
    else:
        keys = list(
            dict.fromkeys(
                [
                    *(plan.requested_metrics or []),
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

    if structured and not narrative:
        facts = _select_facts(contexts, keys, selectors)
        if keys or selectors:
            return _maybe_explain(_structured_answer(facts, keys, selectors, contexts, message), message)
        return DocumentAnswer(answer=DOCUMENT_NO_MATCH, status="document_no_match", used_structured=True)

    hits: list[PageIndexHit] = []
    pending = any(ctx.pageindex_status == PageIndexStatus.building for ctx in contexts)
    ready = [ctx for ctx in contexts if ctx.pageindex_status == PageIndexStatus.ready]
    if narrative or mixed:
        if pending and not ready:
            facts = lookup_facts(contexts, keys=keys or None) if structured or keys else []
            extra = ""
            if facts and keys:
                extra = " " + format_coverage(cover_requested_entities(contexts, keys))
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
            if keys:
                structured_bits.append(format_coverage(cover_requested_entities(contexts, keys)))
            return _maybe_explain(
                DocumentAnswer(
                    answer=_narrative_answer(hits, structured_bits),
                    evidence=[_hit_evidence(rows[0], hit) for hit in hits[:3]],
                    used_structured=bool(structured_bits),
                    used_pageindex=True,
                ),
                message,
                plan,
            )
        if structured or keys:
            facts = _select_facts(contexts, keys, selectors)
            if keys or selectors:
                return _maybe_explain(_structured_answer(facts, keys, selectors, contexts, message), message)
        return DocumentAnswer(answer=DOCUMENT_NO_MATCH, status="document_no_match")

    facts = _select_facts(contexts, keys, selectors)
    if keys or selectors:
        return _maybe_explain(_structured_answer(facts, keys, selectors, contexts, message), message)
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
    message: str = "",
) -> DocumentAnswer:
    if keys:
        coverage = cover_requested_entities(contexts or [], keys, message)
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
        excerpt = ""
        for row in rows:
            for chunk in list(getattr(row, "chunks", None) or [])[:2]:
                text = (getattr(chunk, "text", None) or "").strip()
                if text:
                    excerpt = text[:500]
                    break
            if excerpt:
                break
        if excerpt:
            lines.append("The document says:")
            lines.append(excerpt)
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
            ),
            *_grounded_document_followups(facts, _message),
        ],
        used_structured=bool(facts),
        used_pageindex=bool(hits),
        still_indexing=pending,
    )


def _grounded_document_followups(facts, message: str) -> list[FollowUpSuggestion]:
    from app.pipeline.followup_generator import document_followups

    try:
        return document_followups(facts, message=message, count=3)
    except ValueError:
        return []


def _wants_explanation(message: str, plan: QueryPlan | None = None) -> bool:
    import re

    if re.search(r"\b(explain|what does|summar\w*|how|why|mean|concerning|worry|unusual|okay)\b", message or "", re.I):
        return True
    if plan is None:
        return False
    from app.pipeline.reasoning import explanation_requested

    return explanation_requested(plan, message)


def _document_model_enabled() -> bool:
    """Document explanations do not follow the global chat switch unless that switch is already on."""
    from app.core.config import settings

    return bool(settings.document_explanation_enabled or settings.enable_llm)


def explanation_messages(message: str, evidence: str, *, document_kind: str = "general") -> list[dict[str, str]]:
    """System text is CURA policy. The PDF is only in the user evidence block."""
    from app.pipeline.prompt_modules import CORE, DOCUMENT_EXPLANATION

    kind = document_kind if document_kind in {
        "blood_report", "allergy", "prescription", "discharge", "imaging", "paper", "general"
    } else "general"
    return [
        {"role": "system", "content": f"{CORE}\n\n{DOCUMENT_EXPLANATION}\nDocument kind: {kind}."},
        {
            "role": "user",
            "content": (
                f"Question: {message}\n\n"
                "Evidence from the selected uploaded document. Unresolved rows are not confirmed results.\n"
                f"{evidence}"
            ),
        },
    ]


def _maybe_explain(answer: DocumentAnswer, message: str, plan: QueryPlan | None = None) -> DocumentAnswer:
    """Explanations use one model call when the document flag or the global LLM flag is on."""
    # When an approved model is on, it words the document answer. Lookups still pass only verified text.
    if not (_wants_explanation(message, plan) or _document_model_enabled()):
        return answer
    if not answer.answer or answer.status == "document_no_match":
        return answer
    if not _document_model_enabled():
        # A composed report summary already lists verified findings. Do not flatten it.
        if "Overall picture" not in (answer.answer or ""):
            answer.answer = _plain_explanation(answer.answer)
        answer.llm_called = False
        answer.llm_mode = "deterministic"
        return answer
    evidence = _evidence_for_model(answer.answer)
    try:
        from app.core.config import settings
        from app.core.errors import LLMUnavailableError
        from app.llm.factory import get_llm_client
        from app.llm.openrouter_policy import openrouter_policy

        policy = openrouter_policy()
        policy.assert_privacy_for_health(personal_health=True)
        client = get_llm_client(personal_health=True)
        raw = client.complete(explanation_messages(message, evidence))
    except LLMUnavailableError as exc:
        from app.pipeline.reasoning import _privacy_block

        answer.answer = _plain_explanation(evidence)
        answer.llm_called = False
        answer.llm_mode = "document_fallback"
        answer.fallback_reason = "privacy" if _privacy_block(exc) else "model_unavailable"
        return answer
    except Exception:
        answer.answer = _plain_explanation(evidence)
        answer.llm_called = False
        answer.llm_mode = "document_fallback"
        answer.fallback_reason = "model_unavailable"
        return answer
    text = _answer_text(raw)
    if not text:
        answer.answer = _plain_explanation(evidence)
        answer.llm_called = False
        answer.llm_mode = "document_fallback"
        answer.fallback_reason = "invalid_response"
        return answer
    if _number_not_in_evidence(text, evidence):
        answer.answer = _plain_explanation(evidence)
        answer.llm_called = False
        answer.llm_mode = "document_fallback"
        answer.fallback_reason = "unsupported_number"
        return answer
    answer.answer = text
    answer.llm_called = True
    answer.llm_mode = "document_explanation"
    answer.model = getattr(client, "model", None)
    answer.provider = getattr(client, "provider", None)
    answer.fallback_reason = None
    return answer


def _answer_text(raw: str) -> str:
    import json
    import re

    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{") and not text.endswith("}"):
        return ""
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return ""
        if isinstance(payload, dict):
            inner = payload.get("answer")
            if isinstance(inner, str) and inner.strip().startswith("{"):
                try:
                    nested = json.loads(inner)
                except json.JSONDecodeError:
                    return ""
                if isinstance(nested, dict):
                    return str(nested.get("answer") or "").strip()
            return str(inner or "").strip()
    return text


def _plain_explanation(evidence: str) -> str:
    rows = []
    for line in (evidence or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped in {"Your results", "Source: Uploaded blood report"}:
            continue
        if stripped.startswith("I couldn't find") or stripped.startswith("Conflicting"):
            rows.append(stripped)
            continue
        if "page" in stripped:
            rows.append(stripped.rstrip(".") + ".")
    if not rows:
        return evidence
    return (
        "The uploaded report shows "
        + " ".join(rows[:6])
        + " These figures are what the document prints. They are not a diagnosis."
    )


def _evidence_for_model(evidence: str) -> str:
    """Document text is data. Lines that try to instruct the assistant are not evidence."""
    import re

    injection = re.compile(
        r"\b(?:ignore (?:all |previous |prior )?instructions|disregard (?:the )?(?:above|rules)|you are now|system prompt)\b",
        re.I,
    )
    kept = [line for line in (evidence or "").splitlines() if not injection.search(line)]
    return "\n".join(kept)


def _number_not_in_evidence(model_text: str, evidence: str) -> bool:
    import re

    for match in re.finditer(r"\d+(?:\.\d+)?", model_text or ""):
        if match.group(0) not in (evidence or ""):
            return True
    return False


def _narrative_answer(hits: list[PageIndexHit], structured_bits: list[str]) -> str:
    import re

    parts = list(structured_bits)
    lead = hits[0]
    heading = lead.heading or "this section"
    parts.append(f"The report's {heading} says: {_public_section_text(lead.text)}")
    if re.search(r"allergy|ige", f"{heading} {lead.text}", re.I) and not re.search(
        r"\bkua/l\b", lead.text or "", re.I
    ):
        parts.append(
            "Specific allergen rows were not in the extracted text, so this is not a complete allergy summary."
        )
    parts.append("That is what the document states. It is not a diagnosis from Cura.")
    if lead.page_start:
        span = f"{lead.page_start}-{lead.page_end}" if lead.page_end and lead.page_end != lead.page_start else str(lead.page_start)
        parts.append(f"Source: Uploaded report · {heading} · page {span}")
    return " ".join(part for part in parts if part)


def _public_section_text(text: str) -> str:
    """Drop demographic lines before a section is shown. Do not log this text."""
    import re

    kept = []
    for line in (text or "").splitlines():
        if re.search(
            r"patient name|age/gender|order id|barcode|partner name|referred by|customer since|sin no",
            line,
            re.I,
        ):
            redacted = re.sub(
                r"\b(?:SIN\s*No|Order\s*Id|Barcode|Patient\s*Name|Partner\s*Name|Age/Gender|"
                r"Referred\s*By|Customer\s*Since)\s*:?\s*[A-Za-z0-9][A-Za-z0-9 ./:-]{0,40}",
                " ",
                line,
                flags=re.I,
            )
            measured = re.search(
                r"immunoglobulin e \(ige\) total.{0,80}\d+(?:\.\d+)?\s*iu/ml(?:\s*<\s*\d+(?:\.\d+)?)?",
                redacted,
                re.I,
            ) or re.search(
                r"[A-Z]{4,}(?:\s+[A-Za-z()]{2,20}){0,8}.{0,60}\d+(?:\.\d+)?\s*(?:mg/dl|iu/ml|kua/l|ng/ml|g/dl|%)"
                r"(?:\s*<\s*\d+(?:\.\d+)?)?",
                redacted,
                re.I,
            )
            if measured:
                kept.append(" ".join(measured.group(0).split()))
            continue
        stripped = line.strip()
        if stripped:
            kept.append(stripped)
    return " ".join(kept)[:700]


def _fact_evidence(fact: DocumentHealthFact) -> EvidenceItem:
    rng = None
    if fact.reference_low is not None and fact.reference_high is not None:
        rng = f"{fact.reference_low:g}–{fact.reference_high:g} {fact.unit or ''}".strip()
    elif fact.reference_text:
        rng = f"{fact.reference_text} {fact.unit or ''}".strip()
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
