"""Development-only AUTH / PLAN / RETRIEVAL / CONTEXT / MODEL traces."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("cura.trace")

_SENSITIVE = frozenset(
    {
        "phone",
        "email",
        "mobile",
        "jwt",
        "otp",
        "token",
        "authorization",
        "access_token",
        "password",
    }
)


def trace(stage: str, **fields: Any) -> None:
    if not settings.is_development:
        return
    parts = [f"{key}={_safe(value)}" for key, value in fields.items() if value is not None]
    logger.info("%s %s", stage, " ".join(parts))


def _safe(value: Any) -> str:
    text = str(value)
    lowered = text.lower()
    if any(token in lowered for token in _SENSITIVE):
        return "[redacted]"
    return text[:240]
