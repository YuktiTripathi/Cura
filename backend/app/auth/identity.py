"""Server-side identity helpers. Client-supplied user IDs are never authoritative."""

from __future__ import annotations

from typing import Any

from app.auth.models import AuthenticatedPrincipal
from app.core.errors import UnauthorizedError

_CLIENT_IDENTITY_KEYS = frozenset(
    {
        "user_id",
        "userId",
        "userid",
        "subject_id",
        "subjectId",
        "phone",
        "email",
        "mobile",
        "otp",
    }
)


def authenticated_user_id(principal: AuthenticatedPrincipal) -> str:
    subject = str(principal.subject_id or "").strip()
    if not subject:
        raise UnauthorizedError("Authentication required")
    return subject


def drop_client_identity(payload: Any) -> Any:
    """Remove identity fields from a request body before model construction."""
    if not isinstance(payload, dict):
        return payload
    return {key: value for key, value in payload.items() if key not in _CLIENT_IDENTITY_KEYS}
