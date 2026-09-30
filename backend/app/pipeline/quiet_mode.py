"""Stay quiet when nothing meaningful has changed."""

from __future__ import annotations

from app.contracts.health_context import HealthContext
from app.contracts.personalization import LongitudinalClass, QuietDecision

_MEANINGFUL = {
    LongitudinalClass.newly_abnormal,
    LongitudinalClass.persistently_abnormal,
    LongitudinalClass.improved_but_still_abnormal,
    LongitudinalClass.returned_to_range,
    LongitudinalClass.worsened,
}


def decide_quiet(context: HealthContext, message: str = "") -> QuietDecision:
    text = (message or "").lower()
    asked = any(
        token in text
        for token in (
            "change anything",
            "need to change",
            "do i need to change",
            "everything looks stable",
            "nothing new",
        )
    )
    if not asked:
        return QuietDecision(active=False)
    recent = context.personalization.recent_user_context if context.personalization else None
    if recent and (recent.illness or recent.symptoms):
        return QuietDecision(active=False, reason="recent_symptom_or_illness")
    meaningful = [
        item
        for item in context.baselines or []
        if item.classification in _MEANINGFUL or item.latest_flag in {"low", "high", "critical"}
    ]
    if not meaningful:
        return QuietDecision(active=True, reason="no_meaningful_change")
    if asked and not any(item.classification in _MEANINGFUL for item in context.baselines or []):
        return QuietDecision(active=True, reason="stable_no_action")
    return QuietDecision(active=False)
