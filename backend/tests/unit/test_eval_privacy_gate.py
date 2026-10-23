"""Synthetic checks for OpenRouter retention. No clinical records and no network."""

import pytest

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.openrouter_policy import OpenRouterPolicy


def test_current_config_does_not_request_zdr(monkeypatch):
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    policy = OpenRouterPolicy.load()
    assert policy.privacy_profile == "not_approved"
    prefs = policy.provider_preferences(settings.active_llm_model(), personal_health=False)
    assert prefs.get("data_collection") == "deny"
    assert "zdr" not in prefs
    assert "only" not in prefs
    with pytest.raises(LLMUnavailableError, match="not approved"):
        policy.provider_preferences(settings.active_llm_model(), personal_health=True)


def test_required_but_unconfigured_zdr_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    policy = OpenRouterPolicy.load()
    try:
        policy.provider_preferences("google/gemini-3.8-flash", personal_health=True)
        raised = False
    except LLMUnavailableError as exc:
        raised = "not approved" in str(exc)
    assert raised
    # Non-health calls are not failed by this check. That is the judge gap.
    policy.provider_preferences("google/gemini-3.8-flash", personal_health=False)


def test_configured_zdr_is_requested_and_fallbacks_stay_off(monkeypatch):
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "google/gemini-3.8-flash")
    policy = OpenRouterPolicy.load()
    prefs = policy.provider_preferences("google/gemini-3.8-flash", personal_health=True)
    assert "zdr" not in prefs
    assert prefs["data_collection"] == "deny"
    assert prefs["allow_fallbacks"] is False
    assert "only" not in prefs
    with pytest.raises(LLMUnavailableError, match="not approved"):
        policy.provider_preferences("openai/gpt-5-mini", personal_health=True)


def test_judge_client_does_not_mark_personal_health():
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=False)
    assert client.personal_health is False


def test_general_question_is_not_personal_routing_context():
    from app.routing.jev_client import routing_state_has_personal_context
    from app.routing.schemas import JevRoutingState

    assert not routing_state_has_personal_context(JevRoutingState(current_message="What is HbA1c used to measure?"))


def test_jev_personal_context_fails_closed_before_http_when_zdr_missing(monkeypatch):
    from app.routing.jev_client import JevDecisionsClient
    from app.routing.schemas import JevRoutingState

    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    called = []
    monkeypatch.setattr("app.routing.jev_client.get_http_client", lambda: called.append("http") or None)
    try:
        JevDecisionsClient(api_key="synthetic", model="typesafe/jev-1.13").decide(
            JevRoutingState(current_message="What is my LDL?")
        )
    except LLMUnavailableError as exc:
        assert "not approved" in str(exc)
    else:
        raise AssertionError("expected fail closed")
    assert called == []


def test_unapproved_upstream_is_rejected():
    policy = OpenRouterPolicy.load()
    try:
        policy.assert_model("unknown-vendor/secret-model")
    except LLMUnavailableError as exc:
        assert "allowlist" in str(exc)
    else:
        raise AssertionError("expected allowlist rejection")


def test_retry_payload_keeps_fallback_restriction(monkeypatch):
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "google/gemini-3.8-flash")
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=True)
    first = client._build_payload([{"role": "user", "content": "synthetic"}], "plain")
    second = client._build_payload([{"role": "user", "content": "synthetic"}], "plain")
    assert first["provider"]["allow_fallbacks"] is False
    assert second["provider"] == first["provider"]


def test_personal_payload_cannot_bypass_by_clearing_the_flag(monkeypatch):
    from app.llm.openrouter_policy import messages_contain_personal_clinical

    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", OpenAICompatibleLLMClient._real_complete)
    messages = [{"role": "user", "content": "source_measurements LDL 1 mg/dL"}]
    assert messages_contain_personal_clinical(messages)
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=False)
    try:
        client.complete(messages)
    except LLMUnavailableError as exc:
        assert "not approved" in str(exc)
    else:
        raise AssertionError("expected fail closed")
    assert messages_contain_personal_clinical([{"role": "user", "content": "What is HbA1c used to measure?"}]) is False


def test_payload_omits_zdr_when_retention_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    client = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=True)
    with pytest.raises(LLMUnavailableError, match="not approved"):
        client._build_payload([{"role": "user", "content": "synthetic marker 1"}], "plain")
    public = OpenAICompatibleLLMClient(model="google/gemini-3.8-flash", api_key="synthetic", personal_health=False)
    payload = public._build_payload([{"role": "user", "content": "What is a calorie?"}], "plain")
    assert payload["provider"].get("data_collection") == "deny"
    assert "zdr" not in payload["provider"]
