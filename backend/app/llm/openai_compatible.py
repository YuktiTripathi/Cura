import logging
import re
import time

import json

import httpx

from app.core import perf

from app.core.circuit_breaker import CircuitOpenError, openrouter_breaker
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.core.http import get_http_client
from app.llm.models import LLMStructuredOutput
from app.llm.structured import parse_llm_structured

# Errors a different response_format can fix. Everything else (timeouts, provider errors,
# truncation) would only repeat the same wait, so it is raised straight away.
_FORMAT_ERRORS = {"LLM request format was rejected", "Unexpected LLM response", "LLM returned an empty answer"}

logger = logging.getLogger("cura.llm")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_REASONING_MODEL_RE = re.compile(r"(gpt-5|o1|o3|o4|gemini-3)", re.I)
_ANSWER_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "cura_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "answer": {"type": "string"},
                "summary": {"type": "string"},
                "blocks": {"type": "array", "items": {"type": "object"}},
                "claims": {"type": "array", "items": {"type": "object"}},
                "recommendation_candidates": {"type": "array"},
                "follow_up_questions": {"type": "array", "items": {"type": "string"}},
                "safety_flags": {"type": "array", "items": {"type": "string"}},
                "escalation": {"type": ["string", "null"]},
            },
            "required": ["answer"],
        },
    },
}


def strip_reasoning(text: str) -> str:
    cleaned = _THINK_RE.sub("", text or "")
    return cleaned.strip()


def uses_reasoning_tokens(model: str | None) -> bool:
    return bool(_REASONING_MODEL_RE.search(model or ""))


def message_text(message: dict | None) -> str:
    """Visible assistant text only. Reasoning/thinking is not user-facing."""
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if text and part.get("type") in {None, "text", "output_text"}:
                    parts.append(str(text))
        content = "\n".join(parts)
    return strip_reasoning(str(content or ""))


def _provider_error_detail(response) -> str:
    try:
        data = response.json()
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    err = data.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or "")[:180]
    if isinstance(err, str):
        return err[:180]
    return ""


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        provider: str | None = None,
        timeout: float | int | None = None,
        personal_health: bool = False,
    ) -> None:
        self.provider = provider or settings.resolved_llm_provider()
        self.base_url = (base_url or settings.active_llm_base_url()).rstrip("/")
        self.model = model or settings.active_llm_model()
        self.api_key = api_key if api_key is not None else settings.active_llm_api_key()
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.personal_health = personal_health
        self.last_usage: dict[str, int] = {}
        self.last_finish_reason: str = ""
        self._deadline: float | None = None

    def _remaining(self) -> float:
        if self._deadline is None:
            return self.timeout
        left = self._deadline - time.perf_counter()
        # A fresh budget passes the configured timeout unchanged.
        return self.timeout if left >= float(self.timeout) - 0.05 else left

    def complete(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        if not self.api_key:
            raise LLMUnavailableError("OPENROUTER_API_KEY is not configured")
        from app.llm.openrouter_policy import openrouter_policy
        from app.pipeline.model_safe_context import guard_outgoing_messages

        policy = openrouter_policy()
        if self.personal_health:
            policy.assert_model(self.model)
            policy.assert_privacy_for_health(personal_health=True)
        if policy.dlp_enabled:
            messages = guard_outgoing_messages(messages)
        try:
            openrouter_breaker.allow()
        except CircuitOpenError as exc:
            raise LLMUnavailableError("LLM provider is temporarily unavailable") from exc
        formats = self._format_fallbacks(json_mode)
        last_error: LLMUnavailableError | None = None
        own_deadline = self._deadline is None
        if own_deadline:
            # One wall-clock budget for every attempt of this call (formats, HTTP retries,
            # repair): the tier timeout is the most this answer may take, not per attempt.
            self._deadline = time.perf_counter() + float(self.timeout)
        try:
            for index, fmt in enumerate(formats):
                try:
                    return self._post_once(messages, fmt)
                except LLMUnavailableError as exc:
                    last_error = exc
                    # Another output format only helps when the format was the problem.
                    # Timeouts, provider errors and truncation would just repeat the wait.
                    if index + 1 >= len(formats) or str(exc) not in _FORMAT_ERRORS:
                        raise
                    perf.count("retry_count")
                    logger.warning(
                        "llm_format_fallback model=%s from=%s reason=%s",
                        self.model,
                        fmt,
                        str(exc),
                    )
            raise last_error or LLMUnavailableError("LLM request failed")
        finally:
            if own_deadline:
                self._deadline = None

    def _format_fallbacks(self, json_mode: bool) -> list[str]:
        formats: list[str] = []
        if json_mode:
            if settings.llm_json_schema_output:
                formats.append("json_schema")
            formats.append("json_object")
        formats.append("plain")
        return list(dict.fromkeys(formats))

    def _build_payload(self, messages: list[dict[str, str]], fmt: str) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": settings.llm_max_output_tokens,
        }
        if uses_reasoning_tokens(self.model):
            # Hidden reasoning is billed as output: keep effort low and the cap explicit.
            payload["reasoning"] = {"effort": settings.llm_reasoning_effort or "low"}
            payload["max_tokens"] = max(int(settings.llm_max_output_tokens), int(settings.llm_reasoning_output_cap))
        from app.llm.openrouter_policy import openrouter_policy

        policy = openrouter_policy()
        provider_prefs: dict = {"allow_fallbacks": False}
        only = policy.upstream_only(self.model)
        if only:
            provider_prefs["only"] = only
        if policy.deny_data_collection or settings.openrouter_data_collection_deny:
            provider_prefs["data_collection"] = "deny"
        if self.personal_health and policy.require_zdr and policy.zdr_configured:
            provider_prefs["zdr"] = True
        elif settings.openrouter_zero_data_retention:
            provider_prefs["zdr"] = True
        if fmt == "json_schema":
            payload["temperature"] = 0
            payload["response_format"] = dict(_ANSWER_SCHEMA)
            if settings.openrouter_require_parameters:
                provider_prefs["require_parameters"] = True
        elif fmt == "json_object":
            payload["temperature"] = 0
            payload["response_format"] = {"type": "json_object"}
        if provider_prefs:
            payload["provider"] = provider_prefs
        return payload

    def _post_once(self, messages: list[dict[str, str]], fmt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if settings.openrouter_http_referer:
            headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title:
            headers["X-Title"] = settings.openrouter_app_title
        payload = self._build_payload(messages, fmt)
        from app.llm import prompt_inspector

        audit = prompt_inspector.before_call(payload, fmt)  # dev-only; None otherwise
        try:
            text = self._send(url, headers, payload, fmt)
        except LLMUnavailableError as exc:
            prompt_inspector.after_call(audit, self.last_usage, error=str(exc))
            raise
        prompt_inspector.after_call(audit, self.last_usage)
        return text

    def _send(self, url: str, headers: dict, payload: dict, fmt: str) -> str:
        response = None
        attempts = max(1, int(settings.llm_max_retries) + 1)
        client = get_http_client()
        started = time.perf_counter()
        for attempt in range(attempts):
            timeout = self._remaining()
            if timeout < 0.5:
                openrouter_breaker.record_failure()
                raise LLMUnavailableError("LLM time budget exhausted")
            if attempt:
                perf.count("retry_count")
            perf.count("provider_attempts")
            try:
                response = client.post(url, headers=headers, json=payload, timeout=timeout)
            except httpx.HTTPError as exc:
                if attempt + 1 >= attempts:
                    openrouter_breaker.record_failure()
                    raise LLMUnavailableError("LLM request failed") from exc
                time.sleep(0.1 * (attempt + 1))
                continue
            if response.status_code < 400:
                break
            if response.status_code == 400:
                logger.warning(
                    "llm_http_error status=400 model=%s format=%s detail=%s",
                    self.model,
                    fmt,
                    _provider_error_detail(response),
                )
                raise LLMUnavailableError("LLM request format was rejected")
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt + 1 >= attempts:
                openrouter_breaker.record_failure()
                raise LLMUnavailableError("LLM provider returned an error")
            time.sleep(0.1 * (attempt + 1))
        if response is None:
            openrouter_breaker.record_failure()
            raise LLMUnavailableError("LLM request failed")
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMUnavailableError("Unexpected LLM response") from exc
        usage = data.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        cached = details.get("cached_tokens")
        self.last_usage = {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "cached_tokens": int(cached or 0),
            "reasoning_tokens": int(completion_details.get("reasoning_tokens") or usage.get("reasoning_tokens") or 0),
            "usage_reported": bool(usage),
        }
        perf.count("prompt_tokens", self.last_usage["input_tokens"])
        perf.count("completion_tokens", self.last_usage["output_tokens"])
        try:
            message = data["choices"][0]["message"]
            finish_reason = data["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError("Unexpected LLM response") from exc
        self.last_finish_reason = str(finish_reason or "")
        cleaned = message_text(message)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if str(finish_reason or "") in {"length", "max_tokens"}:
            logger.warning("llm_truncated model=%s format=%s latency_ms=%s", self.model, fmt, latency_ms)
            raise LLMUnavailableError("LLM output was truncated")
        if not cleaned:
            logger.warning(
                "llm_empty_content model=%s format=%s latency_ms=%s completion_tokens=%s",
                self.model,
                fmt,
                latency_ms,
                self.last_usage.get("output_tokens"),
            )
            raise LLMUnavailableError("LLM returned an empty answer")
        openrouter_breaker.record_success()
        logger.info("llm_complete model=%s format=%s latency_ms=%s", self.model, fmt, latency_ms)
        return cleaned

    def _complete_with_mode(self, messages: list[dict[str, str]], json_mode: bool) -> str:
        try:
            return self.complete(messages, json_mode=json_mode)
        except TypeError:
            return self.complete(messages)

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMStructuredOutput:
        from app.llm.answer_cache import answer_cache_get, answer_cache_put

        cached = answer_cache_get(messages, self.model) if settings.answer_cache_enabled else None
        if cached is not None:
            perf.mark("cache_hit", True)
            # Identical prompt (same data, question and context): no tokens spent.
            self.last_usage = {}
            self.last_finish_reason = cached.finish_reason or ""
            return cached
        perf.count("llm_calls")
        self._deadline = time.perf_counter() + float(self.timeout)
        try:
            with perf.stage("llm"):
                result = self._complete_structured_uncached(messages)
        finally:
            self._deadline = None
        if settings.answer_cache_enabled:
            answer_cache_put(messages, self.model, result)
        return result

    def _complete_structured_uncached(self, messages: list[dict[str, str]]) -> LLMStructuredOutput:
        want_schema = bool(settings.llm_json_schema_output or settings.assistant_quality_v2)
        raw = self._complete_with_mode(messages, want_schema)
        parsed = parse_llm_structured(raw)
        if parsed.parse_error or not parsed.answer.strip():
            repair = list(messages) + [
                {
                    "role": "user",
                    "content": "Your previous output was not valid. Return only the JSON object with a string 'answer' field.",
                }
            ]
            perf.count("retry_count")
            try:
                raw = self._complete_with_mode(repair, True)
                parsed = parse_llm_structured(raw)
            except LLMUnavailableError:
                raise
        if parsed.parse_error:
            logger.error(
                "llm_structured_output_contract_violation parse_error=%s answer_preview=%s",
                parsed.parse_error,
                (parsed.answer or "")[:120],
            )
        if not parsed.answer.strip():
            raise LLMUnavailableError("LLM returned an empty answer")
        parsed.finish_reason = self.last_finish_reason or None
        parsed.truncated = self.last_finish_reason in {"length", "max_tokens"}
        return parsed

    def stream_text(self, messages: list[dict[str, str]], on_token) -> str:
        """Stream a plain-text answer token by token (readiness plan 5.4).

        Used only for low-risk general answers. The caller still runs every grounding and
        safety check on the full text, and the client replaces the streamed draft with the
        checked answer.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if settings.openrouter_app_title:
            headers["X-Title"] = settings.openrouter_app_title
        payload = self._build_payload(messages, "text")
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        parts: list[str] = []
        usage: dict = {}
        try:
            with get_http_client().stream("POST", url, headers=headers, json=payload, timeout=self.timeout) as response:
                if response.status_code >= 400:
                    openrouter_breaker.record_failure()
                    raise LLMUnavailableError("LLM provider returned an error")
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        continue
                    usage = chunk.get("usage") or usage
                    for choice in chunk.get("choices") or []:
                        reason = choice.get("finish_reason")
                        if reason:
                            self.last_finish_reason = str(reason)
                        delta = (choice.get("delta") or {}).get("content") or ""
                        if delta:
                            parts.append(delta)
                            on_token(delta)
        except httpx.HTTPError as exc:
            openrouter_breaker.record_failure()
            raise LLMUnavailableError("LLM stream failed") from exc
        self.last_usage = {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
            "cached_tokens": int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
            "usage_reported": bool(usage),
        }
        text = strip_reasoning("".join(parts))
        if self.last_finish_reason in {"length", "max_tokens"}:
            logger.warning("llm_stream_truncated model=%s finish_reason=%s", self.model, self.last_finish_reason)
            raise LLMUnavailableError("LLM output was truncated")
        if not text:
            raise LLMUnavailableError("LLM returned an empty answer")
        openrouter_breaker.record_success()
        return text

    def stream(self, messages: list[dict[str, str]]):
        yield self.complete_structured(messages).answer
