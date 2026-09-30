"""Request-level time budget so Jev + LLM + retrieval cannot stack indefinitely."""

from __future__ import annotations

import time


class TimeBudget:
    def __init__(self, total_seconds: float):
        self.total_seconds = max(1.0, float(total_seconds))
        self.started = time.monotonic()
        self.deadline = self.started + self.total_seconds

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())

    def expired(self) -> bool:
        return self.remaining() <= 0

    def timeout_for(self, stage_seconds: float, *, minimum: float = 0.2) -> float:
        return max(minimum, min(float(stage_seconds), self.remaining()))
