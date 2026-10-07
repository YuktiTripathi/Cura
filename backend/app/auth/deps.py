import logging

from fastapi import Depends, Request

from app.auth.identity import authenticated_user_id
from app.auth.interface import AuthProvider
from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import ForbiddenError
from app.providers.registry import get_registry
from app.core.log_ids import subject_ref

logger = logging.getLogger("cura.auth")


def get_auth_provider() -> AuthProvider:
    return get_registry().auth


def get_principal(
    request: Request,
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthenticatedPrincipal:
    if settings.auth_provider == "mock" and not settings.is_development:
        raise ForbiddenError("Mock auth is development-only")
    if (
        settings.auth_provider == "mock"
        and not settings.dev_auth_header
        and not (settings.mock_user_id or "").strip()
    ):
        raise ForbiddenError("Development header auth is disabled")
    header_identity = request.headers.get("X-Cura-User-Id") or request.headers.get("x-cura-user-id")
    if header_identity and (settings.auth_provider or "").strip().lower() != "mock":
        header_identity = None
    if header_identity and not settings.is_development:
        raise ForbiddenError("X-Cura-User-Id is not allowed outside development")
    principal = provider.authenticate(request)
    authenticated_user_id(principal)
    if settings.is_development:
        logger.info(
            "auth_ok provider=%s subject_id=%s",
            (settings.auth_provider or "mock").strip().lower(),
            subject_ref(principal.subject_id),
        )
    return principal


def get_current_user(
    principal: AuthenticatedPrincipal = Depends(get_principal),
) -> AuthenticatedPrincipal:
    """Existing SuperShyft identity. CURA must not introduce a second login."""
    return principal
