"""Approved personal answers use one model call. Missing data and privacy stay deterministic."""

from datetime import date

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, KnowledgeScope
from app.contracts.health_context import HealthContext, InRangeSummary, MissingItem
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.pipeline.numeric_grounding import unsupported_adjacent_numbers
from app.pipeline.query_planner import build_query_plan
from app.pipeline.reasoning import ReasoningService, explanation_requested

STUB = "Your HbA1c of 6.1% is above the report range. This is not a diagnosis."


def _approve(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(
        settings,
        "personal_health_approved_models",
        "openai/gpt-5-mini,google/gemini-3.8-flash,openai/gpt-5.6-luna",
    )


def _stub(monkeypatch, answer=STUB):
    calls = []

    def complete_structured(self, messages):
        calls.append(self.model)
        return LLMStructuredOutput(answer=answer)

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    return calls


def _hba1c():
    return BloodMarker(
        id="a1c",
        key="hba1c",
        name="HbA1c",
        value=6.1,
        unit="%",
        reference_low=4.4,
        reference_high=5.7,
        flag="high",
        measured_at=date(2026, 9, 20),
        report_id="r2",
    )


def _ctx(plan, markers=None, risks=None, missing=None):
    return HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=plan.knowledge_scope,
        markers=markers or [],
        bio_ai_risks=risks or [],
        missing=missing or [],
        task_contract=plan.task_contract,
        in_range_summary=InRangeSummary(in_range=1, out_of_range=1, missing=0),
    )


def test_blood_report_explanation_calls_the_model_once(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch)
    message = "Help me understand my latest blood report."
    plan = build_query_plan(message)
    assert explanation_requested(plan, message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert result.llm_called is True
    assert calls == [calls[0]]
    assert len(calls) == 1


def test_bio_ai_explanation_calls_the_model_once(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch, "The diabetes risk score is 68, a high band. This is not a diagnosis.")
    message = "Help me understand my latest Bio-AI report and its main findings."
    plan = build_query_plan(message)
    risk = BioAIRisk(
        code="type_2_diabetes",
        name="Type 2 diabetes",
        score=68,
        status="high",
        lifestyle_contribution=55,
        contributing_factors=["activity"],
        measured_at=date(2026, 9, 20),
    )
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, risks=[risk]))
    assert result.llm_called is True
    assert len(calls) == 1
    assert result.llm_mode != "structured_bio_ai"


def test_biomarker_explanation_calls_the_model_once(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch)
    message = "Why is my HbA1c high?"
    plan = build_query_plan(message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert explanation_requested(plan, message)
    assert result.llm_called is True
    assert len(calls) == 1


def test_numeric_lookup_is_worded_by_the_model(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch)
    message = "What is my HbA1c?"
    plan = build_query_plan(message)
    assert not explanation_requested(plan, message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert result.llm_called is True
    assert len(calls) == 1
    assert "6.1" in result.answer
    assert "verified_fallback" not in result.flags


def test_bio_ai_score_lookup_is_worded_by_the_model(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch, "Your type 2 diabetes risk score is 68, in the high band. This is not a diagnosis.")
    message = "What is my Bio-AI diabetes score?"
    plan = build_query_plan(message)
    risk = BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=68, status="high", measured_at=date(2026, 9, 20))
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, risks=[risk]))
    assert result.llm_called is True
    assert len(calls) == 1
    assert "68" in result.answer


def test_omitted_bio_ai_score_is_added_from_the_record(monkeypatch):
    _approve(monkeypatch)
    _stub(monkeypatch, "The diabetes estimate is in a high band. This is not a diagnosis.")
    message = "What is my Bio-AI diabetes score?"
    plan = build_query_plan(message)
    risk = BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=68, status="high", measured_at=date(2026, 9, 20))
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, risks=[risk]))
    assert "68" in result.answer
    assert "not a diagnosis" in result.answer.lower() or "not diagnoses" in result.answer.lower()


def test_missing_report_does_not_invent_a_value(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch)
    message = "Help me understand my latest blood report."
    plan = build_query_plan(message)
    plan = plan.model_copy(update={"task_contract": {**(plan.task_contract or {}), "primary_source": "blood_report"}})
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan))
    assert result.llm_called is False
    assert calls == []
    assert "6.1" not in result.answer
    assert result.llm_mode == "primary_source_unavailable"


def test_unapproved_privacy_does_not_call_the_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    calls = _stub(monkeypatch)
    message = "Why is my HbA1c high?"
    plan = build_query_plan(message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert calls == []
    assert result.llm_called is False
    assert result.fallback_reason == "privacy"
    assert "6.1" in result.answer
    assert "external provider" not in result.answer.lower()


def test_provider_timeout_keeps_the_stored_value(monkeypatch):
    _approve(monkeypatch)

    def down(self, messages):
        raise LLMUnavailableError("timeout")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", down)
    message = "Why is my HbA1c high?"
    plan = build_query_plan(message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert result.llm_called is False
    assert result.fallback_reason == "model_unavailable"
    assert "6.1" in result.answer
    assert "could not be generated" in result.answer.lower() or "6.1" in result.answer


def test_general_question_does_not_require_personal_data():
    plan = build_query_plan("What is LDL cholesterol?")
    assert plan.needs_personal_data is False
    assert plan.needs_blood is False


def test_hindi_explanation_is_not_a_bare_lookup():
    from app.pipeline.indic_terms import canonicalize_biomarker_terms

    message = canonicalize_biomarker_terms("मेरा टीएसएच ठीक है क्या?")
    plan = build_query_plan(message)
    assert plan.needs_personal_data is True
    assert explanation_requested(plan, message) or plan.topic == "tsh"


def test_follow_up_keeps_the_marker_for_the_model(monkeypatch):
    _approve(monkeypatch)
    calls = []

    def complete_structured(self, messages):
        calls.append(" ".join(m.get("content") or "" for m in messages))
        return LLMStructuredOutput(answer=STUB)

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    message = "Why is that high?"
    plan = build_query_plan("Why is my HbA1c high?").model_copy(
        update={"operations": ["INTERPRET", "CONTINUE_INTERPRETATION"], "raw_message": message}
    )
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan, [_hba1c()]))
    assert result.llm_called is True
    assert len(calls) == 1
    assert "6.1" in calls[0]


def test_diagnosis_restraint_runs_before_the_model(monkeypatch):
    _approve(monkeypatch)
    calls = _stub(monkeypatch)
    message = "Do I have diabetes?"
    plan = build_query_plan(message)
    result = ReasoningService().run(
        message=message,
        plan=plan,
        context=_ctx(plan, [_hba1c()]),
        diagnosis_restraint=True,
    )
    assert calls == []
    assert result.llm_called is False
    assert result.llm_mode == "structured_safety"


def test_numeric_grounding_rejects_an_invented_measurement():
    flagged = unsupported_adjacent_numbers(
        "Your HbA1c is 9.9%.",
        {"measurements": [{"name": "HbA1c", "value": 6.1, "unit": "%"}]},
    )
    assert flagged
