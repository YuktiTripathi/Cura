from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.openrouter_policy import openrouter_policy
from app.llm.registry import model_id_for_tier


def assert_model_allowed(model_id: str) -> str:
    policy = openrouter_policy()
    policy.assert_gateway()
    return policy.assert_model(model_id)


def get_llm_client(
    model_tier: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    personal_health: bool = False,
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
        personal_health=personal_health,
    )
