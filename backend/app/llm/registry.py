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
    return {
        settings.answer_model_fast_reasoning: ModelPrice(
            settings.model_price_fast_reasoning_input_per_1m,
            settings.model_price_fast_reasoning_output_per_1m,
        ),
        settings.answer_model_standard_medical: ModelPrice(
            settings.model_price_standard_medical_input_per_1m,
            settings.model_price_standard_medical_output_per_1m,
        ),
        settings.answer_model_deep_medical: ModelPrice(
            settings.model_price_deep_medical_input_per_1m,
            settings.model_price_deep_medical_output_per_1m,
        ),
    }


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    price = model_pricing().get(model_id)
    if price is None:
        return None
    cost = (input_tokens / 1_000_000) * price.input_per_1m + (output_tokens / 1_000_000) * price.output_per_1m
    return round(cost, 8)


def fallback_tiers(tier: AnswerModelTier | str | None) -> list[AnswerModelTier]:
    """Upgrade-only availability fallback. Deep never silently drops."""
    selected = _as_tier(tier)
    if selected is None or selected in {AnswerModelTier.deterministic, AnswerModelTier.fast_reasoning}:
        return []
    if selected == AnswerModelTier.standard_medical:
        return [AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning]
    return [AnswerModelTier.deep_medical_reasoning]


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
