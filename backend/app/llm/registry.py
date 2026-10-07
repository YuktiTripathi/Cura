"""Central answer-model registry. Routing chooses a tier; this module maps it to a model ID."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.common import AnswerModelTier, parse_model_tier
from app.core.config import settings


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: float
    output_per_1m: float


def model_registry() -> dict[str, str]:
    return {
        AnswerModelTier.fast_reasoning.value: settings.answer_model_fast_reasoning,
        AnswerModelTier.standard_medical.value: settings.answer_model_standard_medical,
        AnswerModelTier.deep_medical_reasoning.value: settings.answer_model_deep_medical,
    }


def model_id_for_tier(tier: AnswerModelTier | str | None) -> str:
    parsed = parse_model_tier(tier) if not isinstance(tier, AnswerModelTier) else tier
    if parsed is None or parsed == AnswerModelTier.deterministic:
        return ""
    registry = model_registry()
    return registry.get(parsed.value) or settings.answer_model_standard_medical


def model_pricing() -> dict[str, ModelPrice]:
    """Price per model id. When two tiers share a model, the cheaper tier's price wins:
    a model has one price, and the deep tier's default prices assume a different model."""
    tiers = (
        (settings.answer_model_fast_reasoning, settings.model_price_fast_reasoning_input_per_1m, settings.model_price_fast_reasoning_output_per_1m),
        (settings.answer_model_standard_medical, settings.model_price_standard_medical_input_per_1m, settings.model_price_standard_medical_output_per_1m),
        (settings.answer_model_deep_medical, settings.model_price_deep_medical_input_per_1m, settings.model_price_deep_medical_output_per_1m),
    )
    prices: dict[str, ModelPrice] = {}
    for model, input_price, output_price in tiers:
        prices.setdefault(model, ModelPrice(input_price, output_price))
    return prices


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    price = model_pricing().get(model_id)
    if price is None:
        return None
    cost = (input_tokens / 1_000_000) * price.input_per_1m + (output_tokens / 1_000_000) * price.output_per_1m
    return round(cost, 8)


def fallback_tiers(tier: AnswerModelTier | str | None) -> list[AnswerModelTier]:
    """Upgrade-only availability fallback. Deep never drops, except during a configured
    spend spike, when it tries standard first and keeps deep as the fallback (plan 6.7)."""
    selected = _as_tier(tier)
    if selected is None or selected in {AnswerModelTier.deterministic, AnswerModelTier.fast_reasoning}:
        return []
    if selected == AnswerModelTier.standard_medical:
        return [AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning]
    if _spend_spike():
        # Spend spike (plan 6.7): try standard first; deep stays as the fallback.
        return [AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning]
    return [AnswerModelTier.deep_medical_reasoning]


def _spend_spike() -> bool:
    if settings.answer_model_deep_medical == settings.answer_model_standard_medical:
        return False
    from app.core.request_controls import request_controls

    active = request_controls.spend_spike_active()
    if active:
        from app.core.metrics import SPEND_SPIKE

        SPEND_SPIKE.inc()
    return active


def uses_answer_llm(tier: AnswerModelTier | str | None) -> bool:
    selected = _as_tier(tier)
    return selected in {AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning}


def provider_for_model(model_id: str | None) -> str | None:
    raw = (model_id or "").lower()
    if raw.startswith("openai/") or "gpt-" in raw or "luna" in raw:
        return "openai"
    if raw.startswith("google/") or "gemini" in raw:
        return "google"
    if raw.startswith("anthropic/") or "claude" in raw:
        return "anthropic"
    if raw.startswith("typesafe/") or "jev" in raw:
        return "typesafe"
    return "openrouter" if raw else None


def _as_tier(tier: AnswerModelTier | str | None) -> AnswerModelTier | None:
    if isinstance(tier, AnswerModelTier):
        return tier
    return parse_model_tier(tier)
