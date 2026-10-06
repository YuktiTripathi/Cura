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


_PLACEHOLDER_MARKERS = (
    "change-me", "changeme", "change_me", "placeholder", "example", "dev-secret", "devsecret",
    "secret", "test", "dummy", "your-", "your_", "xxx", "todo",
)


def _looks_placeholder(value: str | None) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True
    lowered = raw.lower()
    return any(marker == lowered or lowered.startswith(marker) for marker in _PLACEHOLDER_MARKERS)


def production_config_problems(cfg: Settings) -> list[str]:
    """Settings that must never reach production. Empty list means safe to start."""
    if cfg.is_development:
        return []
    problems: list[str] = []
    if (cfg.auth_provider or "").strip().lower() not in MOCK_AUTH_PROVIDERS:
        secret = cfg.auth_jwt_secret or ""
        algorithm = (cfg.auth_jwt_algorithm or "").upper()
        if (cfg.auth_jwks_url or "").strip():
            if not cfg.auth_jwks_url.strip().lower().startswith("https://"):
                problems.append("AUTH_JWKS_URL must use https")
        elif algorithm.startswith("HS") and (_looks_placeholder(secret) or len(secret) < 32):
            problems.append("AUTH_JWT_SECRET is empty, a placeholder, or shorter than 32 characters")
        if not (cfg.auth_jwt_issuer or "").strip() or not (cfg.auth_jwt_audience or "").strip():
            problems.append("AUTH_JWT_ISSUER and AUTH_JWT_AUDIENCE must be set")
    if cfg.enable_llm:
        if _looks_placeholder(cfg.active_llm_api_key()):
            problems.append("OPENROUTER_API_KEY is empty or a placeholder")
        if not cfg.openrouter_zero_data_retention:
            problems.append("OPENROUTER_ZERO_DATA_RETENTION must be true in production")
        if not (cfg.require_zdr_for_personal_health or cfg.cura_openrouter_require_zdr):
            problems.append("REQUIRE_ZDR_FOR_PERSONAL_HEALTH must be true in production")
    if is_real_health_provider(cfg.health_provider):
        url = (cfg.supershyft_database_url or "").lower()
        if not url or "password" in url or "localhost" in url or "127.0.0.1" in url:
            problems.append("SUPERSHYFT_DATABASE_URL is missing or points at a dev/placeholder target")
    if cfg.document_storage_backend == "local" and _looks_placeholder(cfg.document_encryption_key):
        problems.append("DOCUMENT_ENCRYPTION_KEY must be set in production")
    return problems


def assert_production_config(cfg: Settings) -> None:
    problems = production_config_problems(cfg)
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
