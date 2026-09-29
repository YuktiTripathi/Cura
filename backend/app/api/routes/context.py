from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.context_ref import ContextRef
from app.contracts.query import QueryPlan
from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import get_db
from app.documents.service import DocumentService
from app.pipeline.lab_parameters import primary_lab_key
from app.providers.registry import ProviderRegistry, get_registry

router = APIRouter()


@router.get("/context/{context_type}/{object_id}", response_model=ContextRef)
def context_reference(
    context_type: str,
    object_id: str,
    source: str = Query(default="supershyft"),
    report_id: str | None = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> ContextRef:
    """Returns an owned, validated reference—never client-provided medical values."""
    if source not in {"supershyft", "user_uploaded"}:
        raise ValidationAppError("Unsupported context source")
    if context_type == "uploaded_document":
        DocumentService(db).get_owned(principal.subject_id, object_id)
        return ContextRef(type="uploaded_document", source="user_uploaded", document_id=object_id)
    if source != "supershyft":
        raise ValidationAppError("This context type requires SuperShyft")

    if context_type == "blood_marker":
        key = primary_lab_key(object_id) or object_id.lower().replace(" ", "_")
        rows = registry.blood.query(
            principal,
            QueryPlan(
                intent=IntentType.latest_result,
                knowledge_scope=KnowledgeScope.personal,
                topic=key,
                report_id=report_id,
                needs_blood=True,
            ),
        )
        if not rows:
            raise NotFoundError("Blood marker context not found")
        return ContextRef(
            type="blood_marker",
            source="supershyft",
            marker_code=key,
            report_id=rows[-1].report_id,
        )
    if context_type == "blood_report":
        rows = registry.blood.query(
            principal,
            QueryPlan(
                intent=IntentType.broad_health_summary,
                knowledge_scope=KnowledgeScope.personal,
                report_id=object_id,
                needs_blood=True,
                history=True,
            ),
        )
        if not rows:
            raise NotFoundError("Blood report context not found")
        return ContextRef(type="blood_report", source="supershyft", report_id=object_id)
    if context_type == "bio_ai_report":
        rows = registry.bio_ai.query(
            principal,
            QueryPlan(
                intent=IntentType.bio_ai_score,
                knowledge_scope=KnowledgeScope.personal,
                report_id=object_id,
                needs_bio_ai=True,
            ),
        )
        if not rows:
            raise NotFoundError("Bio-AI report context not found")
        return ContextRef(type="bio_ai_report", source="supershyft", report_id=object_id)
    if context_type == "bio_ai_risk":
        rows = registry.bio_ai.query(
            principal,
            QueryPlan(
                intent=IntentType.bio_ai_explanation,
                knowledge_scope=KnowledgeScope.personal,
                topic=object_id.lower().replace(" ", "_"),
                report_id=report_id,
                needs_bio_ai=True,
            ),
        )
        if not rows:
            raise NotFoundError("Bio-AI risk context not found")
        return ContextRef(
            type="bio_ai_risk",
            source="supershyft",
            risk_code=object_id,
            report_id=rows[-1].report_id,
        )
    if context_type == "health_scenario":
        if not registry.scenarios.available_topics(principal):
            raise NotFoundError("Health scenario context not found")
        return ContextRef(type="health_scenario", source="supershyft")
    if context_type == "nutrition_item":
        return ContextRef(type="nutrition_item", source="supershyft")
    raise ValidationAppError("Unsupported context type")
