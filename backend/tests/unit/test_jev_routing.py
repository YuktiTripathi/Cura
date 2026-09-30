from unittest.mock import MagicMock

import pytest

from app.contracts.common import IntentType, KnowledgeScope
from app.core.errors import LLMUnavailableError
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_client import JevDecisionsClient
from app.routing.jev_router import resolve_plan
from app.routing.mapper import plan_from_jev
from app.routing.schemas import (
    JevDecision,
    JevDecisionsResponse,
    JevIntent,
    JevOperation,
    JevRoutingState,
    JevSource,
    JevTimeRange,
)
from app.routing.validator import JevDecisionValidationError, validate_jev_decision


def _response() -> JevDecisionsResponse:
    return JevDecisionsResponse(
        answers={},
        model="typesafe/jev-1.13-20260917",
        provider="TypeSafe",
        usage={"input_tokens": 100, "output_tokens": 20},
    )


def _decision(**updates) -> JevDecision:
    values = {
        "intent": JevIntent.general_health_question,
        "source": JevSource.none,
        "operation": JevOperation.general_answer,
    }
    values.update(updates)
    return JevDecision(**values)


def test_decisions_endpoint_is_derived_from_existing_openrouter_base():
    client = JevDecisionsClient(base_url="https://openrouter.ai/api/v1", api_key="test")
    assert client.endpoint == "https://openrouter.ai/api/alpha/decisions"


def test_typed_decisions_response_is_normalized(monkeypatch):
    payload = {
        "answers": {
            "request_type": {"type": "choice", "choice": "lab_result_lookup", "confidence": 0.91},
            "data_source": {"type": "choice", "choice": "lab_results", "confidence": 0.94},
            "operation": {"type": "choice", "choice": "lookup", "confidence": 0.93},
            "time_scope": {"type": "choice", "choice": "latest", "confidence": 0.98},
            "requires_personal_data": {"type": "noul", "noul": 0.99},
            "requires_historical_data": {"type": "noul", "noul": 0.02},
            "requires_document": {"type": "noul", "noul": 0.01},
            "requires_clarification": {"type": "noul", "noul": 0.01},
        },
        "model": "typesafe/jev-1.13",
        "provider": "TypeSafe",
        "usage": {"input_tokens": 42, "output_tokens": 8},
    }
    response = MagicMock(status_code=200)
    response.json.return_value = payload
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.post.return_value = response
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: transport)
    decision, parsed = JevDecisionsClient(api_key="test").decide(
        JevRoutingState(current_message="What is my HbA1c?")
    )
    assert decision.intent == JevIntent.lab_result_lookup
    assert decision.requires_personal_data
    assert decision.source == JevSource.lab_results
    assert decision.confidence == 0.91
    assert parsed.usage.input_tokens == 42


def test_parallel_clarification_noul_cannot_override_clear_lookup(monkeypatch):
    payload = {
        "answers": {
            "request_type": {"type": "choice", "choice": "lab_result_lookup", "confidence": 0.99},
            "data_source": {"type": "choice", "choice": "lab_results", "confidence": 0.9},
            "operation": {"type": "choice", "choice": "lookup", "confidence": 0.88},
            "time_scope": {"type": "choice", "choice": "latest", "confidence": 0.95},
            "requires_personal_data": {"type": "noul", "noul": 0.96},
            "requires_historical_data": {"type": "noul", "noul": 0.1},
            "requires_document": {"type": "noul", "noul": 0.1},
            "requires_clarification": {"type": "noul", "noul": 0.81},
        }
    }
    response = MagicMock(status_code=200)
    response.json.return_value = payload
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.post.return_value = response
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: transport)
    decision, _ = JevDecisionsClient(api_key="test").decide(
        JevRoutingState(current_message="What is my LDL?")
    )
    assert decision.intent == JevIntent.lab_result_lookup
    assert decision.requires_clarification is False
    plan = plan_from_jev(decision, "What is my LDL?")
    assert plan.intent == IntentType.latest_result
    assert plan.needs_supershyft


def test_malformed_decisions_response_fails_closed(monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {"answers": {"request_type": {"type": "choice"}}}
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.post.return_value = response
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: transport)
    with pytest.raises(LLMUnavailableError):
        JevDecisionsClient(api_key="test").decide(
            JevRoutingState(current_message="What is insulin resistance?")
        )


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (_decision(), IntentType.general_health_question),
        (
            _decision(
                intent=JevIntent.lab_result_lookup,
                source=JevSource.lab_results,
                operation=JevOperation.lookup,
                requires_personal_data=True,
                time_range=JevTimeRange.latest,
                requested_metrics=["hba1c"],
            ),
            IntentType.latest_result,
        ),
        (
            _decision(
                intent=JevIntent.lab_result_interpretation,
                source=JevSource.lab_results,
                operation=JevOperation.interpret,
                requires_personal_data=True,
                time_range=JevTimeRange.latest,
                requested_metrics=["ldl"],
            ),
            IntentType.blood_marker_explanation,
        ),
        (
            _decision(
                intent=JevIntent.health_trend_analysis,
                source=JevSource.blood_reports,
                operation=JevOperation.trend,
                requires_personal_data=True,
                requires_historical_data=True,
                time_range=JevTimeRange.six_months,
                requested_metrics=["cholesterol"],
            ),
            IntentType.trend,
        ),
        (
            _decision(
                intent=JevIntent.bio_ai_report_interpretation,
                source=JevSource.bio_ai_report,
                operation=JevOperation.retrieve_and_explain,
                requires_personal_data=True,
                time_range=JevTimeRange.latest,
            ),
            IntentType.bio_ai_explanation,
        ),
    ],
)
def test_validated_decisions_map_to_existing_query_plan(decision, expected):
    plan = plan_from_jev(decision, "test")
    assert plan.intent == expected
    assert isinstance(plan.knowledge_scope, KnowledgeScope)


def test_general_false_positive_is_rejected():
    state = JevRoutingState(current_message="What lifestyle changes can lower my LDL?")
    bad = _decision(
        intent=JevIntent.lab_result_interpretation,
        source=JevSource.lab_results,
        operation=JevOperation.interpret,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
    )
    with pytest.raises(JevDecisionValidationError):
        validate_jev_decision(bad, state, deterministic_requires_personal=False)


def test_unsupported_questionnaire_becomes_clarification():
    state = JevRoutingState(current_message="Show my questionnaire", supported_capabilities=[])
    result = validate_jev_decision(
        _decision(
            intent=JevIntent.questionnaire_lookup,
            source=JevSource.questionnaire,
            operation=JevOperation.lookup,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        ),
        state,
        deterministic_requires_personal=True,
    )
    assert result.requires_clarification
    assert "not available" in (result.clarification_question or "")


def test_jev_disabled_uses_deterministic(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", False)
    plan, trace = resolve_plan("What is my HbA1c?")
    assert not trace.called
    assert plan.intent == IntentType.latest_result
    assert plan.needs_supershyft


def test_jev_timeout_falls_back_safely(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_ for _ in ()).throw(LLMUnavailableError("timeout")),
    )
    plan, trace = resolve_plan("What is insulin resistance?")
    assert trace.fallback
    assert not plan.needs_personal_data


def test_invalid_personal_decision_falls_back_to_personal_deterministic_plan(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(
        JevDecisionsClient,
        "decide",
        lambda *_: (_decision(), _response()),
    )
    plan, trace = resolve_plan("What is my HbA1c?")
    assert trace.fallback
    assert trace.validation_error
    assert plan.needs_supershyft


def test_clarification_plan_does_not_query_supershyft():
    plan = plan_from_jev(
        _decision(
            intent=JevIntent.clarification,
            source=JevSource.none,
            operation=JevOperation.clarify,
            requires_clarification=True,
        ),
        "Tell me about my cholesterol.",
    )
    assert plan.intent == IntentType.ambiguous_clarification
    assert not plan.needs_supershyft
    assert not plan.needs_personal_data


def test_follow_up_previous_uses_memory_topic():
    plan = build_query_plan("What about the previous one?", follow_up_topic="hba1c", prior_personal=True)
    assert plan.topic == "hba1c"


def test_route_confidence_is_not_minimum_of_auxiliary_fields(monkeypatch):
    payload = {
        "answers": {
            "request_type": {"type": "choice", "choice": "lab_result_lookup", "confidence": 0.93},
            "data_source": {"type": "choice", "choice": "lab_results", "confidence": 0.41},
            "operation": {"type": "choice", "choice": "lookup", "confidence": 0.37},
            "time_scope": {"type": "choice", "choice": "latest", "confidence": 0.22},
            "requires_personal_data": {"type": "noul", "noul": 0.99},
            "requires_historical_data": {"type": "noul", "noul": 0.02},
            "requires_document": {"type": "noul", "noul": 0.01},
            "requires_clarification": {"type": "noul", "noul": 0.01},
        }
    }
    response = MagicMock(status_code=200)
    response.json.return_value = payload
    transport = MagicMock()
    transport.__enter__.return_value = transport
    transport.post.return_value = response
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: transport)

    decision, _ = JevDecisionsClient(api_key="test").decide(
        JevRoutingState(current_message="What is my LDL?")
    )
    assert decision.confidence == 0.93
    assert decision.field_confidences["time_scope"] == 0.22
    assert decision.field_confidences["data_source"] == 0.41


def test_jev_mapper_does_not_reinterpret_valid_blood_route():
    decision = _decision(
        intent=JevIntent.lab_result_lookup,
        source=JevSource.lab_results,
        operation=JevOperation.lookup,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=["ldl"],
    )
    plan = plan_from_jev(decision, "What is my LDL?", document_ids=["doc-1"])
    assert plan.intent == IntentType.latest_result
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is False
    assert plan.needs_lifestyle is False
    assert plan.needs_supershyft is True
    assert plan.needs_general is False
    assert plan.needs_user_uploaded is False
    assert plan.data_sources == ["blood_reports"]


def test_general_lifestyle_question_stays_general():
    decision = _decision(
        intent=JevIntent.lifestyle_question,
        source=JevSource.none,
        operation=JevOperation.general_answer,
        requires_personal_data=False,
    )
    plan = plan_from_jev(decision, "How can lifestyle affect blood pressure?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.needs_personal_data is False
    assert plan.needs_supershyft is False
    assert plan.medical_evidence_required is True


def test_general_lifestyle_is_demoted_when_not_record_dependent():
    state = JevRoutingState(current_message="How can lifestyle affect blood pressure?")
    result = validate_jev_decision(
        _decision(
            intent=JevIntent.lifestyle_question,
            source=JevSource.lab_results,
            operation=JevOperation.lookup,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        ),
        state,
        deterministic_requires_personal=False,
    )
    assert result.source == JevSource.none
    assert result.requires_personal_data is False
    assert result.operation == JevOperation.general_answer


def test_personalized_nutrition_keeps_lifestyle_without_blood():
    decision = _decision(
        intent=JevIntent.nutrition_question,
        source=JevSource.nutrition,
        operation=JevOperation.retrieve_and_explain,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=["ldl"],
    )
    plan = plan_from_jev(decision, "Based on my LDL, what should I eat?")
    assert plan.intent == IntentType.nutrition_guidance
    assert plan.needs_lifestyle is True
    assert plan.needs_blood is False
    assert plan.needs_bio_ai is False
    assert plan.needs_supershyft is True


def test_personalized_nutrition_multiple_sources_includes_blood_and_bio():
    decision = _decision(
        intent=JevIntent.nutrition_question,
        source=JevSource.multiple_sources,
        operation=JevOperation.retrieve_and_explain,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=["ldl"],
    )
    plan = plan_from_jev(decision, "Based on my LDL and Bio-AI report, what should I eat?")
    assert plan.intent == IntentType.nutrition_guidance
    assert plan.needs_lifestyle is True
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is True
    assert plan.needs_cross_source is True


def test_bio_ai_explanation_does_not_require_lifestyle():
    decision = _decision(
        intent=JevIntent.bio_ai_report_interpretation,
        source=JevSource.bio_ai_report,
        operation=JevOperation.retrieve_and_explain,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_metrics=["cardiac_health"],
    )
    plan = plan_from_jev(decision, "Why is my cardiac health risk high?")
    assert plan.intent == IntentType.bio_ai_explanation
    assert plan.needs_bio_ai is True
    assert plan.needs_lifestyle is False
    assert plan.needs_blood is False


def test_ontology_normalization_does_not_change_source_flags():
    from app.contracts.query import QueryPlan
    from app.pipeline.ontology import normalize_requested_metrics

    plan = QueryPlan(
        intent=IntentType.latest_result,
        knowledge_scope=KnowledgeScope.personal,
        needs_blood=True,
        needs_supershyft=True,
        requested_metrics=["LDL Cholesterol"],
        topic="LDL Cholesterol",
        raw_message="What is my LDL?",
    )
    out = normalize_requested_metrics(plan)
    assert out.needs_blood is True
    assert out.needs_supershyft is True
    assert out.intent == IntentType.latest_result
    assert "ldl" in out.requested_metrics
    assert out.topic == "ldl"

