import re
import time

import httpx

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.models import LLMStructuredOutput
from app.llm.structured import parse_llm_structured

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    cleaned = _THINK_RE.sub("", text or "")
    return cleaned.strip()


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.provider = provider or settings.resolved_llm_provider()
        self.base_url = (base_url or settings.active_llm_base_url()).rstrip("/")
        self.model = model or settings.active_llm_model()
        self.api_key = api_key if api_key is not None else settings.active_llm_api_key()
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.last_usage: dict[str, int] = {}

    def complete(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        if not self.api_key:
            raise LLMUnavailableError("OPENROUTER_API_KEY is not configured")
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if settings.openrouter_http_referer:
            headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title:
            headers["X-Title"] = settings.openrouter_app_title
        payload: dict = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": settings.llm_max_output_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            payload["temperature"] = 0
        response = None
        attempts = max(1, int(settings.llm_max_retries) + 1)
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                if attempt + 1 >= attempts:
                    raise LLMUnavailableError("LLM request failed") from exc
                time.sleep(0.1 * (attempt + 1))
                continue
            if response.status_code < 400:
                break
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                raise LLMUnavailableError("LLM provider returned an error")
            time.sleep(0.1 * (attempt + 1))
        if response is None:
            raise LLMUnavailableError("LLM request failed")
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMUnavailableError("Unexpected LLM response") from exc
        usage = data.get("usage") or {}
        self.last_usage = {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        }
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError("Unexpected LLM response") from exc
        cleaned = strip_reasoning(str(content))
        if not cleaned:
            raise LLMUnavailableError("LLM returned an empty answer")
        return cleaned

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMStructuredOutput:
        raw = self.complete(messages)
        parsed = parse_llm_structured(raw)
        if not parsed.answer.strip():
            raise LLMUnavailableError("LLM returned an empty answer")
        return parsed

    def stream(self, messages: list[dict[str, str]]):
        yield self.complete_structured(messages).answer
