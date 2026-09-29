from __future__ import annotations

from fastapi import Request

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import UnauthorizedError


class SuperShyftJWTAuthProvider:
    """Validates a SuperShyft-issued bearer token; client-supplied user IDs are ignored."""

    def authenticate(self, request: Request) -> AuthenticatedPrincipal:
        header = request.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            raise UnauthorizedError("Bearer authentication required")
        token = header.split(" ", 1)[1].strip()
        if not token:
            raise UnauthorizedError("Bearer authentication required")
        if not settings.auth_jwt_secret:
            raise UnauthorizedError("Authentication is not configured")
        try:
            import jwt

            options = {"require": ["exp", "sub"]}
            kwargs = {
                "algorithms": [settings.auth_jwt_algorithm],
                "options": options,
            }
            if settings.auth_jwt_audience:
                kwargs["audience"] = settings.auth_jwt_audience
            else:
                kwargs["options"] = {**options, "verify_aud": False}
            if settings.auth_jwt_issuer:
                kwargs["issuer"] = settings.auth_jwt_issuer
            claims = jwt.decode(token, settings.auth_jwt_secret, **kwargs)
        except Exception as exc:
            raise UnauthorizedError("Invalid or expired authentication token") from exc
        subject = str(claims.get(settings.auth_subject_claim) or claims.get("sub") or "").strip()
        if not subject:
            raise UnauthorizedError("Authentication token has no subject")
        display = str(claims.get("given_name") or claims.get("name") or "").strip() or None
        return AuthenticatedPrincipal(subject_id=subject, display_name=display)
