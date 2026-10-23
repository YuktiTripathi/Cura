"""Document explanations are personal health and fail closed without ZDR."""

from app.pipeline.document_answer import DocumentAnswer, _maybe_explain


EVIDENCE = "Creatinine 1.06 mg/dL page 8 In range 0.7-1.4"


def _isolate(monkeypatch, *, zdr_required: bool, zdr_on: bool):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_llm", False)
    monkeypatch.setattr(settings, "document_explanation_enabled", True)
    monkeypatch.setattr(settings, "require_zdr_for_personal_health", zdr_required)
    monkeypatch.setattr(settings, "cura_openrouter_require_zdr", False)
    monkeypatch.setattr(settings, "openrouter_zero_data_retention", zdr_on)
    monkeypatch.setattr(
        settings,
        "personal_health_privacy_profile",
        "safety_retention" if zdr_on else "not_approved",
    )
    monkeypatch.setattr(
        settings,
        "personal_health_approved_models",
        "google/gemini-3.8-flash" if zdr_on else "",
    )


def test_clinical_document_cannot_use_the_non_personal_policy(monkeypatch):
    _isolate(monkeypatch, zdr_required=True, zdr_on=False)
    called = {"client": False, "http": False}

    def _client(**_kwargs):
        called["client"] = True
        raise AssertionError("client constructed without a satisfied personal-health policy")

    monkeypatch.setattr("app.llm.factory.get_llm_client", _client)
    monkeypatch.setattr(
        "httpx.Client.post",
        lambda *_a, **_k: called.__setitem__("http", True),
    )
    out = _maybe_explain(DocumentAnswer(answer=EVIDENCE), "Explain my kidney function test")
    assert called == {"client": False, "http": False}
    assert out.llm_called is False
    assert out.llm_mode == "document_fallback"
    assert out.fallback_reason == "privacy"
    assert "1.06" in out.answer
    assert out.model is None


def test_satisfied_policy_marks_the_call_as_personal_health(monkeypatch):
    _isolate(monkeypatch, zdr_required=True, zdr_on=True)
    from app.core.config import settings

    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "google/gemini-3.8-flash")
    seen = {}

    class _Client:
        model = "configured-model"
        provider = "openrouter"

        def complete(self, messages, **_k):
            seen["system_has_value"] = "1.06" in messages[0]["content"]
            return '{"answer": "Creatinine is 1.06 mg/dL on page 8.", "follow_up_questions": []}'

    def _factory(**kwargs):
        seen["personal_health"] = kwargs.get("personal_health")
        return _Client()

    monkeypatch.setattr("app.llm.factory.get_llm_client", _factory)
    out = _maybe_explain(DocumentAnswer(answer=EVIDENCE), "Explain my kidney function test")
    assert seen["personal_health"] is True
    assert seen["system_has_value"] is False
    assert out.llm_called is True
    assert out.llm_mode == "document_explanation"
    assert out.model == "configured-model"
    assert out.provider == "openrouter"
    assert out.fallback_reason is None
