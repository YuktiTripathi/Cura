from __future__ import annotations

from app.contracts.chat import ProvenanceSource, UserProvenance
from app.contracts.evidence import EvidenceRecord
from app.contracts.query import QueryPlan
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
        if plan.needs_lifestyle and not plan.needs_blood and not plan.needs_bio_ai:
            return "Health Questionnaire"
        if plan.needs_user_uploaded and not plan.needs_supershyft:
            return "Uploaded Document"
        if plan.needs_bio_ai:
            return "Bio-AI Report"
        if plan.needs_blood:
            return "Blood Report"
    return None


def build_user_provenance(
    plan: QueryPlan,
    evidence: list[EvidenceRecord],
    medical: list[MedicalEvidenceDoc],
) -> UserProvenance:
    sources: list[ProvenanceSource] = []
    seen: set[str] = set()

    def add(name: str, url: str | None, source_type: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        sources.append(ProvenanceSource(name=name, url=url, source_type=source_type))

    for item in evidence:
        label = personal_label(item.report_type, item.source, plan)
        if label:
            add(label, None, "personal_record")
    if plan.needs_personal_data and not any(s.source_type == "personal_record" for s in sources):
        label = personal_label(None, None, plan)
        if label:
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
