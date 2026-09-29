from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleLLMClient


def get_llm_client() -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        provider=settings.resolved_llm_provider(),
        base_url=settings.active_llm_base_url(),
        model=settings.active_llm_model(),
        api_key=settings.active_llm_api_key(),
        timeout=settings.llm_timeout_seconds,
    )
