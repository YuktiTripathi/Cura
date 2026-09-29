from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.goals import GoalListRequest, GoalListResponse
from app.contracts.me import MeResponse
from app.contracts.capabilities import CapabilitiesResponse
from app.contracts.snapshot import PersonalHealthSnapshot
from app.db.goal_store import GoalStore
from app.db.session import get_db
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.health_snapshot import build_personal_health_snapshot
from app.pipeline.me_service import build_me_response
from app.providers.registry import ProviderRegistry, get_registry
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.query import QueryPlan

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def me(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
    language: str | None = Query(default=None),
) -> MeResponse:
    return build_me_response(principal, registry, language=language, db=db)


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    language: str | None = Query(default=None),
) -> CapabilitiesResponse:
    response = build_me_response(principal, registry, language=language)
    return CapabilitiesResponse(
        capabilities=response.capabilities,
        starters=response.starters,
    )


@router.get("/health-snapshot", response_model=PersonalHealthSnapshot)
def health_snapshot(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> PersonalHealthSnapshot:
    return build_personal_health_snapshot(principal, registry, db=db)


@router.get("/me/goals", response_model=GoalListResponse)
def get_goals(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> GoalListResponse:
    goals = GoalStore(db).list_for_subject(principal.subject_id)
    reports = []
    try:
        reports = registry.blood.query(
            principal,
            QueryPlan(
                intent=IntentType.health_goal_progress,
                needs_blood=True,
                history=True,
                knowledge_scope=KnowledgeScope.personal,
            ),
        )
    except Exception:
        reports = []
    return GoalListResponse(
        subject_id=principal.subject_id,
        goals=goals,
        progress=compute_goal_progress(goals, reports),
    )


@router.put("/me/goals", response_model=GoalListResponse)
def put_goals(
    payload: GoalListRequest,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> GoalListResponse:
    goals = GoalStore(db).replace_for_subject(principal.subject_id, payload.goals)
    reports = []
    try:
        reports = registry.blood.query(
            principal,
            QueryPlan(
                intent=IntentType.health_goal_progress,
                needs_blood=True,
                history=True,
                knowledge_scope=KnowledgeScope.personal,
            ),
        )
    except Exception:
        reports = []
    return GoalListResponse(
        subject_id=principal.subject_id,
        goals=goals,
        progress=compute_goal_progress(goals, reports),
    )
