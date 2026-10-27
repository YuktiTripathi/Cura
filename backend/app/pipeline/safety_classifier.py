"""Replaceable multilingual safety classifiers.

``SafetyLayer`` combines the deterministic rules with one of these. Urgent from either
layer wins. The model-backed classifier sends only the member's message text, under the
same OpenRouter allowlist and zero-retention policy as answer calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger("cura.safety")

CATEGORIES = ("none", "emergency", "self_harm", "medication_misuse", "diagnosis_request", "urgent_soon")


@dataclass(frozen=True)
class SafetyClassification:
    category: str
    severity: str
    confidence: float
    language: str
    action: str  # allow | urgent | refuse | safe_redirect
    degraded: bool = False


class SafetyClassifier(Protocol):
    def classify(self, text: str) -> SafetyClassification: ...


def _action_for(category: str) -> tuple[str, str]:
    action = {
        "emergency": "urgent",
        "self_harm": "safe_redirect",
        "medication_misuse": "refuse",
        "prompt_injection": "refuse",
        "diagnosis_request": "refuse",
        "out_of_scope": "refuse",
        "urgent_soon": "caution",
    }.get(category, "allow")
    severity = "high" if action in {"urgent", "safe_redirect"} else "medium" if action in {"refuse", "caution"} else "low"
    return action, severity


class HeuristicMultilingualClassifier:
    """Rule-only classifier. Used when the model classifier is disabled (dev, tests)."""

    def classify(self, text: str) -> SafetyClassification:
        from app.pipeline.safety import detect_language_hint, match_safety_category

        category, language, confidence = match_safety_category(text)
        action, severity = _action_for(category)
        return SafetyClassification(
            category=category or "none",
            severity=severity,
            confidence=confidence,
            language=language or detect_language_hint(text),
            action=action,
        )


_SYSTEM_PROMPT = (
    "You are a medical triage safety classifier for an Indian health app. Classify ONLY the user's "
    "message. Messages may be in English, Hindi, Marathi, Punjabi, Gujarati, Bengali or romanized "
    "Hinglish, may describe a third person, and may contain misspellings.\n"
    "Categories:\n"
    "- emergency: symptoms needing emergency services now (chest pain or pressure, stroke signs, severe "
    "breathlessness, altered consciousness, seizure, heavy bleeding, bleeding in pregnancy, vomiting blood, "
    "anaphylaxis, poisoning or overdose, very high or low sugar with symptoms, infant fever or lethargy).\n"
    "- self_harm: any direct or indirect thought of suicide, self harm, or not wanting to live.\n"
    "- medication_misuse: asking whether to start, stop, skip, change, double, or combine a medicine, or about a dose. "
    "Asking whether a blood test should be repeated, or whether it should be fasting, is none.\n"
    "- urgent_soon: symptoms that should be seen within a day (fever for several days, blood in urine or stool, "
    "inability to keep fluids down, very high blood pressure with symptoms, jaundice). "
    "An out-of-range lab result, or a question about what a result means, is none.\n"
    "- diagnosis_request: asks to be diagnosed or to be told they have a disease "
    "(\"do I have diabetes\", \"diagnose me\"). Asking what a lab result means is none.\n"
    "- none: anything else, including negated symptoms (\"no chest pain\") and fitness talk (\"chest day\").\n"
    'Reply with JSON only: {"category": "<one of the above>", "confidence": <0..1>}'
)


class LLMSafetyClassifier:
    """Small fast model with schema constrained output. Fails closed to ``degraded``."""

    def __init__(self, model: str | None = None, timeout: float | None = None, client: httpx.Client | None = None):
        self.model = (model or settings.safety_classifier_model).strip()
        self.timeout = float(timeout or settings.safety_classifier_timeout_seconds)
        self._client = client

    def _degraded(self, text: str) -> SafetyClassification:
        fallback = HeuristicMultilingualClassifier().classify(text)
        return SafetyClassification(
            category=fallback.category,
            severity=fallback.severity,
            confidence=fallback.confidence,
            language=fallback.language,
            action=fallback.action,
            degraded=True,
        )

    def _payload(self, text: str) -> dict:
        from app.llm.openrouter_policy import openrouter_policy

        prefs = openrouter_policy().provider_preferences(self.model, personal_health=True)
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text[:2000]},
            ],
            "temperature": 0,
            "max_tokens": 60,
            "provider": prefs,
            "response_format": {"type": "json_object"},
        }

    def classify(self, text: str) -> SafetyClassification:
        api_key = settings.active_llm_api_key()
        if not api_key:
            return self._degraded(text)
        try:
            payload = self._payload(text)
            client = self._client or httpx.Client(timeout=self.timeout)
            try:
                response = client.post(
                    f"{settings.active_llm_base_url()}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "X-Title": settings.openrouter_app_title},
                    json=payload,
                    timeout=self.timeout,
                )
            finally:
                if self._client is None:
                    client.close()
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            category = str(data.get("category", "none"))
            if category not in CATEGORIES:
                category = "none"
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        except Exception as exc:  # noqa: BLE001 - timeout, policy refusal, bad JSON
            logger.warning("safety_classifier status=degraded error=%s", type(exc).__name__)
            return self._degraded(text)
        from app.pipeline.safety_messages import detect_safety_language

        action, severity = _action_for(category)
        return SafetyClassification(
            category=category,
            severity=severity,
            confidence=confidence,
            language=detect_safety_language(text),
            action=action,
        )


def default_classifier() -> SafetyClassifier:
    if settings.safety_llm_classifier_enabled and settings.enable_llm:
        return LLMSafetyClassifier()
    return HeuristicMultilingualClassifier()


def model_safety_classifier_active() -> bool:
    """True when the default classifier calls a model (and is worth running in parallel)."""
    return bool(settings.safety_llm_classifier_enabled and settings.enable_llm)
