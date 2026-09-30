"""Startup and runtime safety invariants. Fail closed for patient-data misconfiguration."""

from __future__ import annotations

from app.core.config import Settings

REAL_HEALTH_PROVIDERS = frozenset({"supershyft", "postgres", "readonly"})
MOCK_AUTH_PROVIDERS = frozenset({"mock", ""})

REFUSE_MOCK_AUTH_WITH_REAL_HEALTH = (
    "Refusing to start: real health provider cannot be used with mock authentication."
)
REFUSE_PRODUCTION_MOCK_AUTH_WITH_REAL_HEALTH = (
    "Refusing to start: production cannot use mock authentication with a real health provider."
)


def is_real_health_provider(name: str | None) -> bool:
    return (name or "").strip().lower() in REAL_HEALTH_PROVIDERS


def is_mock_auth_provider(name: str | None) -> bool:
    return (name or "mock").strip().lower() in MOCK_AUTH_PROVIDERS


def assert_safe_auth_health_pairing(cfg: Settings) -> None:
    """Mock auth + real SuperShyft is never allowed in production.

    Development/test may opt in with ALLOW_MOCK_AUTH_WITH_REAL_HEALTH=true.
    That flag is ignored when APP_ENV is not a development environment.
    """
    if not (is_mock_auth_provider(cfg.auth_provider) and is_real_health_provider(cfg.health_provider)):
        return
    if not cfg.is_development:
        raise RuntimeError(REFUSE_PRODUCTION_MOCK_AUTH_WITH_REAL_HEALTH)
    if not cfg.allow_mock_auth_with_real_health:
        raise RuntimeError(REFUSE_MOCK_AUTH_WITH_REAL_HEALTH)
