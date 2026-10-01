"""Remove credentials and account identifiers before the medical model sees a payload."""

from __future__ import annotations

from typing import Any

_IDENTITY_KEYS = frozenset(
    {
        "phone",
        "email",
        "mobile",
        "jwt",
        "otp",
        "access_token",
        "refresh_token",
        "authorization",
        "token",
        "subject_id",
        "user_id",
        "userid",
        "userId",
        "subjectId",
    }
)


def sanitize_model_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_model_payload(item)
            for key, item in value.items()
            if key not in _IDENTITY_KEYS
        }
    if isinstance(value, list):
        return [sanitize_model_payload(item) for item in value]
    return value


def payload_contains_identity(value: Any) -> bool:
    if isinstance(value, dict):
        if any(key in _IDENTITY_KEYS for key in value):
            return True
        return any(payload_contains_identity(item) for item in value.values())
    if isinstance(value, list):
        return any(payload_contains_identity(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(token in lowered for token in ("bearer ", "otp=", "eyj"))
    return False
