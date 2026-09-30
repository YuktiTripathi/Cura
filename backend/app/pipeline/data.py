"""Stable facade for deterministic personal-data retrieval.

Blood, Bio-AI, questionnaire, profile, and goals stay in existing repositories.
CURA orchestration should call this rather than provider classes directly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.contracts.query import QueryPlan
from app.providers.registry import ProviderRegistry
from app.retrieval.result import HealthRetrievalResult
from app.retrieval.router import HealthRetrievalRouter


class PersonalDataService:
    """One retrieval entry point per CURA request. Reuse the result; do not re-fetch."""

    def __init__(self, registry: ProviderRegistry):
        self._router = HealthRetrievalRouter(registry)

    def retrieve(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        *,
        db: Session | None = None,
        document_ids: list[str] | None = None,
    ) -> HealthRetrievalResult:
        return self._router.retrieve(principal, plan, db=db, document_ids=document_ids)
