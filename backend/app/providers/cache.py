"""Short-lived cache of a member's Supershyft reads (readiness plan 5.5).

Each relevant turn used to re-read the member's data from the Supershyft database. Reads
are now reused for HEALTH_DATA_CACHE_SECONDS (default 90 s), which covers the follow-up
questions of one conversation without serving stale data for long. Entries are stored
through the request-control store, so they are shared across instances when Redis is
configured. Keys hash the member id and the parts of the query plan that change what is
read; question text is excluded except for the questionnaire, which uses it.
"""

from __future__ import annotations

import hashlib
import json
import logging
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

# Fields that only steer answer style or routing; they never change what is read.
_ANSWER_ONLY = {
    "raw_message", "premise_claim", "fallback_reason", "model_selection_reasons", "answer_model_tier",
    "model_tier", "reasoning_depth", "complexity", "response_mode", "question_type", "conversation_turn",
    "operations_hint", "answer_depth", "reasoning_required", "needs_guidance",
}


def _key(kind: str, principal: AuthenticatedPrincipal, plan: QueryPlan | None, *, include_text: bool) -> str:
    plan_part = ""
    if plan is not None:
        exclude = set(_ANSWER_ONLY) - ({"raw_message"} if include_text else set())
        plan_part = plan.model_dump_json(exclude=exclude)
    material = json.dumps([kind, principal.subject_id, plan_part, settings.health_data_cache_version])
    return "cura:health:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


class _Cached:
    def __init__(self, inner: Any, kind: str, adapter: TypeAdapter, *, include_text: bool = False, uses_plan: bool = True):
        self._inner = inner
        self._kind = kind
        self._adapter = adapter
        self._include_text = include_text
        self._uses_plan = uses_plan

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan):
        ttl = int(settings.health_data_cache_seconds or 0)
        if ttl <= 0:
            return self._inner.query(principal, plan)
        from app.core.metrics import HEALTH_DATA_CACHE
        from app.core.request_controls import request_controls

        key = _key(self._kind, principal, plan if self._uses_plan else None, include_text=self._include_text)
        try:
            raw = request_controls._get(key)
        except Exception:  # noqa: BLE001 - a cache outage must never fail the read
            raw = None
        if raw is not None:
            HEALTH_DATA_CACHE.labels(kind=self._kind, result="hit").inc()
            return self._adapter.validate_json(raw)
        HEALTH_DATA_CACHE.labels(kind=self._kind, result="miss").inc()
        result = self._inner.query(principal, plan)
        try:
            request_controls._set(key, self._adapter.dump_json(result).decode("utf-8"), ttl)
        except Exception:  # noqa: BLE001
            logger.warning("health_data_cache status=write_failed kind=%s", self._kind)
        return result


def cached_blood(inner) -> _Cached:
    return _Cached(inner, "blood", TypeAdapter(list[BloodReport]))


def cached_bio_ai(inner) -> _Cached:
    return _Cached(inner, "bio_ai", TypeAdapter(list[BioAIReport]))


def cached_lifestyle(inner) -> _Cached:
    return _Cached(inner, "lifestyle", TypeAdapter(LifestyleContext | None), uses_plan=False)


def cached_questionnaires(inner) -> _Cached:
    return _Cached(inner, "questionnaire", TypeAdapter(list[QuestionnaireInstance]), include_text=True)


WRAPPERS: dict[str, Callable] = {
    "blood": cached_blood,
    "bio_ai": cached_bio_ai,
    "lifestyle": cached_lifestyle,
    "questionnaires": cached_questionnaires,
}
