"""Lightweight CURA landing readiness endpoint.

This endpoint never returns raw medical data. It checks the existing provider cache
and triggers the existing asynchronous preload through the /me service.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.deps import get_principal
from app.auth.models import AuthenticatedPrincipal
from app.pipeline.me_service import schedule_latest_preload
from app.providers.cache import storage_key
from app.core.request_controls import request_controls
from app.providers.registry import ProviderRegistry, get_registry

router = APIRouter()


class HomeReadiness(BaseModel):
    status: Literal["loading", "ready", "partial", "unavailable"]
    blood_cached: bool
    bio_ai_cached: bool
    lifestyle_cached: bool
    questionnaire_cached: bool
    # This endpoint does not infer report availability from cache misses.
    # Clients should refresh /me once ready for personalized starter questions.
    refresh_me_when_ready: bool = True


@router.get("/cura/home/readiness", response_model=HomeReadiness)
def home_readiness(
    principal: AuthenticatedPrincipal = Depends(get_principal),
    registry: ProviderRegistry = Depends(get_registry),
) -> HomeReadiness:
    from app.core.config import settings

    # With caching disabled, no readiness state can be inferred.
    if settings.health_data_cache_seconds <= 0:
        return HomeReadiness(status="unavailable", blood_cached=False, bio_ai_cached=False,
                             lifestyle_cached=False, questionnaire_cached=False, refresh_me_when_ready=False)

    # Check cache-entry presence rather than payload truthiness: a completed
    # provider read can legitimately contain [] or null.
    def present(kind: str) -> bool:
        try:
            return request_controls._get(storage_key(kind, principal.subject_id, "latest")) is not None
        except Exception:  # noqa: BLE001
            return False

    blood_cached = present("blood")
    bio_cached = present("bio_ai")
    lifestyle_cached = present("lifestyle")
    questionnaire_cached = present("questionnaire")
    cached_count = sum((blood_cached, bio_cached, lifestyle_cached, questionnaire_cached))
    if cached_count == 4:
        status = "ready"
    elif cached_count:
        status = "partial"
    else:
        status = "loading"

    if status != "ready":
        schedule_latest_preload(principal, registry)

    return HomeReadiness(status=status, blood_cached=blood_cached, bio_ai_cached=bio_cached,
                         lifestyle_cached=lifestyle_cached, questionnaire_cached=questionnaire_cached)
