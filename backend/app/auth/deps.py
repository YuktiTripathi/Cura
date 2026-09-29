from fastapi import Depends, Request

from app.auth.interface import AuthProvider
from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.core.errors import ForbiddenError
from app.providers.registry import get_registry


def get_auth_provider() -> AuthProvider:
    return get_registry().auth


def get_principal(
    request: Request,
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthenticatedPrincipal:
    if settings.auth_provider == "mock" and not settings.is_development:
        raise ForbiddenError("Mock auth is development-only")
    if settings.auth_provider == "mock" and not settings.dev_auth_header:
        raise ForbiddenError("Development header auth is disabled")
    return provider.authenticate(request)
