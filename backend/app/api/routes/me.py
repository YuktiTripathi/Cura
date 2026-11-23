from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.biomarkers.overview import ReportNotFound, build_body_system_overview
from app.biomarkers.risk_overview import build_risk_overview
from app.contracts.body_systems import BodySystemOverview, RiskOverview
from app.contracts.goals import GoalListRequest, GoalListResponse
from app.core.errors import ProviderUnavailableError
from app.pipeline.unified_service import unified_category, unified_overview
from app.contracts.unified_health import CategoryDetail, UnifiedOverview
from app.contracts.me import MeResponse
from app.contracts.capabilities import CapabilitiesResponse
from app.contracts.overview import HealthOverview
from app.contracts.snapshot import PersonalHealthSnapshot
from app.db.goal_store import GoalStore
from app.db.session import get_db
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.health_overview import build_health_overview
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


@router.get("/me/overview", response_model=HealthOverview)
def health_overview(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> HealthOverview:
    """Latest values with history, active insights, scores and reports for the home dashboard."""
    return build_health_overview(build_personal_health_snapshot(principal, registry, db=db))


def _history_plan(**needs) -> QueryPlan:
    return QueryPlan(intent=IntentType.latest_result, history=True, knowledge_scope=KnowledgeScope.personal, **needs)


@router.get("/me/body-systems", response_model=BodySystemOverview)
def body_systems(
    report_id: str | None = Query(default=None, max_length=128),
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
) -> BodySystemOverview:
    """Blood report grouped by body system, from the member's structured results. No model call."""
    try:
        reports = registry.blood.query(principal, _history_plan(needs_blood=True)) or []
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Your blood report isn't available right now.") from exc
    try:
        return build_body_system_overview(reports, report_id)
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail="That report was not found.") from exc


@router.get("/me/bio-ai-risks", response_model=RiskOverview)
def bio_ai_risks(
    report_id: str | None = Query(default=None, max_length=128),
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
) -> RiskOverview:
    """Predicted risks the member's Bio-AI report returned, grouped for display. No model call."""
    plan = QueryPlan(
        intent=IntentType.bio_ai_score, needs_bio_ai=True, history=True, knowledge_scope=KnowledgeScope.personal
    )
    try:
        reports = registry.bio_ai.query(principal, plan) or []
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Your Bio-AI report isn't available right now.") from exc
    try:
        return build_risk_overview(reports, report_id)
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail="That report was not found.") from exc


@router.get("/me/health-overview", response_model=UnifiedOverview)
def unified_health_overview(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> UnifiedOverview:
    """Blood results and Bio-AI risks in one set of health categories. Values are the reports' own."""
    return unified_overview(principal, registry, db)


@router.get("/me/health-overview/{category_id}", response_model=CategoryDetail)
def unified_health_category(
    category_id: str,
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> CategoryDetail:
    detail = unified_category(principal, registry, category_id, db)
    if detail is None:
        raise HTTPException(status_code=404, detail="That health category has no results.")
    return detail


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
