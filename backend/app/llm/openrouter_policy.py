"""Single OpenRouter production policy. Do not scatter provider restrictions."""

from __future__ import annotations

import logging
import re
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
    deny_data_collection: bool
    prompt_injection_protection: bool
    dlp_enabled: bool
    clinical_safety_enabled: bool
    package_safety_enabled: bool
    request_timeout: float
    max_retries: int
    privacy_profile: str = "not_approved"
    approved_personal_models: frozenset[str] = field(default_factory=frozenset)
    extra_models: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def load(cls) -> "OpenRouterPolicy":
        models = {item.strip() for item in (settings.llm_allowed_models or "").split(",") if item.strip()}
        extra = {item.strip() for item in (settings.cura_openrouter_allowed_models or "").split(",") if item.strip()}
        models.update(extra)
        models.update(model_registry().values())
        models.add(settings.jev_model)
        models.add(settings.active_llm_model())
        if (settings.stt_provider or "").strip().lower() == "openrouter":
            models.add(settings.resolved_stt_model())
        gateway = {item.strip().lower() for item in (settings.llm_allowed_providers or "openrouter").split(",") if item.strip()}
        upstream = {
            item.strip().lower()
            for item in (settings.cura_openrouter_allowed_providers or "openai,google,anthropic,typesafe").split(",")
            if item.strip()
        }
        deny = bool(settings.cura_openrouter_deny_data_collection and settings.openrouter_data_collection_deny)
        profile = (settings.personal_health_privacy_profile or "not_approved").strip().lower()
        approved = {
            item.strip()
            for item in (settings.personal_health_approved_models or "").split(",")
            if item.strip()
        }
        return cls(
            allowed_models=frozenset(models),
            allowed_providers=frozenset(gateway),
            allowed_upstream_providers=frozenset(upstream),
            deny_data_collection=deny,
            prompt_injection_protection=bool(settings.cura_openrouter_prompt_injection_protection),
            dlp_enabled=bool(settings.cura_openrouter_dlp_enabled),
            clinical_safety_enabled=bool(settings.cura_clinical_safety_enabled),
            package_safety_enabled=bool(settings.cura_package_safety_enabled),
            request_timeout=float(settings.llm_timeout_seconds),
            max_retries=int(settings.llm_max_retries),
            privacy_profile=profile,
            approved_personal_models=frozenset(approved),
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
        # "openrouter" here means no vendor slug, not an upstream endpoint.
        if upstream and upstream != "openrouter" and upstream not in self.allowed_upstream_providers:
            raise LLMUnavailableError("LLM model is not on the approved allowlist")
        return selected

    def personal_interpretation_permitted(self, model_id: str | None = None) -> bool:
        """Safety retention is not zero retention. An empty allowlist sends nothing."""
        if self.privacy_profile != "safety_retention" or not self.approved_personal_models:
            return False
        if model_id and model_id not in self.approved_personal_models:
            return False
        return True

    def assert_privacy_for_health(self, *, personal_health: bool, model: str | None = None) -> None:
        if personal_health and not self.personal_interpretation_permitted(model):
            self.log_privacy(model=model, approved=False, personal_health=True)
            raise LLMUnavailableError(
                "Personal health interpretation is not approved for an external provider"
            )

    def upstream_only(self, model_id: str) -> list[str]:
        slug = _UPSTREAM_SLUGS.get((provider_for_model(model_id) or "").lower())
        return [slug] if slug else []

    def provider_preferences(self, model_id: str, *, personal_health: bool, require_parameters: bool = False) -> dict:
        self.assert_gateway()
        self.assert_model(model_id)
        self.assert_privacy_for_health(personal_health=personal_health, model=model_id)
        # Do not pin provider.only to the model vendor. That pin selects endpoints the
        # account privacy policy rejects. allow_fallbacks stays off so the model cannot change.
        prefs: dict = {"allow_fallbacks": False}
        if self.deny_data_collection:
            prefs["data_collection"] = "deny"
        if require_parameters:
            prefs["require_parameters"] = True
        self.log_privacy(model=model_id, approved=True, personal_health=personal_health)
        return prefs

    def log_privacy(self, *, model: str | None, approved: bool, personal_health: bool) -> None:
        logger.info(
            "OPENROUTER_PRIVACY_POLICY profile=%s data_collection_denied=%s "
            "provider_approved=%s personal_health=%s model=%s",
            self.privacy_profile,
            self.deny_data_collection,
            approved,
            personal_health,
            (model or "")[:80],
        )
        trace(
            "OPENROUTER POLICY",
            model_approved=approved,
            provider_approved=approved,
            privacy_profile=self.privacy_profile,
            data_collection_denied=self.deny_data_collection,
        )


_PERSONAL_CLINICAL = re.compile(
    r"\b(?:my|mera|meri|mine)\b.{0,48}\b(?:ldl|hdl|hba1c|tsh|glucose|creatinine|ferritin|cholesterol|triglyceride|lab|report|marker)s?\b"
    r"|\bsource_measurements\b"
    r"|\d+(?:\.\d+)?\s*(?:mg/dl|g/dl|mmol/l|u/l|iu/l)\b"
    r"|\b20\d{2}-\d{2}-\d{2}\b.{0,80}\b(?:stored|glucose|hba1c|cholesterol|iron|creatinine|albumin|bio-?\s*ai)\b"
    r"|\b(?:stored|blood report|bio-?\s*ai)\b.{0,80}\b20\d{2}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)


def messages_contain_personal_clinical(messages: list) -> bool:
    """True when the outbound text itself carries personal clinical content."""
    parts: list[str] = []
    for message in messages or []:
        if isinstance(message, dict):
            parts.append(str(message.get("content") or ""))
    return bool(_PERSONAL_CLINICAL.search(" ".join(parts)))


def openrouter_policy() -> OpenRouterPolicy:
    return OpenRouterPolicy.load()


def approved_model_for_tier(tier: str | None) -> str:
    policy = openrouter_policy()
    selected = model_id_for_tier(tier) if tier else settings.active_llm_model()
    return policy.assert_model(selected)
