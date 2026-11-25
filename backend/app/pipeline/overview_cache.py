"""Precomputed overview screens. The chat path still builds answers; these keys only hold UI payloads."""

from __future__ import annotations

import hashlib
import json
import logging
import threading

from app.core.request_controls import request_controls

logger = logging.getLogger("cura.overview_cache")

TTL_SECONDS = 600


def _subject(subject_id: str) -> str:
    return hashlib.sha256(subject_id.encode()).hexdigest()[:24]


def overview_key(subject_id: str) -> str:
    return f"user:{_subject(subject_id)}:cura:overview_v2"


def system_key(subject_id: str, system_slug: str) -> str:
    return f"user:{_subject(subject_id)}:cura:system:{system_slug}"


def read_payload(key: str):
    raw = request_controls._get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def write_payload(key: str, payload) -> None:
    body = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    request_controls._set(key, body, TTL_SECONDS)


def schedule_overview_precompute(principal, registry) -> None:
    threading.Thread(
        target=_precompute,
        args=(principal, registry),
        name="cura-overview-precompute",
        daemon=True,
    ).start()


def _precompute(principal, registry) -> None:
    from app.db.session import SessionLocal
    from app.pipeline.unified_service import build_category, build_overview

    db = SessionLocal()
    try:
        overview = build_overview(principal, registry, db)
        write_payload(overview_key(principal.subject_id), overview.model_dump(mode="json"))
        for card in overview.categories or []:
            detail = build_category(principal, registry, card.id, db)
            if detail is not None:
                write_payload(system_key(principal.subject_id, card.id), detail.model_dump(mode="json"))
    except Exception:
        logger.warning("overview_precompute status=failed", exc_info=True)
    finally:
        db.close()
