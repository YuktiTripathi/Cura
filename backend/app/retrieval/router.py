"""Python health-data retrieval router. Jev decides; this layer retrieves."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core import perf

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
        wants_questionnaire = bool(plan.needs_questionnaire)
        wants_ihr = bool(
            plan.needs_supershyft
            or plan.needs_blood
            or plan.needs_bio_ai
            or plan.needs_lifestyle
            or plan.needs_profile
            or plan.needs_goals
        )
        wants_docs = bool(plan.needs_user_uploaded)
        if plan.needs_cross_source:
            wants_ihr = True
            wants_docs = True
        if wants_questionnaire and not (
            plan.needs_blood or plan.needs_bio_ai or plan.needs_lifestyle or plan.needs_profile or plan.needs_goals
        ):
            wants_ihr = False
        if not wants_ihr and not wants_docs and not wants_questionnaire:
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
        jobs = []
        if wants_ihr:
            jobs.append(("ihr", lambda: self._timed("ihr_fetch", self._retrieve_ihr, principal, plan, result)))
        if wants_questionnaire:
            jobs.append(("questionnaire", lambda: self._timed("questionnaire_fetch", self._retrieve_questionnaire, principal, plan, result)))
        if jobs and wants_docs and db is not None:
            with ThreadPoolExecutor(max_workers=min(2, len(jobs))) as pool:
                futures = [perf.submit_with_context(pool, fn) for _, fn in jobs]
                self._retrieve_documents(principal, plan, result, db, document_ids or [])
                for future in as_completed(futures):
                    future.result()
        elif len(jobs) > 1:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [perf.submit_with_context(pool, fn) for _, fn in jobs]
                for future in as_completed(futures):
                    future.result()
        else:
            if wants_ihr:
                self._timed("ihr_fetch", self._retrieve_ihr, principal, plan, result)
            if wants_questionnaire:
                self._timed("questionnaire_fetch", self._retrieve_questionnaire, principal, plan, result)
            if wants_docs and db is not None:
                self._retrieve_documents(principal, plan, result, db, document_ids or [])
        result.finalize_status()
        result.record_outcome(
            "blood_reports",
            requested=bool(plan.needs_blood),
            records=sum(len(r.markers) for r in result.blood_reports),
            unavailable=result.status == "provider_unavailable" and bool(plan.needs_blood),
            unauthorized=result.status == "unauthorized",
        )
        result.record_outcome(
            "bio_ai_report",
            requested=bool(plan.needs_bio_ai),
            records=sum(len(r.risks) for r in result.bio_ai_reports),
            unavailable=result.status == "provider_unavailable" and bool(plan.needs_bio_ai),
            unauthorized=result.status == "unauthorized",
        )
        result.record_outcome(
            "questionnaire",
            requested=bool(plan.needs_questionnaire),
            records=sum(len(item.answers) for item in result.questionnaire_instances),
        )
        result.record_outcome(
            "lifestyle",
            requested=bool(plan.needs_lifestyle or plan.needs_profile),
            records=1 if result.lifestyle else 0,
        )
        result.record_outcome(
            "health_goals",
            requested=bool(plan.needs_goals),
            records=0,
        )
        result.record_outcome(
            "uploaded_documents",
            requested=bool(plan.needs_user_uploaded),
            records=len(result.document_evidence),
        )
        logger.info(
            "health_retrieval invoked=true status=%s ihr=%s questionnaire=%s documents=%s stored_extraction=%s "
            "blood=%s bio=%s q=%s doc_evidence=%s topic=%s history=%s",
            result.status,
            result.ihr_called,
            result.questionnaire_called,
            result.documents_called,
            result.used_stored_document_extraction,
            len(result.blood_reports),
            len(result.bio_ai_reports),
            sum(len(item.answers) for item in result.questionnaire_instances),
            len(result.document_evidence),
            plan.topic,
            plan.history or plan.time_scope,
        )
        return result

    @staticmethod
    def _timed(stage_name, fn, *args, **kwargs):
        with perf.stage(stage_name):
            return fn(*args, **kwargs)

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

            lifestyle_future = None
            if plan.needs_lifestyle or plan.needs_profile:
                # Lifestyle/preferences do not depend on the IHR rows: read them concurrently.
                lifestyle_future = perf.submit_with_context(
                    _IO_POOL, self._timed, "lifestyle_fetch", self.registry.lifestyle.query, principal, plan
                )
            try:
                with perf.stage("blood_bioai_fetch"):
                    bundle = IhrRepository().get_ihr_data_for_query(principal, plan)
            except ProviderUnavailableError as exc:
                result.status = "provider_unavailable"
                result.error_reason = getattr(exc, "reason", None) or "provider_unavailable"
                if lifestyle_future is not None:
                    lifestyle_future.cancel()
                raise
            if plan.needs_blood:
                result.blood_reports = bundle.blood_reports
            if plan.needs_bio_ai:
                result.bio_ai_reports = bundle.bio_ai_reports
            if lifestyle_future is not None:
                result.lifestyle = lifestyle_future.result()
            result.source_names.append("ihr")
            return
        # Independent provider reads run concurrently; errors propagate as before.
        futures = {}
        if plan.needs_blood:
            futures["blood"] = perf.submit_with_context(_IO_POOL, self._timed, "blood_fetch", self.registry.blood.query, principal, plan)
        if plan.needs_bio_ai:
            futures["bio_ai"] = perf.submit_with_context(_IO_POOL, self._timed, "bioai_fetch", self.registry.bio_ai.query, principal, plan)
        if plan.needs_lifestyle or plan.needs_profile:
            futures["lifestyle"] = perf.submit_with_context(_IO_POOL, self._timed, "lifestyle_fetch", self.registry.lifestyle.query, principal, plan)
        if "blood" in futures:
            result.blood_reports = futures["blood"].result()
        if "bio_ai" in futures:
            result.bio_ai_reports = futures["bio_ai"].result()
        if "lifestyle" in futures:
            result.lifestyle = futures["lifestyle"].result()
        result.source_names.append("ihr")

    def _retrieve_questionnaire(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        result: HealthRetrievalResult,
    ) -> None:
        result.questionnaire_called = True
        provider = getattr(self.registry, "questionnaires", None)
        if provider is None:
            return
        from app.core.errors import ProviderUnavailableError

        try:
            result.questionnaire_instances = provider.query(principal, plan) or []
        except ProviderUnavailableError as exc:
            result.status = "provider_unavailable"
            result.error_reason = getattr(exc, "reason", None) or "provider_unavailable"
            raise
        if result.questionnaire_instances:
            result.source_names.append("questionnaire")

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


# Shared pool for independent provider reads (blood, Bio-AI, lifestyle) within one request.
_IO_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="cura-io")
