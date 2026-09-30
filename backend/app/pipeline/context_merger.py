"""Merge retrieved source contexts without flattening conflicting measurements."""

from __future__ import annotations

from datetime import date, datetime

from app.contracts.common import HealthSourceType
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.health_context import CrossSourceValue, HealthContext, SourceConflict
from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import canonicalize_marker_name, display_name_for


def _source_type_for_fact(fact: ProvenancedFact) -> str:
    if fact.source_type:
        return fact.source_type
    source = (fact.source or "").lower()
    if fact.fact_type == FactKind.questionnaire_response or source == "questionnaire":
        return HealthSourceType.supershyft_questionnaire.value
    if fact.fact_type == FactKind.medical_evidence or source in {"medical_corpus", "medical_knowledge"}:
        return HealthSourceType.medical_knowledge.value
    if source in {"user_uploaded", "uploaded_document"}:
        return HealthSourceType.uploaded_document.value
    if fact.notes and any("Bio-AI" in note for note in fact.notes):
        return HealthSourceType.supershyft_bio_ai.value
    if fact.fact_type in {FactKind.user_preference, FactKind.user_provided_data}:
        return HealthSourceType.supershyft_lifestyle.value
    return HealthSourceType.supershyft_blood.value


def annotate_fact(fact: ProvenancedFact) -> ProvenancedFact:
    source_type = _source_type_for_fact(fact)
    source_id = fact.source_id or fact.document_id or fact.report_id or fact.response_id
    return fact.model_copy(update={"source_type": source_type, "source_id": source_id})


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def attach_medical_evidence(ctx: HealthContext, docs: list) -> HealthContext:
    extra: list[ProvenancedFact] = []
    for doc in docs:
        extra.append(
            ProvenancedFact(
                fact=doc.title or doc.name,
                value=None,
                source=doc.name,
                fact_type=FactKind.medical_evidence,
                source_type=HealthSourceType.medical_knowledge.value,
                source_id=doc.url,
                notes=[doc.url, doc.excerpt[:240]],
                confidence="high",
            )
        )
    ctx.facts = [*(ctx.facts or []), *extra]
    return ctx


class ContextMerger:
    """Combine retrieved facts while preserving per-source provenance."""

    def merge_into(self, ctx: HealthContext, plan: QueryPlan, subject_id: str | None = None) -> HealthContext:
        del plan, subject_id
        facts = [annotate_fact(fact) for fact in (ctx.facts or [])]
        ctx.facts = facts
        ctx.source_conflicts = self._conflicts(facts)
        return ctx

    def _conflicts(self, facts: list[ProvenancedFact]) -> list[SourceConflict]:
        measured = [
            fact
            for fact in facts
            if fact.fact_type == FactKind.measured_data and fact.value is not None
        ]
        grouped: dict[str, list[ProvenancedFact]] = {}
        for fact in measured:
            key = canonicalize_marker_name(str(fact.fact or "")) or str(fact.fact or "")
            grouped.setdefault(key, []).append(fact)
        conflicts: list[SourceConflict] = []
        for key, rows in grouped.items():
            families = set()
            for row in rows:
                source_type = row.source_type or ""
                if source_type == HealthSourceType.uploaded_document.value:
                    families.add("uploaded_document")
                elif source_type.startswith("supershyft_"):
                    families.add("supershyft")
                elif source_type == HealthSourceType.medical_knowledge.value:
                    continue
                elif source_type:
                    families.add(source_type)
            values = {row.value for row in rows}
            if "uploaded_document" not in families or len(families) < 2 or len(values) < 2:
                continue
            conflicts.append(
                SourceConflict(
                    metric=key,
                    name=display_name_for(key),
                    values=[
                        CrossSourceValue(
                            source=row.source_type or row.source,
                            value=float(row.value) if isinstance(row.value, (int, float)) else None,
                            unit=row.unit,
                            measured_at=_as_date(row.measured_at),
                            report_id=row.report_id,
                            document_id=row.document_id,
                            page=row.page,
                            confidence=row.confidence or "high",
                        )
                        for row in rows
                    ],
                )
            )
        return conflicts
