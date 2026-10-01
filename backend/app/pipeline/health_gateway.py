"""Adapters over existing SuperShyft providers. Jev and the LLM never call this."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.identity import authenticated_user_id
from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.common import IntentType
from app.contracts.goals import HealthGoal
from app.contracts.query import QueryPlan
from app.contracts.questionnaire import QuestionnaireInstance
from app.contracts.user import UserProfile
from app.documents.contracts import DocumentOut
from app.documents.service import DocumentService
from app.providers.registry import ProviderRegistry


def _principal_for(user_id: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(subject_id=str(user_id).strip())


class HealthDataGateway:
    """Read personal health data for one authenticated SuperShyft user_id.

    Calls existing registry providers (IHR / bookings / questionnaire / profile)
    and CURA's document/goal stores. Does not open SQL from the planner or LLM.
    """

    def __init__(self, registry: ProviderRegistry, db: Session | None = None):
        self.registry = registry
        self.db = db

    def get_profile(self, user_id: str) -> UserProfile:
        return self.registry.users.get_profile(_principal_for(user_id))

    def get_latest_blood_report(self, user_id: str) -> BloodReport | None:
        reports = self.get_blood_history(user_id)
        return reports[-1] if reports else None

    def get_blood_history(
        self,
        user_id: str,
        biomarker_codes: list[str] | None = None,
    ) -> list[BloodReport]:
        plan = QueryPlan(
            intent=IntentType.trend if biomarker_codes else IntentType.latest_result,
            needs_blood=True,
            history=True,
            requested_metrics=list(biomarker_codes or []),
            time_operation="trend" if biomarker_codes else "latest_marker",
        )
        reports = list(self.registry.blood.query(_principal_for(user_id), plan))
        return sorted(reports, key=lambda row: (row.report_date, row.report_id))

    def get_latest_bioai(self, user_id: str) -> BioAIReport | None:
        reports = self.get_bioai_history(user_id)
        return reports[-1] if reports else None

    def get_bioai_history(self, user_id: str) -> list[BioAIReport]:
        plan = QueryPlan(
            intent=IntentType.bio_ai_explanation,
            needs_bio_ai=True,
            history=True,
        )
        reports = list(self.registry.bio_ai.query(_principal_for(user_id), plan))
        return sorted(reports, key=lambda row: (row.report_date, row.report_id))

    def get_latest_questionnaire(self, user_id: str) -> QuestionnaireInstance | None:
        instances = self.get_questionnaire_history(user_id)
        return instances[-1] if instances else None

    def get_questionnaire_history(self, user_id: str) -> list[QuestionnaireInstance]:
        plan = QueryPlan(
            intent=IntentType.questionnaire_lookup,
            needs_questionnaire=True,
            history=True,
        )
        instances = list(self.registry.questionnaires.query(_principal_for(user_id), plan))
        return sorted(
            instances,
            key=lambda row: (str(row.recorded_at or ""), row.assessment_instance_id or ""),
        )

    def get_goals(self, user_id: str) -> list[HealthGoal]:
        if self.db is None:
            return []
        from app.db.goal_store import GoalStore

        return GoalStore(self.db).list_for_subject(str(user_id))

    def get_uploaded_health_documents(self, user_id: str) -> list[DocumentOut]:
        if self.db is None:
            return []
        return DocumentService(self.db).list_for_user(str(user_id))

    def get_document_for_user(self, user_id: str, document_id: str):
        if self.db is None:
            from app.core.errors import NotFoundError

            raise NotFoundError("Document not found.")
        return DocumentService(self.db).get_owned(str(user_id), document_id)

    def owned_report_ids(self, user_id: str) -> set[str]:
        ids: set[str] = set()
        for report in self.get_blood_history(user_id):
            if report.report_id:
                ids.add(report.report_id)
        for report in self.get_bioai_history(user_id):
            if report.report_id:
                ids.add(report.report_id)
        return ids

    def profile_for_principal(self, principal: AuthenticatedPrincipal) -> UserProfile:
        return self.get_profile(authenticated_user_id(principal))
