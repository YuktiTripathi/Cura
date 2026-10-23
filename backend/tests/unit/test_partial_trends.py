"""Partial lipid trends stay answerable when one marker in the panel is missing."""

from datetime import date

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, AnswerModelTier, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.pipeline.evidence_inventory import assemble_evidence, classify_marker_trends
from app.pipeline.query_planner import build_query_plan
from app.pipeline.reasoning import ReasoningService

QUESTION = "Has my cholesterol improved since my previous report?"


def _marker(key, name, value, unit, day, report_id):
    return BloodMarker(
        id=f"{key}-{day}",
        key=key,
        name=name,
        value=value,
        unit=unit,
        flag="normal",
        measured_at=day,
        report_id=report_id,
    )


def _context(markers):
    plan = build_query_plan(QUESTION).model_copy(
        update={
            "answer_model_tier": AnswerModelTier.standard_medical,
            "model_tier": AnswerModelTier.standard_medical,
            "operations": ["COMPARE", "INTERPRET"],
            "needs_blood": True,
            "needs_personal_data": True,
        }
    )
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=markers,
        task_contract=plan.task_contract,
    )
    return plan, context


def _hdl_pair():
    return [
        _marker("hdl", "HDL", 37, "mg/dL", date(2026, 6, 12), "r1"),
        _marker("hdl", "HDL", 38, "mg/dL", date(2026, 9, 20), "r2"),
    ]


def _cholesterol_pair():
    return [
        _marker("cholesterol", "Total Cholesterol", 210, "mg/dL", date(2026, 6, 12), "r1"),
        _marker("cholesterol", "Total Cholesterol", 198, "mg/dL", date(2026, 9, 20), "r2"),
    ]


def test_cholesterol_and_hdl_histories_are_both_used():
    coverage = classify_marker_trends(QUESTION, _cholesterol_pair() + _hdl_pair())
    assert coverage["support"] == "partial"
    keys = {row["key"] for row in coverage["supported"]}
    assert keys == {"cholesterol", "hdl"}
    assert "ldl" in coverage["missing"] and "triglycerides" in coverage["missing"]
    hdl = next(row for row in coverage["supported"] if row["key"] == "hdl")
    assert hdl["absolute_change"] == 1
    assert hdl["previous_date"] == "2026-06-12"
    assert hdl["current_date"] == "2026-09-20"
    assert hdl["unit"] == "mg/dL"


def test_hdl_history_does_not_block_a_missing_cholesterol_panel():
    plan, context = _context(_hdl_pair())
    package = assemble_evidence(plan, context)
    coverage = classify_marker_trends(QUESTION, context.markers)
    assert coverage["support"] == "partial"
    assert "cholesterol" in coverage["missing"]
    assert package.blocked_answer is None
    assert any(row["key"] == "hdl" for row in coverage["supported"])
    assert "overall cholesterol" in (package.limitation or "").lower()


def test_cholesterol_history_with_hdl_missing_is_partial():
    coverage = classify_marker_trends(QUESTION, _cholesterol_pair())
    assert coverage["support"] == "partial"
    assert "hdl" in coverage["missing"]
    assert {row["key"] for row in coverage["supported"]} == {"cholesterol"}


def test_one_date_does_not_calculate_a_trend():
    coverage = classify_marker_trends(QUESTION, [_marker("hdl", "HDL", 37, "mg/dL", date(2026, 9, 20), "r2")])
    assert coverage["support"] == "unsupported"
    assert coverage["supported"] == []
    assert "hdl" in coverage["single_date"]


def test_incompatible_units_are_not_subtracted():
    markers = [
        _marker("hdl", "HDL", 37, "mg/dL", date(2026, 6, 12), "r1"),
        _marker("hdl", "HDL", 0.98, "mmol/L", date(2026, 9, 20), "r2"),
    ]
    coverage = classify_marker_trends(QUESTION, markers)
    assert coverage["supported"] == []
    assert "hdl" in coverage["incompatible_units"]


def test_conflicting_same_day_values_are_not_trended():
    markers = [
        _marker("hdl", "HDL", 37, "mg/dL", date(2026, 6, 12), "r1"),
        _marker("hdl", "HDL", 40, "mg/dL", date(2026, 6, 12), "r1b"),
        _marker("hdl", "HDL", 38, "mg/dL", date(2026, 9, 20), "r2"),
    ]
    coverage = classify_marker_trends(QUESTION, markers)
    assert coverage["supported"] == []
    assert "hdl" in coverage["conflicting"]


def test_no_relevant_measurements_stay_blocked():
    plan, context = _context([])
    package = assemble_evidence(plan, context)
    assert package.blocked_answer
    assert package.measurements == []


def test_unapproved_privacy_does_not_call_the_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "not_approved")
    monkeypatch.setattr(settings, "personal_health_approved_models", "")
    calls = []

    def complete_structured(self, messages):
        calls.append(messages)
        return LLMStructuredOutput(answer="should not run")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    plan, context = _context(_hdl_pair())
    result = ReasoningService().run(message=QUESTION, plan=plan, context=context)
    assert calls == []
    assert result.llm_called is False
    assert result.fallback_reason == "privacy"
    assert "37" in result.answer and "38" in result.answer
    assert "cholesterol" in result.answer.lower()
    assert "overall cholesterol" in result.answer.lower()


def test_approved_path_sends_the_hdl_pair_to_the_model(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(
        settings,
        "personal_health_approved_models",
        "openai/gpt-5-mini,google/gemini-3.8-flash,openai/gpt-5.6-luna",
    )
    seen = []

    def complete_structured(self, messages):
        seen.append({"model": self.model, "text": " ".join(m.get("content") or "" for m in messages)})
        return LLMStructuredOutput(answer="HDL changed by 1 mg/dL. Total cholesterol was not retrieved.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    plan, context = _context(_hdl_pair())
    result = ReasoningService().run(message=QUESTION, plan=plan, context=context)
    assert result.llm_called is True
    assert seen
    assert "37" in seen[0]["text"] and "38" in seen[0]["text"]
    assert "overall cholesterol" in (context.evidence_package or {}).get("limitation", "").lower()


def test_model_outage_returns_the_partial_comparison(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "openai/gpt-5-mini")

    def complete_structured(self, messages):
        raise LLMUnavailableError("provider timeout")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    plan, context = _context(_hdl_pair())
    result = ReasoningService().run(message=QUESTION, plan=plan, context=context)
    assert result.llm_called is False
    assert result.fallback_reason == "model_unavailable"
    assert "37" in result.answer and "38" in result.answer
    assert "mg/dL" in result.answer
    assert "2026-06-12" in result.answer and "2026-09-20" in result.answer
    assert "overall cholesterol" in result.answer.lower()
