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


# Above this complexity a DEEP question is not answered by a smaller model on failure:
# a temporary-service message is more honest than a weaker answer presented as equivalent.
DEEP_FALLBACK_MAX_SCORE = 8
# At or below this a STANDARD question is straightforward enough for the FAST model.
STANDARD_TO_FAST_MAX_SCORE = 4


def fallback_tiers(tier: AnswerModelTier | str | None, complexity_score: int | None = None) -> list[AnswerModelTier]:
    """Tiers to try, in order, when a model is unavailable (one call each, one shared budget).

    FAST      -> STANDARD (a stronger model is always safe)
    STANDARD  -> FAST for straightforward questions, otherwise DEEP
    DEEP      -> STANDARD only while the question is still answerable by it; otherwise none
    During a configured spend spike DEEP tries STANDARD first and keeps DEEP as the fallback.
    """
    selected = _as_tier(tier)
    if selected is None or selected == AnswerModelTier.deterministic:
        return []
    return _distinct_models(_fallback_order(selected, complexity_score))


def _distinct_models(tiers: list[AnswerModelTier]) -> list[AnswerModelTier]:
    """Never retry the same model under another tier name: that repeats the failed call."""
    seen: set[str] = set()
    out: list[AnswerModelTier] = []
    for item in tiers:
        model = model_id_for_tier(item)
        if model in seen:
            continue
        seen.add(model)
        out.append(item)
    return out


def _fallback_order(selected: AnswerModelTier, complexity_score: int | None) -> list[AnswerModelTier]:
    score = complexity_score if complexity_score is not None else 5
    if selected == AnswerModelTier.fast_reasoning:
        return [AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical]
    if selected == AnswerModelTier.standard_medical:
        if score <= STANDARD_TO_FAST_MAX_SCORE:
            return [AnswerModelTier.standard_medical, AnswerModelTier.fast_reasoning]
        return [AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning]
    if _spend_spike():
        return [AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning]
    if score <= DEEP_FALLBACK_MAX_SCORE:
        return [AnswerModelTier.deep_medical_reasoning, AnswerModelTier.standard_medical]
    return [AnswerModelTier.deep_medical_reasoning]


def answer_timeout_for_tier(tier: AnswerModelTier | str | None) -> float:
    selected = _as_tier(tier)
    return {
        AnswerModelTier.fast_reasoning: settings.answer_timeout_fast_seconds,
        AnswerModelTier.standard_medical: settings.answer_timeout_standard_seconds,
        AnswerModelTier.deep_medical_reasoning: settings.answer_timeout_deep_seconds,
    }.get(selected, settings.answer_timeout_standard_seconds)


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
    return selected in {AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning}


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
