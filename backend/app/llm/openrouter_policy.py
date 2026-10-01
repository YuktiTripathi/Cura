"""Single OpenRouter production policy. Do not scatter provider restrictions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.registry import model_id_for_tier, model_registry, provider_for_model
from app.pipeline.dev_trace import trace

logger = logging.getLogger("cura.llm")

_UPSTREAM_SLUGS = {
    "openai": "OpenAI",
    "google": "Google",
    "anthropic": "Anthropic",
    "typesafe": "Typesafe",
}


@dataclass(frozen=True)
class OpenRouterPolicy:
    allowed_models: frozenset[str]
    allowed_providers: frozenset[str]
    allowed_upstream_providers: frozenset[str]
    require_zdr: bool
    deny_data_collection: bool
    prompt_injection_protection: bool
    dlp_enabled: bool
    clinical_safety_enabled: bool
    package_safety_enabled: bool
    request_timeout: float
    max_retries: int
    zdr_configured: bool = False
    extra_models: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def load(cls) -> "OpenRouterPolicy":
        models = {item.strip() for item in (settings.llm_allowed_models or "").split(",") if item.strip()}
        extra = {item.strip() for item in (settings.cura_openrouter_allowed_models or "").split(",") if item.strip()}
        models.update(extra)
        models.update(model_registry().values())
        models.add(settings.jev_model)
        models.add(settings.active_llm_model())
        if (settings.eval_candidate_model or "").strip():
            models.add(settings.eval_candidate_model.strip())
        gateway = {item.strip().lower() for item in (settings.llm_allowed_providers or "openrouter").split(",") if item.strip()}
        upstream = {
            item.strip().lower()
            for item in (settings.cura_openrouter_allowed_providers or "openai,google,anthropic,typesafe").split(",")
            if item.strip()
        }
        require_zdr = bool(settings.cura_openrouter_require_zdr or settings.require_zdr_for_personal_health)
        deny = bool(settings.cura_openrouter_deny_data_collection and settings.openrouter_data_collection_deny)
        return cls(
            allowed_models=frozenset(models),
            allowed_providers=frozenset(gateway),
            allowed_upstream_providers=frozenset(upstream),
            require_zdr=require_zdr,
            deny_data_collection=deny or require_zdr,
            prompt_injection_protection=bool(settings.cura_openrouter_prompt_injection_protection),
            dlp_enabled=bool(settings.cura_openrouter_dlp_enabled),
            clinical_safety_enabled=bool(settings.cura_clinical_safety_enabled),
            package_safety_enabled=bool(settings.cura_package_safety_enabled),
            request_timeout=float(settings.llm_timeout_seconds),
            max_retries=int(settings.llm_max_retries),
            zdr_configured=bool(settings.openrouter_zero_data_retention),
        )

    def assert_gateway(self) -> str:
        provider = settings.resolved_llm_provider()
        if provider not in self.allowed_providers:
            raise LLMUnavailableError("LLM provider is not on the approved allowlist")
        return provider

    def assert_model(self, model_id: str) -> str:
        selected = (model_id or "").strip()
        if selected not in self.allowed_models:
            raise LLMUnavailableError("LLM model is not on the approved allowlist")
        upstream = (provider_for_model(selected) or "").lower()
        if upstream and upstream not in self.allowed_upstream_providers:
            raise LLMUnavailableError("LLM model is not on the approved allowlist")
        return selected

    def assert_privacy_for_health(self, *, personal_health: bool) -> None:
        if personal_health and self.require_zdr and not self.zdr_configured:
            self.log_privacy(model=None, approved=False, personal_health=True)
            raise LLMUnavailableError("Personal health LLM requires a ZDR-capable endpoint")

    def upstream_only(self, model_id: str) -> list[str]:
        slug = _UPSTREAM_SLUGS.get((provider_for_model(model_id) or "").lower())
        return [slug] if slug else []

    def provider_preferences(self, model_id: str, *, personal_health: bool, require_parameters: bool = False) -> dict:
        self.assert_gateway()
        self.assert_model(model_id)
        self.assert_privacy_for_health(personal_health=personal_health)
        prefs: dict = {"allow_fallbacks": False}
        only = self.upstream_only(model_id)
        if only:
            prefs["only"] = only
        if self.deny_data_collection:
            prefs["data_collection"] = "deny"
        if personal_health and self.require_zdr and self.zdr_configured:
            prefs["zdr"] = True
        elif self.zdr_configured and personal_health:
            prefs["zdr"] = True
        if require_parameters:
            prefs["require_parameters"] = True
        self.log_privacy(model=model_id, approved=True, personal_health=personal_health)
        return prefs

    def log_privacy(self, *, model: str | None, approved: bool, personal_health: bool) -> None:
        logger.info(
            "OPENROUTER_PRIVACY_POLICY zdr_required=%s zdr_enabled=%s data_collection_denied=%s "
            "provider_approved=%s personal_health=%s model=%s",
            self.require_zdr and personal_health,
            self.zdr_configured,
            self.deny_data_collection,
            approved,
            personal_health,
            (model or "")[:80],
        )
        trace(
            "OPENROUTER POLICY",
            model_approved=approved,
            provider_approved=approved,
            zdr_enabled=self.zdr_configured if personal_health and self.require_zdr else False,
            data_collection_denied=self.deny_data_collection,
        )


def openrouter_policy() -> OpenRouterPolicy:
    return OpenRouterPolicy.load()


def approved_model_for_tier(tier: str | None) -> str:
    policy = openrouter_policy()
    selected = model_id_for_tier(tier) if tier else settings.active_llm_model()
    return policy.assert_model(selected)
