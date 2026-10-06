from app.core.circuit_breaker import jev_breaker, openrouter_breaker, supershyft_breaker
from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.providers.registry import set_registry
from integrations.supershyft.db import reset_engine

settings.health_provider = "mock"
settings.allow_mock_auth_with_real_health = True
settings.mock_user_id = ""
settings.allow_mock_header_override = False
settings.enable_llm = False
settings.llm_provider = "openrouter"
settings.jev_enabled = False
settings.supershyft_database_url = ""
settings.voice_enabled = False
settings.stt_provider = "none"
settings.rate_limit_requests = 10000
jev_breaker.reset()
openrouter_breaker.reset()
supershyft_breaker.reset()
reset_engine()
set_registry(None)
OpenAICompatibleLLMClient._real_complete = OpenAICompatibleLLMClient.complete


def _test_llm_complete(self, messages, json_mode=False):
    user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    # The question is the last line of the prompt (prompt caching layout).
    question = next((line for line in reversed(user.splitlines()) if line.startswith("User question:")), "")
    return (
        "This is general medical education, not a personal lab result. "
        "HbA1c LDL HDL TSH Vitamin D B12 CRP insulin resistance metabolic age. "
        + question
        + " "
        + user[:240]
    )


OpenAICompatibleLLMClient.complete = _test_llm_complete
