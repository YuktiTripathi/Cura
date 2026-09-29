from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass

from app.contracts.chat import ChatRequest, ChatResponse
from app.core.config import settings
from app.core.errors import ProviderUnavailableError, RateLimitedError, ValidationAppError


@dataclass
class _Entry:
    expires_at: float
    value: str


class RequestControlStore:
    """Redis-backed production controls with a bounded in-process development fallback."""

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def _client(self):
        if self._redis is not None:
            return self._redis
        if not settings.redis_url:
            if settings.redis_required and not settings.is_development:
                raise ProviderUnavailableError(
                    "Request-control service is unavailable", reason="redis_not_configured"
                )
            return None
        try:
            import redis

            self._redis = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._redis.ping()
            return self._redis
        except Exception as exc:
            if settings.redis_required and not settings.is_development:
                raise ProviderUnavailableError(
                    "Request-control service is unavailable", reason="redis_unavailable"
                ) from exc
            return None

    @staticmethod
    def _subject_key(subject_id: str) -> str:
        return hashlib.sha256(subject_id.encode()).hexdigest()[:24]

    def check_rate_limit(self, subject_id: str) -> None:
        subject = self._subject_key(subject_id)
        window = max(1, settings.rate_limit_window_seconds)
        bucket = int(time.time() // window)
        key = f"cura:rate:{subject}:{bucket}"
        client = self._client()
        if client:
            count = client.incr(key)
            if count == 1:
                client.expire(key, window + 1)
        else:
            now = time.time()
            with self._lock:
                self._prune(now)
                entry = self._memory.get(key)
                count = int(entry.value) + 1 if entry else 1
                self._memory[key] = _Entry(now + window + 1, str(count))
        if count > max(1, settings.rate_limit_requests):
            raise RateLimitedError("Too many requests. Please try again shortly.")

    def idempotency_lookup(
        self,
        subject_id: str,
        idempotency_key: str | None,
        payload: ChatRequest,
    ) -> ChatResponse | None:
        if not idempotency_key:
            return None
        key = self._idempotency_key(subject_id, idempotency_key)
        payload_hash = self._payload_hash(payload)
        raw = self._get(key)
        if not raw:
            return None
        stored = json.loads(raw)
        if stored.get("payload_hash") != payload_hash:
            raise ValidationAppError("Idempotency-Key was already used for a different request")
        return ChatResponse.model_validate(stored["response"])

    def idempotency_store(
        self,
        subject_id: str,
        idempotency_key: str | None,
        payload: ChatRequest,
        response: ChatResponse,
    ) -> None:
        if not idempotency_key:
            return
        body = json.dumps(
            {
                "payload_hash": self._payload_hash(payload),
                "response": response.model_dump(mode="json"),
            },
            separators=(",", ":"),
        )
        self._set(
            self._idempotency_key(subject_id, idempotency_key),
            body,
            max(1, settings.idempotency_ttl_seconds),
        )

    def _get(self, key: str) -> str | None:
        client = self._client()
        if client:
            return client.get(key)
        now = time.time()
        with self._lock:
            self._prune(now)
            entry = self._memory.get(key)
            return entry.value if entry else None

    def _set(self, key: str, value: str, ttl: int) -> None:
        client = self._client()
        if client:
            client.setex(key, ttl, value)
            return
        with self._lock:
            self._memory[key] = _Entry(time.time() + ttl, value)

    def _prune(self, now: float) -> None:
        expired = [key for key, entry in self._memory.items() if entry.expires_at <= now]
        for key in expired:
            self._memory.pop(key, None)
        if len(self._memory) > 5000:
            for key in list(self._memory)[:1000]:
                self._memory.pop(key, None)

    def _idempotency_key(self, subject_id: str, supplied: str) -> str:
        digest = hashlib.sha256(supplied.encode()).hexdigest()
        return f"cura:idem:{self._subject_key(subject_id)}:{digest}"

    @staticmethod
    def _payload_hash(payload: ChatRequest) -> str:
        raw = payload.model_dump_json(exclude_none=True)
        return hashlib.sha256(raw.encode()).hexdigest()


request_controls = RequestControlStore()
