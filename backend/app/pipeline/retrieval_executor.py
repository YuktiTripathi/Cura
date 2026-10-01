"""Execute a TaskPlan / QueryPlan against the authenticated user only.

Jev may name sources and entities. It must never supply the user id.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.identity import authenticated_user_id
from app.auth.models import AuthenticatedPrincipal
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.pipeline.dev_trace import trace
from app.pipeline.health_gateway import HealthDataGateway
from app.providers.registry import ProviderRegistry
from app.retrieval.result import HealthRetrievalResult
from app.retrieval.router import HealthRetrievalRouter

logger = logging.getLogger("cura.retrieval")


class RetrievalExecutor:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry
        self._router = HealthRetrievalRouter(registry)

    def execute(
        self,
        *,
        user_id: str,
        task_plan: QueryPlan,
        db: Session | None = None,
        document_ids: list[str] | None = None,
        principal: AuthenticatedPrincipal | None = None,
    ) -> HealthRetrievalResult:
        if principal is None:
            raise UnauthorizedError("Authentication required")
        authenticated = authenticated_user_id(principal)
        if str(user_id).strip() != authenticated:
            raise UnauthorizedError("Authentication required")
        plan = self._drop_unowned_report_id(authenticated, task_plan, db)
        result = self._router.retrieve(
            principal, plan, db=db, document_ids=document_ids or plan.document_ids or []
        )
        records = (
            len(result.blood_reports)
            + len(result.bio_ai_reports)
            + len(result.questionnaire_instances)
            + len(result.documents)
        )
        logger.info(
            "cura_retrieval conversation_sources=%s records=%s status=%s",
            ",".join(result.source_names or plan.data_sources or []),
            records,
            result.status,
        )
        trace(
            "RETRIEVAL",
            user_id=authenticated,
            sources=list(plan.data_sources or []),
            entities=list(plan.requested_metrics or [])[:12],
            records=records,
            ownership="validated",
            status=result.status,
        )
        return result

    def _drop_unowned_report_id(
        self, user_id: str, plan: QueryPlan, db: Session | None
    ) -> QueryPlan:
        if not plan.report_id:
            return plan
        owned = HealthDataGateway(self.registry, db).owned_report_ids(user_id)
        if plan.report_id in owned:
            return plan
        return plan.model_copy(update={"report_id": None})


def audit_request(
    *,
    principal: AuthenticatedPrincipal,
    conversation_id: str | None,
    sources: list[str],
    records: int,
    model_tier: str | None,
    success: bool,
) -> None:
    user_id = authenticated_user_id(principal)
    logged_user = user_id if settings.is_development else "hashed"
    logger.info(
        "cura_audit user=%s conversation_id=%s sources=%s records=%s model_tier=%s success=%s",
        logged_user,
        conversation_id or "",
        ",".join(sources),
        records,
        model_tier or "",
        success,
    )
    trace(
        "AUTH",
        authenticated_user_resolved=True,
        user_id=user_id if settings.is_development else None,
    )
