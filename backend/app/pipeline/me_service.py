from __future__ import annotations

import logging
import threading

from app.auth.models import AuthenticatedPrincipal
from app.contracts.me import MeCapabilities, MeResponse
from app.core.copy import greeting_for_first_name
from app.core.errors import ProviderUnavailableError
from app.pipeline.starters import HealthSnapshot, build_starters
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


def _snapshot_from_cache(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> HealthSnapshot:
    """Starter chips use a warm latest cache only. A miss does not read SuperShyft."""
    from pydantic import TypeAdapter

    from app.contracts.bio_ai import BioAIReport
    from app.contracts.blood import BloodReport
    from app.providers.cache import peek

    snap = HealthSnapshot(available=True)
    blood = peek("blood", principal.subject_id, "latest", TypeAdapter(list[BloodReport])) or []
    bio = peek("bio_ai", principal.subject_id, "latest", TypeAdapter(list[BioAIReport])) or []
    if blood:
        snap.has_blood = True
        ordered = sorted(blood, key=lambda report: (report.report_date, report.report_id))
        latest = ordered[-1]
        snap.markers = [marker for marker in latest.markers if marker.value is not None]
        counts: dict[str, int] = {}
        for report in ordered:
            for key in {marker.key for marker in report.markers if marker.value is not None}:
                counts[key] = counts.get(key, 0) + 1
        snap.marker_history = counts
    if bio:
        snap.has_bio = True
        latest_bio = sorted(bio, key=lambda report: (report.report_date, report.report_id))[-1]
        snap.bio_risks = list(latest_bio.risks or [])
    _apply_lifestyle(snap, principal, registry)
    return snap


def _apply_lifestyle(snap: HealthSnapshot, principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> None:
    """Nutrition is a lifestyle flag, not a blood-history read."""
    from app.contracts.common import IntentType, KnowledgeScope
    from app.contracts.query import QueryPlan

    try:
        life = registry.lifestyle.query(
            principal,
            QueryPlan(
                intent=IntentType.broad_health_summary,
                needs_lifestyle=True,
                knowledge_scope=KnowledgeScope.personal,
            ),
        )
    except Exception:  # noqa: BLE001
        return
    if not life or not life.notes:
        return
    blob = " ".join(life.notes).lower()
    if "diet" in blob or "nutrition" in blob:
        snap.has_nutrition = True
        snap.lifestyle_topics.add("diet")
    if "sleep" in blob:
        snap.lifestyle_topics.add("sleep")
    if "activity" in blob or "exercise" in blob:
        snap.lifestyle_topics.add("activity")


def preload_latest(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> None:
    """Fill blood:latest and bio_ai:latest through the same cache path chat uses."""
    _preload_one(principal, registry, "blood")
    _preload_one(principal, registry, "bio_ai")


def preload_for_entry(principal: AuthenticatedPrincipal, registry: ProviderRegistry, context_ref) -> None:
    """Warm only the dataset the member just opened. A general question starts nothing."""
    if context_ref is None:
        return
    kind = getattr(context_ref, "type", None)
    entry = getattr(context_ref, "entry_point", None)
    if kind in {"blood_report", "blood_marker"} or entry == "blood_report_overview":
        _preload_one(principal, registry, "blood")
    elif kind in {"bio_ai_report", "bio_ai_risk"}:
        _preload_one(principal, registry, "bio_ai")


def _preload_one(principal: AuthenticatedPrincipal, registry: ProviderRegistry, kind: str) -> None:
    from app.contracts.common import IntentType, KnowledgeScope
    from app.contracts.query import QueryPlan

    if kind == "blood":
        plan = QueryPlan(
            intent=IntentType.latest_result,
            needs_blood=True,
            history=False,
            time_operation="latest_marker",
            knowledge_scope=KnowledgeScope.personal,
        )
        try:
            registry.blood.query(principal, plan)
        except Exception:  # noqa: BLE001
            logger.warning("health_preload status=blood_failed")
        return
    plan = QueryPlan(
        intent=IntentType.bio_ai_score,
        needs_bio_ai=True,
        history=False,
        time_operation="latest_marker",
        knowledge_scope=KnowledgeScope.personal,
    )
    try:
        registry.bio_ai.query(principal, plan)
    except Exception:  # noqa: BLE001
        logger.warning("health_preload status=bio_ai_failed")


def schedule_entry_preload(principal: AuthenticatedPrincipal, registry: ProviderRegistry, context_ref) -> None:
    if context_ref is None:
        return
    threading.Thread(
        target=preload_for_entry,
        args=(principal, registry, context_ref),
        name="cura-entry-preload",
        daemon=True,
    ).start()


def schedule_latest_preload(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> None:
    """Start the fill and return. /me must not join this thread."""
    threading.Thread(
        target=preload_latest,
        args=(principal, registry),
        name="cura-health-preload",
        daemon=True,
    ).start()


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
    snap = _snapshot_from_cache(principal, registry)
    schedule_latest_preload(principal, registry)
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
