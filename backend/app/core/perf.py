"""Per-request performance trace: stage timings and counters, never health content.

One ``RequestPerf`` is bound to the request with a context variable. Worker threads see it
when their task is submitted through ``submit_with_context`` (or ``copy_context().run``).
Only numbers, stage names and internal identifiers are recorded; no names, messages,
values or other PHI, so the structured log line is safe to ship to log storage.
"""

from __future__ import annotations

import contextvars
import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger("cura.perf")

_current: contextvars.ContextVar["RequestPerf | None"] = contextvars.ContextVar("cura_request_perf", default=None)


@dataclass
class RequestPerf:
    request_id: str = ""
    started: float = field(default_factory=time.perf_counter)
    stages_ms: dict[str, int] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    flags: dict[str, object] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_ms(self, stage: str, ms: int) -> None:
        with self._lock:
            self.stages_ms[stage] = self.stages_ms.get(stage, 0) + int(ms)

    def count(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + n

    def set(self, name: str, value: object) -> None:
        with self._lock:
            self.flags[name] = value

    def total_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)

    def snapshot(self) -> dict:
        with self._lock:
            out = {
                "request_id": self.request_id,
                "total_ms": self.total_ms(),
                **{f"{k}_ms": v for k, v in sorted(self.stages_ms.items())},
                **dict(sorted(self.counters.items())),
                **dict(sorted(self.flags.items())),
            }
        out.setdefault("retry_count", 0)
        out.setdefault("provider_attempts", 0)
        out.setdefault("llm_calls", 0)
        out.setdefault("cache_hit", False)
        return out


def begin(request_id: str) -> RequestPerf:
    perf = RequestPerf(request_id=request_id)
    _current.set(perf)
    return perf


def current() -> RequestPerf | None:
    return _current.get()


def end() -> None:
    _current.set(None)


@contextmanager
def stage(name: str):
    """Time a block into the current request trace (no-op outside a request)."""
    perf = _current.get()
    started = time.perf_counter()
    try:
        yield
    finally:
        if perf is not None:
            perf.add_ms(name, int((time.perf_counter() - started) * 1000))


def count(name: str, n: int = 1) -> None:
    perf = _current.get()
    if perf is not None:
        perf.count(name, n)


def mark(name: str, value: object) -> None:
    perf = _current.get()
    if perf is not None:
        perf.set(name, value)


def submit_with_context(pool, fn, *args, **kwargs):
    """``pool.submit`` that keeps the request trace (and other context vars) in the worker."""
    ctx = contextvars.copy_context()
    return pool.submit(ctx.run, fn, *args, **kwargs)


def emit(extra: dict | None = None) -> dict | None:
    """Write one structured, PHI-free performance line for the request."""
    perf = _current.get()
    if perf is None:
        return None
    record = perf.snapshot()
    if extra:
        record.update({k: v for k, v in extra.items() if isinstance(v, (int, float, bool, str)) or v is None})
    logger.info("cura_perf %s", json.dumps(record, sort_keys=True))
    return record
