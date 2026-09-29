from typing import Protocol

from fastapi import Request

from app.auth.models import AuthenticatedPrincipal


class AuthProvider(Protocol):
    def authenticate(self, request: Request) -> AuthenticatedPrincipal:
        ...
