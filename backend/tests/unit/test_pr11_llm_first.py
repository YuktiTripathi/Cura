"""The approved model writes ordinary answers. Safety and outages stay labeled fallbacks."""

from datetime import date

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth
from app.contracts.health_context import HealthContext
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.pipeline.query_planner import build_query_plan
from app.pipeline.reasoning import ReasoningService


def _approve(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(
        settings,
        "personal_health_approved_models",
        "openai/gpt-5-mini,google/gemini-3.8-flash,openai/gpt-5.6-luna",
    )


def _marker():
    return BloodMarker(
        id="ldl",
        key="ldl",
        name="LDL cholesterol",
        value=96,
        unit="mg/dL",
        reference_low=0,
        reference_high=100,
        flag="normal",
        measured_at=date(2026, 9, 20),
        report_id="r2",
    )


def _ctx(plan):
    return HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=plan.knowledge_scope,
        markers=[_marker()],
        task_contract=plan.task_contract,
    )


def test_lookup_prompt_contains_the_verified_value(monkeypatch):
    _approve(monkeypatch)
    seen = []

    def complete_structured(self, messages):
        seen.append(" ".join(item.get("content") or "" for item in messages))
        return LLMStructuredOutput(answer="Your LDL cholesterol is 96 mg/dL, inside the range on the report.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    message = "What is my LDL cholesterol?"
    plan = build_query_plan(message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan))
    assert result.llm_called is True
    assert result.answer.startswith("Your LDL")
    assert "96" in seen[0]
    assert "verified_fallback" not in result.flags


def test_provider_outage_is_a_labeled_fallback(monkeypatch):
    _approve(monkeypatch)

    def down(self, messages):
        raise LLMUnavailableError("timeout")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", down)
    message = "What is my LDL cholesterol?"
    plan = build_query_plan(message)
    result = ReasoningService().run(message=message, plan=plan, context=_ctx(plan))
    assert result.llm_called is False
    assert result.fallback_reason == "model_unavailable"
    assert result.llm_mode == "deterministic_fallback"
    assert "96" in result.answer


def test_clinical_improvement_sentence_is_removed_without_a_second_claim(monkeypatch):
    _approve(monkeypatch)

    def complete_structured(self, messages):
        return LLMStructuredOutput(
            answer="HbA1c was 6.2% on 2026-06-12 and 6.1% on 2026-09-20. That is a clear improvement."
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    message = "Has my HbA1c improved?"
    plan = build_query_plan(message)
    marker = BloodMarker(
        id="a", key="hba1c", name="HbA1c", value=6.1, unit="%", flag="high",
        measured_at=date(2026, 9, 20), report_id="r2",
    )
    earlier = BloodMarker(
        id="b", key="hba1c", name="HbA1c", value=6.2, unit="%", flag="high",
        measured_at=date(2026, 6, 12), report_id="r1",
    )
    ctx = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=plan.knowledge_scope,
        markers=[marker, earlier],
        task_contract=plan.task_contract,
    )
    result = ReasoningService().run(message=message, plan=plan, context=ctx)
    assert result.llm_called is True
    assert "6.2" in result.answer and "6.1" in result.answer
    assert "improvement" not in result.answer.lower()
    assert "not a clinical conclusion" not in result.answer.lower()
