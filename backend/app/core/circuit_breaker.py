"""Fail-fast after repeated dependency failures. Timeouts are not retried while open."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


class CircuitOpenError(RuntimeError):
    def __init__(self, name: str):
        super().__init__(f"circuit_open:{name}")
        self.name = name


@dataclass
class _State:
    failures: int = 0
    opened_at: float = 0.0
    open: bool = False


class CircuitBreaker:
    def __init__(self, name: str, *, failure_threshold: int = 3, recovery_seconds: float = 20.0):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = max(1.0, recovery_seconds)
        self._state = _State()
        self._lock = threading.Lock()

    def allow(self) -> None:
        with self._lock:
            if not self._state.open:
                return
            if time.monotonic() - self._state.opened_at >= self.recovery_seconds:
                self._state.open = False
                self._state.failures = 0
                return
            raise CircuitOpenError(self.name)

    def record_success(self) -> None:
        with self._lock:
            self._state.failures = 0
            self._state.open = False

    def reset(self) -> None:
        with self._lock:
            self._state = _State()

    def record_failure(self) -> None:
        with self._lock:
            self._state.failures += 1
            if self._state.failures >= self.failure_threshold:
                self._state.open = True
                self._state.opened_at = time.monotonic()


jev_breaker = CircuitBreaker("jev", failure_threshold=3, recovery_seconds=20)
openrouter_breaker = CircuitBreaker("openrouter", failure_threshold=3, recovery_seconds=20)
supershyft_breaker = CircuitBreaker("supershyft", failure_threshold=3, recovery_seconds=15)
