"""Health explanation endpoints. They read the signed in member's own data only and reuse the unified overview.

There is no member id in any path. The principal decides whose data is read, so one member cannot ask for another's.
Wording is cached by a key that includes the member and a hash of their reports, so a changed report is never served
from an old cache. Refresh therefore recomputes from the live reports.
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.contracts.member_snapshot import HealthView
from app.contracts.unified_health import CategoryDetail, Finding, UnifiedOverview
from app.db.session import get_db
from app.core.config import settings
from app.core.metrics import SNAPSHOT_BUILD, SNAPSHOT_NAVIGATION
from app.pipeline.unified_service import unified_category, unified_finding, unified_overview
from app.snapshot.assemble import to_health_view
from app.snapshot.cache import load_snapshot
from app.providers.registry import ProviderRegistry, get_registry

router = APIRouter(prefix="/health-explanation", tags=["health-explanation"])


def _timed_snapshot(principal, registry):
    started = time.perf_counter()
    try:
        snapshot = load_snapshot(principal, registry)
    except Exception:
        SNAPSHOT_BUILD.labels(outcome="error").observe(time.perf_counter() - started)
        raise
    SNAPSHOT_BUILD.labels(outcome=snapshot.state).observe(time.perf_counter() - started)
    return snapshot


@router.get("/view", response_model=HealthView)
def health_view(principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry)):
    if not settings.member_snapshot_enabled:
        raise HTTPException(status_code=404, detail="Member snapshot is disabled.")
    return to_health_view(_timed_snapshot(principal, registry))


@router.get("/overview", response_model=UnifiedOverview)
def overview(principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    if settings.member_snapshot_enabled:
        return _timed_snapshot(principal, registry).overview
    return unified_overview(principal, registry, db)


@router.post("/refresh", response_model=UnifiedOverview)
def refresh(principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    if settings.member_snapshot_enabled:
        started = time.perf_counter()
        snapshot = load_snapshot(principal, registry, refresh=True)
        SNAPSHOT_BUILD.labels(outcome="refresh").observe(time.perf_counter() - started)
        return snapshot.overview
    return unified_overview(principal, registry, db)


@router.get("/categories/{category_id}", response_model=CategoryDetail)
def category(category_id: str, principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry), db: Session = Depends(get_db)):
    if settings.member_snapshot_enabled:
        started = time.perf_counter()
        detail = _timed_snapshot(principal, registry).categories.get(category_id)
        SNAPSHOT_NAVIGATION.labels(screen="category").observe(time.perf_counter() - started)
    else:
        detail = unified_category(principal, registry, category_id, db)
    if detail is None:
        raise HTTPException(status_code=404, detail="That health category has no results.")
    return detail


@router.get("/findings/{finding_id}", response_model=Finding)
def finding(finding_id: str, principal: AuthenticatedPrincipal = Depends(get_principal), registry: ProviderRegistry = Depends(get_registry)):
    if settings.member_snapshot_enabled:
        started = time.perf_counter()
        result = _timed_snapshot(principal, registry).findings.get(finding_id)
        SNAPSHOT_NAVIGATION.labels(screen="finding").observe(time.perf_counter() - started)
    else:
        result = unified_finding(principal, registry, finding_id)
    if result is None:
        raise HTTPException(status_code=404, detail="That finding was not found.")
    return result
