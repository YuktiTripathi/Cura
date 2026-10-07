"""Cache of model answers for identical prompts (readiness plan 6, lever 5).

The key is a hash of the exact prompt (system text, the member's data, the question and
the conversation focus) plus the model. Any change in the member's data or the question
changes the prompt, so a stale answer cannot be served. Only the raw model output is
cached: grounding, safety review and translation still run on every use. Entries live in
Redis when configured (shared across instances) or in process, for ANSWER_CACHE_TTL_SECONDS.
"""

from __future__ import annotations

import hashlib
import json
import logging

from app.core.config import settings
from app.llm.models import LLMStructuredOutput

logger = logging.getLogger("cura.llm")


def _key(messages: list[dict[str, str]], model: str) -> str:
    material = json.dumps({"model": model, "messages": messages, "v": settings.answer_cache_version}, sort_keys=True)
    return "cura:answer:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _enabled() -> bool:
    return int(settings.answer_cache_ttl_seconds or 0) > 0


def answer_cache_get(messages: list[dict[str, str]], model: str) -> LLMStructuredOutput | None:
    if not _enabled():
        return None
    from app.core.metrics import ANSWER_CACHE
    from app.core.request_controls import request_controls

    try:
        raw = request_controls._get(_key(messages, model))
    except Exception:  # noqa: BLE001 - a cache outage must never fail the answer
        return None
    if not raw:
        ANSWER_CACHE.labels(result="miss").inc()
        return None
    ANSWER_CACHE.labels(result="hit").inc()
    return LLMStructuredOutput.model_validate_json(raw)


def answer_cache_put(messages: list[dict[str, str]], model: str, result: LLMStructuredOutput) -> None:
    if not _enabled() or result.parse_error or result.truncated or not (result.answer or "").strip():
        return
    from app.core.request_controls import request_controls

    try:
        request_controls._set(_key(messages, model), result.model_dump_json(), int(settings.answer_cache_ttl_seconds))
    except Exception:  # noqa: BLE001
        logger.warning("answer_cache status=write_failed")
