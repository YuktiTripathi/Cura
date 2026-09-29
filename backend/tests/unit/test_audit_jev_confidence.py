from app.contracts.common import IntentType
from app.core.errors import LLMUnavailableError
from app.pipeline.claim_check import ClaimVerdict, classify_claim
from app.routing.jev_client import JevDecisionsClient
from app.routing.jev_router import JEV_MIN_CONFIDENCE, resolve_plan
from app.routing.schemas import (
    JevDecision,
    JevDecisionsResponse,
    JevIntent,
    JevOperation,
    JevSource,
    JevTimeRange,
)


def _decision(**updates) -> JevDecision:
    values = {
        "intent": JevIntent.lab_result_lookup,
        "source": JevSource.lab_results,
        "operation": JevOperation.lookup,
        "requires_personal_data": True,
        "time_range": JevTimeRange.latest,
        "requested_metrics": ["hba1c"],
        "confidence": 0.91,
    }
    values.update(updates)
    return JevDecision(**values)


def _response() -> JevDecisionsResponse:
    return JevDecisionsResponse(answers={}, model="jev-test")


def test_confidence_threshold_is_not_fabricated():
    assert JEV_MIN_CONFIDENCE == 0.80


def test_low_confidence_falls_back(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_decision(confidence=0.42), _response()),
    )
    plan, trace = resolve_plan("What is my HbA1c?")
    assert trace.fallback
    assert trace.fallback_reason == "low_confidence"
    assert plan.fallback_reason == "low_confidence"
    assert plan.intent == IntentType.latest_result
    assert plan.needs_supershyft


def test_missing_confidence_falls_back(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_decision(confidence=None), _response()),
    )
    plan, trace = resolve_plan("What is my HbA1c?")
    assert trace.fallback
    assert trace.fallback_reason == "confidence_unavailable"


def test_high_confidence_is_accepted(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_decision(confidence=0.92, requested_metrics=["hba1c"]), _response()),
    )
    plan, trace = resolve_plan("What is my HbA1c?")
    assert not trace.fallback
    assert trace.overridden is False
    assert plan.intent == IntentType.latest_result
    assert plan.topic == "hba1c"


def test_unavailable_jev_falls_back(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_ for _ in ()).throw(LLMUnavailableError("down")),
    )
    plan, trace = resolve_plan("What is my HbA1c?")
    assert trace.fallback
    assert plan.intent == IntentType.latest_result


def test_pcod_risk_high_confidence_jev_lookup_is_not_overridden(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (
            _decision(
                confidence=0.94,
                requested_metrics=[],
            ),
            _response(),
        ),
    )
    plan, trace = resolve_plan("Tell me my risk score for PCOD?")
    assert not trace.fallback
    assert trace.overridden is False
    assert plan.intent == IntentType.latest_result
    assert plan.needs_blood
    assert not plan.needs_bio_ai
    assert plan.topic == "pcos"


def test_pcod_risk_jev_bio_ai_lookup_is_accepted(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (
            _decision(
                intent=JevIntent.bio_ai_report_lookup,
                source=JevSource.bio_ai_report,
                operation=JevOperation.lookup,
                requires_personal_data=True,
                time_range=JevTimeRange.latest,
                requested_metrics=[],
                confidence=0.94,
            ),
            _response(),
        ),
    )
    plan, trace = resolve_plan("Tell me my risk score for PCOD?")
    assert not trace.fallback
    assert plan.intent == IntentType.bio_ai_score
    assert plan.needs_bio_ai
    assert not plan.needs_blood
    assert plan.topic == "pcos"


def test_claim_check_does_not_rubber_stamp():
    evidence = "High TSH can have several meanings and needs clinical context."
    assert classify_claim("High TSH can have several meanings and needs clinical context.", evidence) in {
        ClaimVerdict.SUPPORTED,
        ClaimVerdict.PARTIALLY_SUPPORTED,
        ClaimVerdict.CONTEXT_DEPENDENT,
    }
    assert classify_claim("TSH always cures thyroid cancer immediately.", evidence) in {
        ClaimVerdict.UNSUPPORTED,
        ClaimVerdict.CONTRADICTED,
    }
