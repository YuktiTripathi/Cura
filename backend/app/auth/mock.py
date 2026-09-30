from fastapi import Request

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import UnauthorizedError


class MockAuthProvider:
    """Development-only auth. Never use in production.

    When MOCK_USER_ID is set, that identity is the default principal so local
    SuperShyft testing does not require a request header. A header may override
    only when ALLOW_MOCK_HEADER_OVERRIDE=true in a development environment.
    """

    def authenticate(self, request: Request) -> AuthenticatedPrincipal:
        if not settings.is_development:
            raise UnauthorizedError("Mock authentication is development-only")
        pinned = (settings.mock_user_id or "").strip()
        header = (
            request.headers.get("X-Cura-User-Id") or request.headers.get("x-cura-user-id") or ""
        ).strip()
        if (
            header
            and settings.dev_auth_header
            and (settings.allow_mock_header_override or not pinned)
        ):
            subject = header
        elif pinned:
            subject = pinned
        else:
            raise UnauthorizedError("Development auth requires MOCK_USER_ID or X-Cura-User-Id")
        return AuthenticatedPrincipal(
            subject_id=subject,
            roles=["member"],
            consent_scopes=["health.read", "chat.write"],
            display_name=None,
        )
