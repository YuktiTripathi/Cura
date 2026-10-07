"""Optional model judge for medication and diagnosis claims (readiness plan 2.7).

Runs after the rule-based review, only on answers that mention a medicine or a
diagnosis. A small fast model with schema-constrained output decides whether the answer
tells the member to start, stop, change or dose a medicine, or states a diagnosis. If it
does, the answer is replaced with the safe fallback. Sends only the answer text, under
the same OpenRouter allowlist and zero-retention policy as answer calls.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger("cura.safety")

_TRIGGER = re.compile(
    r"\b(mg|mcg|dose|dosage|tablet|tablets|medicine|medication|insulin|metformin|statin|"
    r"diagnos\w*|you have|you are suffering|prescri\w*|stop taking|start taking)\b",
    re.I,
)

_PROMPT = (
    "You review answers from a health education assistant before a member sees them. The assistant "
    "may explain results and general information, but must never: tell the member to start, stop, skip, "
    "switch, combine or change the dose of a medicine; give a specific dose; or state that the member has "
    "a disease (a diagnosis). Saying a value is above or below a range, or suggesting they discuss it with "
    "a doctor, is allowed. Reply with JSON only: {\"unsafe\": true|false, \"reason\": \"<short>\"}"
)


@dataclass(frozen=True)
class JudgeVerdict:
    unsafe: bool
    reason: str = ""
    available: bool = True


def should_judge(answer: str) -> bool:
    return bool(settings.safety_answer_judge_enabled and settings.enable_llm and _TRIGGER.search(answer or ""))


def judge_answer(answer: str, client: httpx.Client | None = None) -> JudgeVerdict:
    model = settings.safety_classifier_model
    try:
        from app.llm.openrouter_policy import openrouter_policy

        payload = {
            "model": model,
            "messages": [{"role": "system", "content": _PROMPT}, {"role": "user", "content": answer[:6000]}],
            "temperature": 0,
            "max_tokens": 80,
            "provider": openrouter_policy().provider_preferences(model, personal_health=True),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer_verdict",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"unsafe": {"type": "boolean"}, "reason": {"type": "string"}},
                        "required": ["unsafe", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
        }
        own = client is None
        client = client or httpx.Client(timeout=settings.safety_classifier_timeout_seconds)
        try:
            response = client.post(
                f"{settings.active_llm_base_url()}/chat/completions",
                headers={"Authorization": f"Bearer {settings.active_llm_api_key()}", "X-Title": settings.openrouter_app_title},
                json=payload,
                timeout=settings.safety_classifier_timeout_seconds,
            )
        finally:
            if own:
                client.close()
        response.raise_for_status()
        data = json.loads(response.json()["choices"][0]["message"]["content"])
        return JudgeVerdict(unsafe=bool(data.get("unsafe")), reason=str(data.get("reason", ""))[:200])
    except Exception as exc:  # noqa: BLE001 - timeout, policy refusal, bad JSON
        logger.warning("answer_judge status=unavailable error=%s", type(exc).__name__)
        return JudgeVerdict(unsafe=False, available=False)
