from __future__ import annotations

from fastapi import Request

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import UnauthorizedError


class SuperShyftJWTAuthProvider:
    """Validates a SuperShyft-issued bearer token; client-supplied user IDs are ignored."""

    def authenticate(self, request: Request) -> AuthenticatedPrincipal:
        header = request.headers.get("Authorization", "")
        token = ""
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
        if not token:
            token = (request.cookies.get("cura_session") or "").strip()
        if not token:
            raise UnauthorizedError("Bearer authentication required")
        jwks_url = (settings.auth_jwks_url or "").strip()
        if not jwks_url and not settings.auth_jwt_secret:
            raise UnauthorizedError("Authentication is not configured")
        try:
            import jwt

            options = {"require": ["exp", "iss", "aud"] if jwks_url else ["exp"]}
            if jwks_url:
                # Asymmetric tokens: Cura only holds Supershyft's public keys, so a Cura
                # leak cannot mint tokens. Never accept HS* or "none" on this path.
                algorithms = [a for a in _asymmetric_algorithms() if not a.upper().startswith("HS")]
                key = _jwks_client(jwks_url).get_signing_key_from_jwt(token).key
            else:
                algorithms = [settings.auth_jwt_algorithm]
                key = settings.auth_jwt_secret
            kwargs = {
                "algorithms": algorithms,
                "options": options,
            }
            if settings.auth_jwt_audience:
                kwargs["audience"] = settings.auth_jwt_audience
            else:
                kwargs["options"] = {**options, "verify_aud": False}
            if settings.auth_jwt_issuer:
                kwargs["issuer"] = settings.auth_jwt_issuer
            claims = jwt.decode(token, key, **kwargs)
        except Exception as exc:
            raise UnauthorizedError("Invalid or expired authentication token") from exc
        subject = _subject_from_claims(claims)
        if not subject:
            raise UnauthorizedError("Authentication token has no subject")
        display = str(claims.get("given_name") or claims.get("name") or "").strip() or None
        return AuthenticatedPrincipal(subject_id=subject, display_name=display)


def _subject_from_claims(claims: dict) -> str:
    """Internal SuperShyft user id only. Phone/email claims are never used as identity."""
    for key in (settings.auth_subject_claim, "sub", "user_id", "userId"):
        raw = claims.get(key)
        if raw is None or raw == "":
            continue
        return str(raw).strip()
    return ""


_JWKS_CLIENTS: dict[str, object] = {}


def _asymmetric_algorithms() -> list[str]:
    raw = settings.auth_jwt_algorithms or "RS256"
    return [item.strip() for item in raw.split(",") if item.strip()]


def _jwks_client(url: str):
    """Cached JWKS client; keys are refetched when Supershyft rotates them (unknown kid)."""
    client = _JWKS_CLIENTS.get(url)
    if client is None:
        from jwt import PyJWKClient

        client = PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)
        _JWKS_CLIENTS[url] = client
    return client
