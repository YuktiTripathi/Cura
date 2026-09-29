"""Python health-data retrieval router. Jev decides; this layer retrieves."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.providers.registry import ProviderRegistry
from app.retrieval.documents import retrieve_structured_documents
from app.retrieval.result import HealthRetrievalResult

logger = logging.getLogger("cura.retrieval")


class HealthRetrievalRouter:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    def retrieve(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        *,
        db: Session | None = None,
        document_ids: list[str] | None = None,
    ) -> HealthRetrievalResult:
        result = HealthRetrievalResult()
        wants_ihr = bool(plan.needs_supershyft or (plan.needs_personal_data and not plan.needs_user_uploaded))
        wants_docs = bool(plan.needs_user_uploaded)
        if plan.needs_cross_source:
            wants_ihr = True
            wants_docs = True
        if not wants_ihr and not wants_docs:
            result.skipped_reason = "general_no_personal_data"
            result.status = "not_required"
            logger.info(
                "health_retrieval skipped=true reason=general provider=none "
                "subject_present=%s topic=%s",
                bool(principal.subject_id),
                plan.topic,
            )
            return result

        if not (principal.subject_id or "").strip():
            result.invoked = True
            result.status = "unauthorized"
            result.error_reason = "missing_principal"
            return result

        result.invoked = True
        if wants_ihr:
            self._retrieve_ihr(principal, plan, result)
        if wants_docs and db is not None:
            self._retrieve_documents(principal, plan, result, db, document_ids or [])
        result.finalize_status()
        logger.info(
            "health_retrieval invoked=true status=%s ihr=%s documents=%s stored_extraction=%s "
            "blood=%s bio=%s doc_evidence=%s topic=%s history=%s",
            result.status,
            result.ihr_called,
            result.documents_called,
            result.used_stored_document_extraction,
            len(result.blood_reports),
            len(result.bio_ai_reports),
            len(result.document_evidence),
            plan.topic,
            plan.history or plan.time_scope,
        )
        return result

    def _retrieve_ihr(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        result: HealthRetrievalResult,
    ) -> None:
        result.ihr_called = True
        health = (settings.health_provider or "mock").strip().lower()
        if health in {"supershyft", "postgres", "readonly"}:
            from app.core.errors import ProviderUnavailableError
            from integrations.supershyft.ihr import IhrRepository

            try:
                bundle = IhrRepository().get_ihr_data_for_query(principal, plan)
            except ProviderUnavailableError as exc:
                result.status = "provider_unavailable"
                result.error_reason = getattr(exc, "reason", None) or "provider_unavailable"
                raise
            if plan.needs_blood:
                result.blood_reports = bundle.blood_reports
            if plan.needs_bio_ai:
                result.bio_ai_reports = bundle.bio_ai_reports
            if plan.needs_lifestyle or plan.needs_profile:
                result.lifestyle = self.registry.lifestyle.query(principal, plan)
            result.source_names.append("ihr")
            return
        if plan.needs_blood:
            result.blood_reports = self.registry.blood.query(principal, plan)
        if plan.needs_bio_ai:
            result.bio_ai_reports = self.registry.bio_ai.query(principal, plan)
        if plan.needs_lifestyle or plan.needs_profile:
            result.lifestyle = self.registry.lifestyle.query(principal, plan)
        result.source_names.append("ihr")

    def _retrieve_documents(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        result: HealthRetrievalResult,
        db: Session,
        document_ids: list[str],
    ) -> None:
        result.documents_called = True
        docs, evidence, used_stored = retrieve_structured_documents(db, principal, plan, document_ids)
        result.documents = docs
        result.document_evidence = evidence
        result.used_stored_document_extraction = used_stored
        result.reparsed_pdf = False
        if evidence:
            result.source_names.append("uploaded_document")
