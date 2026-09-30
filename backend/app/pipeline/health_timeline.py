from __future__ import annotations

from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.questionnaire import QuestionnaireInstance
from app.documents.contracts import DocumentOut
from app.contracts.timeline import PersonalHealthTimeline, TimelineEvent
from app.pipeline.fact_envelope import bio_risk_fact, marker_fact


def build_health_timeline(
    *,
    subject_id: str,
    blood_reports: list[BloodReport] | None = None,
    bio_reports: list[BioAIReport] | None = None,
    documents: list[DocumentOut] | None = None,
    questionnaire_instances: list[QuestionnaireInstance] | None = None,
) -> PersonalHealthTimeline:
    events: list[TimelineEvent] = []
    for report in sorted(blood_reports or [], key=lambda r: (r.report_date, r.report_id)):
        events.append(
            TimelineEvent(
                event_type="blood_report",
                occurred_at=report.report_date,
                source=report.source or "SuperShyft",
                report_id=report.report_id,
                title="Blood report",
                facts=[marker_fact(marker, subject_id) for marker in report.markers if marker.value is not None],
            )
        )
    for report in sorted(bio_reports or [], key=lambda r: (r.report_date, r.report_id)):
        events.append(
            TimelineEvent(
                event_type="bio_ai_report",
                occurred_at=report.report_date,
                source="SuperShyft",
                report_id=report.report_id,
                title="Bio-AI report",
                facts=[bio_risk_fact(risk, subject_id) for risk in report.risks if risk.score is not None],
            )
        )
    for doc in documents or []:
        events.append(
            TimelineEvent(
                event_type="uploaded_document",
                occurred_at=getattr(doc, "created_at", None),
                source="user_uploaded",
                document_id=getattr(doc, "document_id", None) or getattr(doc, "id", None),
                title=getattr(doc, "filename", None) or "Uploaded document",
                facts=[],
            )
        )
    for instance in questionnaire_instances or []:
        events.append(
            TimelineEvent(
                event_type="questionnaire",
                occurred_at=instance.recorded_at,
                source="questionnaire",
                report_id=instance.assessment_instance_id,
                title="Questionnaire",
                facts=[answer.as_fact() for answer in instance.answers],
            )
        )
    events.sort(key=lambda item: (str(item.occurred_at or ""), item.report_id or item.document_id or ""))
    return PersonalHealthTimeline(subject_id=subject_id, events=events)
