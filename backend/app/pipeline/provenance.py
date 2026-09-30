from __future__ import annotations

from app.contracts.chat import ProvenanceSource, UserProvenance
from app.contracts.evidence import EvidenceRecord
from app.contracts.query import QueryPlan
from app.pipeline.presentation import user_source_caption
from app.retrieval.medical import MedicalEvidenceDoc

_PERSONAL_LABELS = {
    "bio_ai_report": "Bio-AI Report",
    "blood_report": "Blood Report",
    "questionnaire": "Health Questionnaire",
    "user_uploaded": "Uploaded Document",
    "uploaded_document": "Uploaded Document",
}


def personal_label(report_type: str | None = None, source: str | None = None, plan: QueryPlan | None = None) -> str | None:
    if report_type in _PERSONAL_LABELS:
        return _PERSONAL_LABELS[report_type]
    if source == "user_uploaded":
        return "Uploaded Document"
    if plan:
        if plan.needs_bio_ai and not plan.needs_blood:
            return "Bio-AI Report"
        if plan.needs_blood and not plan.needs_bio_ai:
            return "Blood Report"
        if plan.needs_lifestyle and not plan.needs_blood and not plan.needs_bio_ai and not plan.needs_questionnaire:
            return "Health Questionnaire"
        if plan.needs_questionnaire:
            return "Health Questionnaire"
        if plan.needs_user_uploaded and not plan.needs_supershyft:
            return "Uploaded Document"
        if plan.needs_bio_ai:
            return "Bio-AI Report"
        if plan.needs_blood:
            return "Blood Report"
    return None


def _is_blood_report_fact(item: EvidenceRecord) -> bool:
    return item.report_type == "blood_report" and bool(item.marker or item.value is not None)


def build_user_provenance(
    plan: QueryPlan,
    evidence: list[EvidenceRecord],
    medical: list[MedicalEvidenceDoc],
) -> UserProvenance:
    sources: list[ProvenanceSource] = []
    seen: set[str] = set()

    def add(
        name: str,
        url: str | None,
        source_type: str,
        *,
        source_id: str | None = None,
        occurred_at: str | None = None,
    ) -> None:
        key = f"{name}|{source_id or ''}"
        if not name or key in seen:
            return
        seen.add(key)
        sources.append(
            ProvenanceSource(
                name=name,
                url=url,
                source_type=source_type,
                source_id=source_id,
                occurred_at=occurred_at,
            )
        )

    blood_items = [item for item in evidence if _is_blood_report_fact(item)]
    if blood_items:
        ordered = sorted(blood_items, key=lambda item: (item.report_date, item.report_id))
        latest = ordered[-1]
        add(
            user_source_caption("blood_report", latest.report_date, latest=True),
            None,
            "personal_record",
            source_id=latest.report_id,
            occurred_at=str(latest.report_date),
        )
        oldest = ordered[0]
        if oldest.report_id != latest.report_id:
            add(
                user_source_caption("blood_report", oldest.report_date, latest=False),
                None,
                "personal_record",
                source_id=oldest.report_id,
                occurred_at=str(oldest.report_date),
            )
    bio_items = [item for item in evidence if item.report_type == "bio_ai_report"]
    if bio_items:
        ordered = sorted(bio_items, key=lambda item: (item.report_date, item.report_id))
        seen_ids: set[str] = set()
        for index, item in enumerate(ordered):
            if item.report_id in seen_ids:
                continue
            seen_ids.add(item.report_id)
            latest = index == len(ordered) - 1 or item.report_date == ordered[-1].report_date
            add(
                user_source_caption("bio_ai_report", item.report_date, latest=latest),
                None,
                "personal_record",
                source_id=item.report_id,
                occurred_at=str(item.report_date),
            )
    other = [item for item in evidence if item.report_type not in {"blood_report", "bio_ai_report"}]
    for item in other:
        if item.report_type in {"user_uploaded", "uploaded_document"}:
            page = f" · page {item.page_start}" if item.page_start else ""
            add(f"Uploaded report{page}", None, "personal_record", source_id=item.document_id or item.report_id)
            continue
        label = personal_label(item.report_type, item.source, plan)
        if label:
            add(label, None, "personal_record", source_id=item.report_id or item.document_id)
    if plan.needs_personal_data and not any(s.source_type == "personal_record" for s in sources):
        label = personal_label(None, None, plan)
        if label and label != "Blood Report":
            add(label, None, "personal_record")
    for doc in medical:
        add(doc.name, doc.url, doc.source_type)

    if any(s.source_type == "personal_record" for s in sources) and any(
        s.source_type != "personal_record" for s in sources
    ):
        kind = "mixed"
    elif any(s.source_type == "personal_record" for s in sources):
        kind = "personal_health"
    elif sources:
        kind = "medical_reference"
    else:
        kind = "none"
    return UserProvenance(type=kind, sources=sources)


def internal_provenance(
    plan: QueryPlan,
    evidence: list[EvidenceRecord],
    medical: list[MedicalEvidenceDoc],
) -> list[dict]:
    rows = []
    for item in evidence:
        rows.append(
            {
                "source_type": item.report_type,
                "internal_provider": item.source,
                "report_id": item.report_id,
                "document_id": item.document_id,
                "user_visible_label": personal_label(item.report_type, item.source, plan),
            }
        )
    for doc in medical:
        rows.append(
            {
                "source_type": doc.source_type,
                "internal_provider": "medical_corpus",
                "name": doc.name,
                "url": doc.url,
                "tier": doc.tier,
                "user_visible_label": doc.name,
            }
        )
    return rows
