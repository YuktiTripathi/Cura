"""Cache of a member's SuperShyft provider reads.

Stores provider payloads (reports, lifestyle, questionnaire instances), never a
HealthContext and never a model answer. The chat turn still plans, builds context,
selects evidence, and validates safety. A hit only skips the database read.

Keys are an opaque member hash, data kind, and scope (latest or history).
The raw member id is not part of the Redis key. AuthenticatedPrincipal has no
tenant id. SuperShyft user ids are unique in that one database, so the hash of
the member id is the isolation boundary. Do not reuse an entry across member ids.

SuperShyft writes are outside CURA. This module does not observe them. Freshness is
the configurable TTL, or an explicit invalidate_health_data call. An expired entry
is not returned. A valid unexpired entry may be served when the database is down.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import TypeAdapter

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.lifestyle import LifestyleContext
from app.contracts.query import QueryPlan
from app.contracts.questionnaire import QuestionnaireInstance
from app.core.config import settings

logger = logging.getLogger("cura.providers")

KINDS = ("blood", "bio_ai", "lifestyle", "questionnaire")
SCOPES = ("latest", "history")
_HISTORY_OPS = {"trend", "previous", "compare"}


def member_token(subject_id: str) -> str:
    """Stable opaque id. The Redis key does not contain the raw member id."""
    return hashlib.sha256(str(subject_id).encode("utf-8")).hexdigest()[:32]


def cache_scope(plan: QueryPlan | None) -> str:
    """History is a separate entry so a two-report cache cannot answer a deeper trend."""
    if plan is None:
        return "latest"
    if (
        plan.history
        or plan.compare
        or plan.report_id
        or plan.time_operation in _HISTORY_OPS
    ):
        return "history"
    return "latest"


def _scope_label(kind: str, scope: str) -> str:
    if kind == "lifestyle" and scope != "history":
        return "current"
    if scope in {"standard", "latest"}:
        return "latest"
    return "history"


def storage_key(kind: str, subject_id: str, scope: str) -> str:
    label = _scope_label(kind, scope)
    return f"cura:health:{member_token(subject_id)}:{kind}:{label}"


def peek(kind: str, subject_id: str, scope: str, adapter: TypeAdapter) -> Any | None:
    """Read a warm entry. Does not load from SuperShyft."""
    from app.core.request_controls import request_controls

    raw = _read(request_controls, storage_key(kind, subject_id, scope))
    if raw is None:
        return None
    try:
        return _unwrap(raw, adapter)
    except Exception:  # noqa: BLE001
        return None


def invalidate_health_data(subject_id: str, kind: str | None = None) -> None:
    """Drop one member's provider cache. Not called by SuperShyft writes."""
    from app.core.request_controls import request_controls

    kinds = (kind,) if kind else KINDS
    for item in kinds:
        for scope in ("latest", "history", "current"):
            key = storage_key(item, subject_id, scope)
            try:
                request_controls._delete(key)
                request_controls._delete(key + ":lock")
            except Exception:  # noqa: BLE001
                logger.warning("health_data_cache status=invalidate_failed kind=%s", item)


def read_through(kind: str, subject_id: str, scope: str, adapter: TypeAdapter, loader: Callable[[], Any]) -> Any:
    """Return a cached provider payload, or load it once and store it."""
    ttl = int(settings.health_data_cache_seconds or 0)
    if ttl <= 0:
        return loader()
    from app.core.metrics import HEALTH_DATA_CACHE
    from app.core.request_controls import request_controls

    key = storage_key(kind, subject_id, scope)
    cached = _read(request_controls, key)
    if cached is not None:
        HEALTH_DATA_CACHE.labels(kind=kind, result="hit").inc()
        return _unwrap(cached, adapter)
    HEALTH_DATA_CACHE.labels(kind=kind, result="miss").inc()

    lock_key = key + ":lock"
    token = uuid.uuid4().hex
    owned = False
    try:
        owned = bool(request_controls._set_nx(lock_key, token, int(settings.health_data_cache_lock_seconds or 20)))
    except Exception:  # noqa: BLE001 - locking must not block the read
        logger.warning("health_data_cache status=lock_failed kind=%s", kind)
        return _load_and_store(request_controls, key, ttl, adapter, loader, kind)

    if not owned:
        waited = _wait(request_controls, key, float(settings.health_data_cache_wait_seconds or 5))
        if waited is not None:
            HEALTH_DATA_CACHE.labels(kind=kind, result="hit").inc()
            return _unwrap(waited, adapter)
        filled = _read(request_controls, key)
        if filled is not None:
            HEALTH_DATA_CACHE.labels(kind=kind, result="hit").inc()
            return _unwrap(filled, adapter)
        logger.warning("health_data_cache status=lock_wait_elapsed kind=%s", kind)
        return _load_and_store(request_controls, key, ttl, adapter, loader, kind)
    filled = _read(request_controls, key)
    if filled is not None:
        try:
            request_controls._compare_delete(lock_key, token)
        except Exception:  # noqa: BLE001
            logger.warning("health_data_cache status=unlock_failed kind=%s", kind)
        HEALTH_DATA_CACHE.labels(kind=kind, result="hit").inc()
        return _unwrap(filled, adapter)
    try:
        return _load_and_store(request_controls, key, ttl, adapter, loader, kind)
    finally:
        try:
            request_controls._compare_delete(lock_key, token)
        except Exception:  # noqa: BLE001
            logger.warning("health_data_cache status=unlock_failed kind=%s", kind)


def _read(store, key: str) -> str | None:
    try:
        return store._get(key)
    except Exception:  # noqa: BLE001
        return None


def _wait(store, key: str, seconds: float) -> str | None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        raw = _read(store, key)
        if raw is not None:
            return raw
        time.sleep(0.05)
    return _read(store, key)


def _source_ids(result: Any) -> list[str]:
    rows = result if isinstance(result, list) else [result]
    ids: list[str] = []
    for item in rows:
        if item is None:
            continue
        for attr in ("report_id", "assessment_instance_id"):
            value = getattr(item, attr, None)
            if value:
                ids.append(str(value))
                break
    return ids


def _pack(kind: str, scope: str, result: Any, adapter: TypeAdapter) -> str:
    label = _scope_label(kind, scope)
    body = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_ids": _source_ids(result),
        "version": settings.health_data_cache_version,
        "scope": label,
        "complete": label == "history",
        "payload": json.loads(adapter.dump_json(result)),
    }
    return json.dumps(body)


def _unwrap(raw: str, adapter: TypeAdapter) -> Any:
    data = json.loads(raw)
    if isinstance(data, dict) and "payload" in data:
        return adapter.validate_python(data["payload"])
    return adapter.validate_json(raw)


def _load_and_store(store, key: str, ttl: int, adapter: TypeAdapter, loader: Callable[[], Any], kind: str) -> Any:
    result = loader()
    try:
        scope = "history" if key.endswith(":history") else "latest"
        store._set(key, _pack(kind, scope, result, adapter), ttl)
    except Exception:  # noqa: BLE001
        logger.warning("health_data_cache status=write_failed kind=%s", kind)
    return result


def _explicit_marker_keys(plan: QueryPlan) -> list[str]:
    from app.pipeline.ontology import retrieval_metric_keys

    return list(retrieval_metric_keys(plan))


def _needs_history_backfill(plan: QueryPlan) -> bool:
    """One older-report read only for a personal question that names a marker."""
    if not plan.needs_blood:
        return False
    if getattr(plan.knowledge_scope, "value", plan.knowledge_scope) == "general":
        return False
    if getattr(plan.intent, "value", "") == "general_health_question":
        return False
    if cache_scope(plan) == "history":
        return False
    return bool(_explicit_marker_keys(plan))


def _keys_present(reports: list[BloodReport]) -> set[str]:
    return {marker.key for report in reports or [] for marker in report.markers or [] if marker.key}


def backfill_missing_markers(latest: list[BloodReport], history: list[BloodReport], plan: QueryPlan) -> list[BloodReport]:
    """Add the newest older report that contains each requested marker the latest read lacks.

    Latest markers stay on their own reports. An older value keeps that report's date.
    """
    missing = [key for key in _explicit_marker_keys(plan) if key not in _keys_present(latest)]
    if not missing:
        return latest
    seen = {report.report_id for report in latest}
    still = set(missing)
    older: list[BloodReport] = []
    for report in reversed(list(history or [])):
        if report.report_id in seen:
            continue
        matched = [marker for marker in report.markers or [] if marker.key in still and marker.value is not None]
        if not matched:
            continue
        older.append(report.model_copy(update={"markers": matched}))
        seen.add(report.report_id)
        still -= {marker.key for marker in matched}
        if not still:
            break
    return list(latest) + list(reversed(older))


class _Cached:
    """Test and registry wrapper. Caches the provider query by member and scope.

    Production SuperShyft providers cache their own unfiltered load and then apply
    the plan, so a hit is not the previous question's filtered slice.
    """

    def __init__(self, inner: Any, kind: str, adapter: TypeAdapter):
        self._inner = inner
        self._kind = kind
        self._adapter = adapter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan):
        if hasattr(self._inner, "load_for_cache") and hasattr(self._inner, "apply_plan"):
            scope = cache_scope(plan)
            payload = read_through(
                self._kind,
                principal.subject_id,
                scope,
                self._adapter,
                lambda: self._inner.load_for_cache(principal, scope),
            )
            shaped = self._inner.apply_plan(payload, plan)
            if self._kind == "blood" and _needs_history_backfill(plan) and any(
                key not in _keys_present(shaped) for key in _explicit_marker_keys(plan)
            ):
                history = read_through(
                    self._kind,
                    principal.subject_id,
                    "history",
                    self._adapter,
                    lambda: self._inner.load_for_cache(principal, "history"),
                )
                return backfill_missing_markers(shaped, history, plan)
            return shaped
        scope = cache_scope(plan) if self._kind in {"blood", "bio_ai"} else "latest"
        return read_through(
            self._kind,
            principal.subject_id,
            scope,
            self._adapter,
            lambda: self._inner.query(principal, plan),
        )


def cached_blood(inner) -> _Cached:
    return _Cached(inner, "blood", TypeAdapter(list[BloodReport]))


def cached_bio_ai(inner) -> _Cached:
    return _Cached(inner, "bio_ai", TypeAdapter(list[BioAIReport]))


def cached_lifestyle(inner) -> _Cached:
    return _Cached(inner, "lifestyle", TypeAdapter(LifestyleContext | None))


def cached_questionnaires(inner) -> _Cached:
    return _Cached(inner, "questionnaire", TypeAdapter(list[QuestionnaireInstance]))


WRAPPERS: dict[str, Callable] = {
    "blood": cached_blood,
    "bio_ai": cached_bio_ai,
    "lifestyle": cached_lifestyle,
    "questionnaires": cached_questionnaires,
}
