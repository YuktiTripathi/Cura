from fastapi import Request

from app.auth.models import AuthenticatedPrincipal
from app.core.errors import UnauthorizedError


class MockAuthProvider:
    """Development-only auth via X-Cura-User-Id. Never use in production."""

    def authenticate(self, request: Request) -> AuthenticatedPrincipal:
        subject = request.headers.get("X-Cura-User-Id") or request.headers.get("x-cura-user-id")
        if not subject:
            raise UnauthorizedError("Development auth requires X-Cura-User-Id")
        return AuthenticatedPrincipal(
            subject_id=subject.strip(),
            roles=["member"],
            consent_scopes=["health.read", "chat.write"],
            display_name=None,
        )
