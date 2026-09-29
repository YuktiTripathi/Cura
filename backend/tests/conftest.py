from app.core.config import settings
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.providers.registry import set_registry
from integrations.supershyft.db import reset_engine

settings.health_provider = "mock"
settings.enable_llm = False
settings.llm_provider = "openrouter"
settings.jev_enabled = False
settings.supershyft_database_url = ""
settings.voice_enabled = False
settings.stt_provider = "none"
settings.rate_limit_requests = 10000
reset_engine()
set_registry(None)
OpenAICompatibleLLMClient._real_complete = OpenAICompatibleLLMClient.complete


def _test_llm_complete(self, messages, json_mode=False):
    user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    return (
        "This is general medical education, not a personal lab result. "
        "HbA1c LDL HDL TSH Vitamin D B12 CRP insulin resistance metabolic age. "
        + user[:240]
    )


OpenAICompatibleLLMClient.complete = _test_llm_complete
