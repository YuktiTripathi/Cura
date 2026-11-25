"""One current snapshot per member. Keys use a hash, never the raw member id."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.auth.models import AuthenticatedPrincipal
from app.biomarkers.health_categories import REGISTRY_VERSION
from app.contracts.member_snapshot import MemberSnapshot
from app.core.config import settings
from app.core.metrics import SNAPSHOT_CACHE, SNAPSHOT_PAYLOAD_BYTES
from app.providers.cache import member_token
from app.snapshot.assemble import assemble_snapshot

logger = logging.getLogger("cura.snapshot")


def snapshot_key(subject_id: str) -> str:
    from app.biomarkers.medical_registry import CONTENT_VERSION, library_revision

    return (
        f"cura:snapshot:{member_token(subject_id)}:"
        f"{settings.member_snapshot_schema_version}:{REGISTRY_VERSION}:{CONTENT_VERSION}:{library_revision()}"
    )


def invalidate_snapshot(subject_id: str) -> None:
    from app.core.request_controls import request_controls

    key = snapshot_key(subject_id)
    try:
        request_controls._delete(key)
        request_controls._delete(key + ":lock")
    except Exception:
        logger.warning("snapshot_cache status=invalidate_failed")


def _read(store, key: str) -> MemberSnapshot | None:
    try:
        raw = store._get(key)
    except Exception:
        logger.warning("snapshot_cache status=read_failed")
        return None
    if not raw:
        return None
    try:
        return MemberSnapshot.model_validate_json(raw)
    except Exception:
        logger.warning("snapshot_cache status=decode_failed")
        return None


def _store(store, key: str, snapshot: MemberSnapshot, ttl: int) -> None:
    body = snapshot.model_dump_json()
    SNAPSHOT_PAYLOAD_BYTES.set(len(body.encode()))
    try:
        store._set(key, body, ttl)
    except Exception:
        logger.warning("snapshot_cache status=write_failed")


def _wait(store, key: str, seconds: float) -> MemberSnapshot | None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        found = _read(store, key)
        if found is not None:
            return found
        time.sleep(0.05)
    return _read(store, key)


def load_snapshot(principal: AuthenticatedPrincipal, registry, *, refresh: bool = False) -> MemberSnapshot:
    """Return the current snapshot. Expired entries are misses, not silent hits."""
    from app.core.request_controls import request_controls
    from app.providers.cache import invalidate_health_data

    ttl = int(settings.member_snapshot_ttl_seconds or 0)
    if refresh:
        invalidate_snapshot(principal.subject_id)
        try:
            invalidate_health_data(principal.subject_id)
        except Exception:
            logger.warning("snapshot_cache status=provider_invalidate_failed")
    if ttl <= 0:
        SNAPSHOT_CACHE.labels(result="bypass").inc()
        return assemble_snapshot(principal, registry)

    key = snapshot_key(principal.subject_id)
    if not refresh:
        cached = _read(request_controls, key)
        if cached is not None and cached.registry_version == REGISTRY_VERSION and cached.schema_version == settings.member_snapshot_schema_version:
            age_s = None
            if cached.built_at is not None:
                built = cached.built_at
                if built.tzinfo is None:
                    built = built.replace(tzinfo=timezone.utc)
                age_s = int(max(0, (datetime.now(timezone.utc) - built).total_seconds()))
            logger.info("snapshot_cache status=hit age_seconds=%s", age_s)
            SNAPSHOT_CACHE.labels(result="hit").inc()
            return cached
    SNAPSHOT_CACHE.labels(result="miss").inc()

    lock_key = key + ":lock"
    token = uuid.uuid4().hex
    owned = False
    try:
        owned = bool(request_controls._set_nx(lock_key, token, int(settings.member_snapshot_lock_seconds or 20)))
    except Exception:
        logger.warning("snapshot_cache status=lock_unavailable")
        return assemble_snapshot(principal, registry)

    if not owned:
        waited = _wait(request_controls, key, float(settings.member_snapshot_wait_seconds or 5))
        if waited is not None:
            SNAPSHOT_CACHE.labels(result="hit").inc()
            return waited
        logger.warning("snapshot_cache status=lock_expired")
        return assemble_snapshot(principal, registry)
    try:
        again = _read(request_controls, key)
        if again is not None and not refresh:
            SNAPSHOT_CACHE.labels(result="hit").inc()
            return again
        snapshot = assemble_snapshot(principal, registry)
        _store(request_controls, key, snapshot, ttl)
        return snapshot
    finally:
        try:
            request_controls._compare_delete(lock_key, token)
        except Exception:
            logger.warning("snapshot_cache status=unlock_failed")
