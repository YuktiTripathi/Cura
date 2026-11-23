"""Loads both reports once from the existing providers and returns the unified views."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.biomarkers.overview import build_body_system_overview
from app.biomarkers.risk_overview import build_risk_overview
from app.biomarkers.unified_overview import build_category_detail, build_unified_overview, gather, prepare
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.consent import has_current_consent
from app.core.errors import ProviderUnavailableError
from app.health_explanation.category_story import CategoryProfile, build_story, load_profile
from app.pipeline.unified_wording import model_wording
from app.providers.registry import ProviderRegistry

logger = logging.getLogger("cura.unified")


def _load(principal: AuthenticatedPrincipal, registry: ProviderRegistry):
    blood = bio = None
    try:
        reports = registry.blood.query(principal, QueryPlan(intent=IntentType.latest_result, history=True, knowledge_scope=KnowledgeScope.personal, needs_blood=True)) or []
        blood = build_body_system_overview(reports)
    except ProviderUnavailableError:
        logger.warning("unified blood_unavailable")
    try:
        reports = registry.bio_ai.query(principal, QueryPlan(intent=IntentType.bio_ai_score, needs_bio_ai=True, history=True, knowledge_scope=KnowledgeScope.personal)) or []
        bio = build_risk_overview(reports)
    except ProviderUnavailableError:
        logger.warning("unified bio_unavailable")
    return blood, bio


def _context(principal, registry, db) -> list[str]:
    """Plain lines about the member that may shape advice: diet, habits, conditions, allergies."""
    try:
        from app.pipeline.health_snapshot import build_personal_health_snapshot

        profile = build_personal_health_snapshot(principal, registry, db=db).profile
    except Exception:  # noqa: BLE001 - context is a bonus, never a reason to fail the screen
        return []
    if profile is None:
        return []
    lines: list[str] = []
    for group in (profile.dietary_preferences, profile.lifestyle, profile.relevant_conditions, profile.allergies):
        lines.extend(f.fact for f in group[:3] if f.fact)
    return lines[:10]


def _wording(principal, registry, db, blood, bio):
    if not _can_use_model(principal, db):
        return None
    cards, parts, prov = prepare(blood, bio)
    if not cards:
        return None
    return model_wording(principal.subject_id, cards, parts, prov, _context(principal, registry, db))


def _can_use_model(principal: AuthenticatedPrincipal, db: Session | None) -> bool:
    return settings.enable_llm and _has_consent(principal, db)


def _has_consent(principal: AuthenticatedPrincipal, db: Session | None) -> bool:
    return (
        not settings.consent_enforced() or (db is not None and has_current_consent(db, principal.subject_id))
    )


def unified_overview(principal: AuthenticatedPrincipal, registry: ProviderRegistry, db: Session | None = None):
    blood, bio = _load(principal, registry)
    return build_unified_overview(blood, bio, _wording(principal, registry, db, blood, bio))


def unified_category(principal: AuthenticatedPrincipal, registry: ProviderRegistry, category_id: str, db: Session | None = None):
    blood, bio = _load(principal, registry)
    detail = build_category_detail(category_id, blood, bio)
    if detail is None:
        return None
    entities = [
        row.cura_key or row.canonical_id for row in (blood.results if blood else [])
        if row.system_id == category_id and (row.cura_key or row.canonical_id)
    ]
    entities.extend(f.id.removeprefix("risk:") for f in detail.findings if f.source_type == "predicted_risk")
    consent = _has_consent(principal, db)
    profile = load_profile(principal, registry, entities) if consent else CategoryProfile(None, None, [])
    detail.story = build_story(detail, profile, principal.subject_id, allow_model=settings.enable_llm and consent)
    return detail


def unified_finding(principal: AuthenticatedPrincipal, registry: ProviderRegistry, finding_id: str):
    blood, bio = _load(principal, registry)
    for parts in gather(blood, bio).values():
        for finding in (*parts.measured, *parts.risks):
            if finding.id == finding_id:
                return finding
    return None
