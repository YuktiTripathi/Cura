from __future__ import annotations

import logging

from app.auth.models import AuthenticatedPrincipal
from app.contracts.me import MeCapabilities, MeResponse
from app.core.copy import greeting_for_first_name
from app.core.errors import ProviderUnavailableError
from app.pipeline.starters import build_starters, collect_snapshot
from app.providers.registry import ProviderRegistry
from app.voice.providers import voice_input_available
from app.core.log_ids import subject_ref

logger = logging.getLogger("cura.me")


def public_user_id(subject_id: str) -> str | int:
    value = str(subject_id).strip()
    return int(value) if value.isdigit() else value


def _capabilities_from_snapshot(snap, *, has_health_goals: bool = False) -> MeCapabilities:
    return MeCapabilities(
        has_blood_report=snap.has_blood,
        has_bio_ai_report=snap.has_bio,
        has_questionnaire=bool(getattr(snap, "has_questionnaire", False)),
        has_nutrition=snap.has_nutrition,
        has_health_scenario=bool(snap.has_blood or snap.has_bio),
        has_health_goals=has_health_goals,
        voice_input=voice_input_available(),
    )


def build_me_response(
    principal: AuthenticatedPrincipal,
    registry: ProviderRegistry,
    language: str | None = None,
    db=None,
) -> MeResponse:
    user_id = public_user_id(principal.subject_id)
    try:
        profile = registry.users.get_profile(principal)
    except ProviderUnavailableError:
        logger.warning(
            "supershyft_db operation=get_profile status=unavailable user_id=%s",
            subject_ref(principal.subject_id),
        )
        starters = build_starters(principal, registry, language, profile_available=False)
        return MeResponse(
            user_id=user_id,
            first_name=None,
            last_name=None,
            display_name=None,
            greeting=greeting_for_first_name(None, language),
            profile_available=False,
            capabilities=MeCapabilities(voice_input=voice_input_available()),
            starters=starters,
        )

    first = (profile.first_name or "").strip() or None
    last = (profile.last_name or "").strip() or None
    display = first
    snap = collect_snapshot(principal, registry)
    has_goals = False
    if db is not None:
        from app.db.goal_store import GoalStore

        has_goals = bool(GoalStore(db).list_for_subject(principal.subject_id))
    return MeResponse(
        user_id=user_id,
        first_name=first,
        last_name=last,
        display_name=display,
        greeting=greeting_for_first_name(first, language),
        profile_available=True,
        capabilities=_capabilities_from_snapshot(snap, has_health_goals=has_goals),
        starters=build_starters(
            principal,
            registry,
            language,
            snapshot=snap,
            profile_available=True,
        ),
    )
