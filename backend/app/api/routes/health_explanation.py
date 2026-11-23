"""Health explanation endpoints. They read the signed in member's own data only and reuse the unified overview.

There is no member id in any path. The principal decides whose data is read, so one member cannot ask for another's.
Wording is cached by a key that includes the member and a hash of their reports, so a changed report is never served
from an old cache. Refresh therefore recomputes from the live reports.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.unified_health import CategoryDetail, Finding, UnifiedOverview
from app.db.session import get_db
from app.pipeline.unified_service import unified_category, unified_finding, unified_overview
from app.providers.registry import ProviderRegistry, get_registry

router = APIRouter(prefix="/health-explanation", tags=["health-explanation"])


@router.get("/overview", response_model=UnifiedOverview)
def overview(principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    return unified_overview(principal, registry, db)


@router.post("/refresh", response_model=UnifiedOverview)
def refresh(principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    return unified_overview(principal, registry, db)


@router.get("/categories/{category_id}", response_model=CategoryDetail)
def category(category_id: str, principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    detail = unified_category(principal, registry, category_id, db)
    if detail is None:
        raise HTTPException(status_code=404, detail="That health category has no results.")
    return detail


@router.get("/findings/{finding_id}", response_model=Finding)
def finding(finding_id: str, principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry)):
    result = unified_finding(principal, registry, finding_id)
    if result is None:
        raise HTTPException(status_code=404, detail="That finding was not found.")
    return result
