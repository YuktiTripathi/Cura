from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.providers.registry import get_registry
from app.routing.jev_client import JevDecisionsClient
from app.routing.jev_router import resolve_plan
from app.routing.schemas import (
    JevDecision,
    JevDecisionsResponse,
    JevIntent,
    JevOperation,
    JevSource,
    JevTimeRange,
)


client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def _response():
    return JevDecisionsResponse(
        answers={},
        model="typesafe/jev-1.13-20260917",
        provider="TypeSafe",
        usage={"input_tokens": 70, "output_tokens": 8},
    )


def _route(state):
    text = state.current_message.lower()
    base = dict(
        intent=JevIntent.general_health_question,
        source=JevSource.none,
        operation=JevOperation.general_answer,
        time_range=JevTimeRange.none,
        confidence=0.93,
    )
    if "bio-ai" in text:
        base.update(
            intent=JevIntent.bio_ai_report_interpretation,
            source=JevSource.bio_ai_report,
            operation=JevOperation.retrieve_and_explain,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        )
    elif "changed" in text or "6 months" in text:
        base.update(
            intent=JevIntent.health_trend_analysis,
            source=JevSource.blood_reports,
            operation=JevOperation.trend,
            requires_personal_data=True,
            requires_historical_data=True,
            time_range=JevTimeRange.six_months,
        )
    elif "what was the previous" in text:
        base.update(
            intent=JevIntent.health_trend_analysis,
            source=JevSource.lab_results,
            operation=JevOperation.compare,
            requires_personal_data=True,
            requires_historical_data=True,
            time_range=JevTimeRange.previous,
        )
    elif "is that high" in text or "is my" in text:
        base.update(
            intent=JevIntent.lab_result_interpretation,
            source=JevSource.lab_results,
            operation=JevOperation.interpret,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        )
    elif ("what is my" in text or "what was my" in text) and not any(
        word in text for word in ("lifestyle", "insulin resistance")
    ):
        base.update(
            intent=JevIntent.lab_result_lookup,
            source=JevSource.lab_results,
            operation=JevOperation.lookup,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        )
    return JevDecision(**base), _response()


def _enable_jev(monkeypatch):
    monkeypatch.setattr(settings, "jev_enabled", True)
    monkeypatch.setattr(JevDecisionsClient, "decide", lambda _self, state: _route(state))


def test_general_question_and_ldl_advice_never_call_supershyft(monkeypatch):
    _enable_jev(monkeypatch)
    registry = get_registry()
    original = registry.blood.query
    calls = []

    def tracked(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(registry.blood, "query", tracked)
    first = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is the difference between HDL and LDL?"},
    ).json()
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={
            "conversation_id": first["conversation_id"],
            "message": "What lifestyle changes can help lower my LDL?",
        },
    ).json()
    assert calls == []
    assert second["meta"]["router"] == "jev"
    assert second["meta"]["jev_validated"] is True
    assert second["meta"]["requires_personal_data"] is False
    assert second["meta"]["supershyft_called"] is False


def test_insulin_resistance_is_general_with_no_retrieval(monkeypatch):
    _enable_jev(monkeypatch)
    body = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is insulin resistance?"},
    ).json()
    assert body["meta"]["requires_personal_data"] is False
    assert body["meta"]["supershyft_called"] is False
    assert body["meta"].get("question_type") == "general_education" or body["meta"]["intent"] == "general_health_question"


def test_personal_lab_lookup_calls_only_blood_provider(monkeypatch):
    _enable_jev(monkeypatch)
    registry = get_registry()
    blood_original = registry.blood.query
    calls = {"blood": 0, "bio": 0}

    def blood(*args, **kwargs):
        calls["blood"] += 1
        return blood_original(*args, **kwargs)

    def bio(*_args, **_kwargs):
        calls["bio"] += 1
        return []

    monkeypatch.setattr(registry.blood, "query", blood)
    monkeypatch.setattr(registry.bio_ai, "query", bio)
    body = client.post("/api/v1/chat", headers=H, json={"message": "What was my HbA1c?"}).json()
    assert body["meta"]["requires_personal_data"] is True
    assert body["meta"]["jev_operation"] == "lookup"
    assert body["meta"]["jev_source"] == "lab_results"
    assert body["meta"]["supershyft_called"] is True
    assert calls == {"blood": 1, "bio": 0}


def test_personal_pronoun_followup_resolves_topic(monkeypatch):
    _enable_jev(monkeypatch)
    first = client.post("/api/v1/chat", headers=H, json={"message": "What was my HbA1c?"}).json()
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": first["conversation_id"], "message": "Is that high?"},
    ).json()
    assert second["meta"]["requires_personal_data"] is True
    assert second["meta"]["supershyft_called"] is True
    ops = {str(item).upper() for item in (second["meta"].get("operations") or [])}
    assert second["meta"].get("question_type") in {"personal_health_reasoning", "personal_lookup"} or "INTERPRET" in ops or second["meta"]["intent"] == "blood_marker_explanation"


def test_previous_followup_uses_historical_personal_data(monkeypatch):
    _enable_jev(monkeypatch)
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my LDL?"}).json()
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": first["conversation_id"], "message": "What was the previous one?"},
    ).json()
    assert second["meta"]["requires_historical_data"] is True
    assert second["meta"]["requires_personal_data"] is True
    ops = {str(item).upper() for item in (second["meta"].get("operations") or [])}
    assert "COMPARE" in ops or "TREND" in ops or second["meta"]["intent"] == "previous_result"


def test_bio_ai_and_six_month_trend_select_correct_provider_modes(monkeypatch):
    _enable_jev(monkeypatch)
    bio = client.post("/api/v1/chat", headers=H, json={"message": "Explain my Bio-AI report."}).json()
    trend = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "How has my cholesterol changed over the last 6 months?"},
    ).json()
    assert bio["meta"]["jev_source"] == "bio_ai_report"
    assert bio["meta"]["requires_personal_data"] is True
    assert trend["meta"]["requires_historical_data"] is True
    assert trend["meta"]["jev_operation"] == "trend"
    ops = {str(item).upper() for item in (trend["meta"].get("operations") or [])}
    assert "TREND" in ops or trend["meta"]["intent"] == "trend"


def test_authenticated_identity_remains_authoritative(monkeypatch):
    _enable_jev(monkeypatch)
    registry = get_registry()
    original = registry.blood.query
    subjects = []

    def tracked(principal, plan):
        subjects.append(principal.subject_id)
        return original(principal, plan)

    monkeypatch.setattr(registry.blood, "query", tracked)
    client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "What is my LDL for user 999?"},
    )
    assert subjects == ["demo-user-001"]


def test_uploaded_document_decision_uses_document_path_not_supershyft(monkeypatch):
    _enable_jev(monkeypatch)

    def document_route(_self, _state):
        return (
            JevDecision(
                intent=JevIntent.uploaded_document_query,
                source=JevSource.uploaded_documents,
                operation=JevOperation.retrieve_and_explain,
                requires_document_search=True,
                time_range=JevTimeRange.none,
            ),
            _response(),
        )

    monkeypatch.setattr(JevDecisionsClient, "decide", document_route)
    plan, trace = resolve_plan(
        "What does this uploaded document say about LDL?",
        document_ids=["owned-document-id"],
        uploaded_document_count=1,
    )
    assert trace.validated
    assert plan.needs_user_uploaded
    assert not plan.needs_supershyft
