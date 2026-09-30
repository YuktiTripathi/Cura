"""Replaceable multilingual safety classifier. Deterministic rules always win on high confidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SafetyClassification:
    category: str
    severity: str
    confidence: float
    language: str
    action: str  # allow | urgent | refuse | safe_redirect


class SafetyClassifier(Protocol):
    def classify(self, text: str) -> SafetyClassification: ...


class HeuristicMultilingualClassifier:
    """Pattern helper used after deterministic high-confidence rules.

    A later model-backed classifier can replace this class without changing SafetyLayer.
    """

    def classify(self, text: str) -> SafetyClassification:
        from app.pipeline.safety import detect_language_hint, match_safety_category

        category, language, confidence = match_safety_category(text)
        action = {
            "emergency": "urgent",
            "self_harm": "safe_redirect",
            "medication_misuse": "refuse",
            "prompt_injection": "refuse",
            "diagnosis_request": "refuse",
            "out_of_scope": "refuse",
        }.get(category, "allow")
        severity = "high" if action in {"urgent", "safe_redirect"} else "medium" if action == "refuse" else "low"
        return SafetyClassification(
            category=category or "none",
            severity=severity,
            confidence=confidence,
            language=language or detect_language_hint(text),
            action=action,
        )
