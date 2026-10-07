"""Member ids in logs (readiness plan 1.9): a stable short hash, never the raw id."""

from __future__ import annotations

import hashlib


def subject_ref(subject_id: str | None) -> str:
    return hashlib.sha256((subject_id or "").encode("utf-8")).hexdigest()[:12]
