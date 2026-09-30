from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.registry import model_id_for_tier, model_registry


def _allowed_models() -> set[str]:
    configured = {item.strip() for item in (settings.llm_allowed_models or "").split(",") if item.strip()}
    configured.update(model_registry().values())
    configured.add(settings.jev_model)
    configured.add(settings.active_llm_model())
    if (settings.eval_candidate_model or "").strip():
        configured.add(settings.eval_candidate_model.strip())
    return configured


def _allowed_providers() -> set[str]:
    return {item.strip().lower() for item in (settings.llm_allowed_providers or "openrouter").split(",") if item.strip()}


def assert_model_allowed(model_id: str) -> str:
    provider = settings.resolved_llm_provider()
    if provider not in _allowed_providers():
        raise LLMUnavailableError("LLM provider is not on the approved allowlist")
    selected = (model_id or "").strip()
    allowed = _allowed_models()
    if selected not in allowed:
        raise LLMUnavailableError("LLM model is not on the approved allowlist")
    return selected


def get_llm_client(
    model_tier: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
) -> OpenAICompatibleLLMClient:
    selected = model or (model_id_for_tier(model_tier) if model_tier else settings.active_llm_model())
    if not (selected or "").strip():
        raise LLMUnavailableError("No answer model is configured for this routing tier")
    selected = assert_model_allowed(selected)
    return OpenAICompatibleLLMClient(
        provider=settings.resolved_llm_provider(),
        base_url=settings.active_llm_base_url(),
        model=selected,
        api_key=settings.active_llm_api_key(),
        timeout=timeout if timeout is not None else settings.llm_timeout_seconds,
    )
