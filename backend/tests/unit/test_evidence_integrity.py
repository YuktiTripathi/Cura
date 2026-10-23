"""Verified measurements stay authoritative when a model answer contradicts them."""

from datetime import date
from types import SimpleNamespace

from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth
from app.contracts.health_context import HealthContext, InRangeSummary
from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.pipeline.cross_source import CrossSourceComparator, SourceValue, render_comparison
from app.pipeline.query_planner import build_query_plan
from app.pipeline.reasoning import ReasoningService
from app.pipeline.evidence_inventory import (
    authoritative_measurement_answer,
    classify_marker_trends,
    contradicting_answer,
    omitted_supported_facts,
    render_partial_trend,
)


def _marker(key, value, unit, day):
    return SimpleNamespace(key=key, name=key.upper(), value=value, unit=unit, measured_at=date.fromisoformat(day))


def test_hdl_history_when_total_cholesterol_is_missing():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
    ]
    text = render_partial_trend("Has my cholesterol improved?", markers)
    assert "37" in text and "38" in text
    assert "cholesterol" in text.lower()
    assert "overall cholesterol" in text.lower()


def test_hdl_and_triglyceride_history():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
        _marker("triglycerides", 240, "mg/dL", "2026-06-12"),
        _marker("triglycerides", 220, "mg/dL", "2026-09-20"),
    ]
    coverage = classify_marker_trends("Has my cholesterol improved?", markers)
    assert coverage["support"] == "partial"
    assert {row["key"] for row in coverage["supported"]} == {"hdl", "triglycerides"}
    assert "cholesterol" in coverage["missing"]


def test_both_hba1c_dates_are_classified():
    markers = [
        _marker("hba1c", 6.2, "%", "2026-06-12"),
        _marker("hba1c", 6.1, "%", "2026-09-20"),
    ]
    coverage = classify_marker_trends("Why is my HbA1c high?", markers)
    assert coverage["support"] == "full"
    assert coverage["supported"][0]["previous_value"] == 6.2
    assert coverage["supported"][0]["current_value"] == 6.1


def test_absent_history_is_not_invented():
    markers = [_marker("hdl", 38, "mg/dL", "2026-09-20")]
    text = render_partial_trend("Has my HDL improved?", markers)
    assert "Only one measurement date" in text
    assert "38" in text or "hdl" in text.lower()


def test_same_day_conflict_blocks_a_trend():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-09-20"),
        _marker("hdl", 50, "mg/dL", "2026-09-20"),
    ]
    coverage = classify_marker_trends("Has my HDL improved?", markers)
    assert coverage["support"] == "unsupported"
    assert "hdl" in coverage["conflicting"]


def test_missing_unit_blocks_cross_source_delta():
    result = CrossSourceComparator().compare(
        "creatinine",
        "Creatinine",
        SourceValue(source="user_uploaded", value=1.06, unit="mg/dL", date=date(2026, 8, 1)),
        SourceValue(source="supershyft", value=0.9, unit=None, date=date(2026, 9, 20)),
    )
    assert result.difference is None
    assert result.direction is None
    assert result.unit is None
    text = render_comparison(result)
    assert "improved" not in text.lower()
    assert "0.9 mg" not in text
    assert "no verified unit" in text.lower() or "no numeric change" in text.lower()


def test_different_units_are_not_subtracted():
    result = CrossSourceComparator().compare(
        "glucose",
        "Glucose",
        SourceValue(source="user_uploaded", value=5.4, unit="mmol/L", date=date(2026, 8, 1)),
        SourceValue(source="supershyft", value=98, unit="mg/dL", date=date(2026, 9, 20)),
    )
    assert result.difference is None
    text = render_comparison(result)
    assert "units do not match" in text.lower()


def test_same_unit_comparison_still_calculates():
    result = CrossSourceComparator().compare(
        "hdl",
        "HDL",
        SourceValue(source="user_uploaded", value=37, unit="mg/dL", date=date(2026, 6, 12)),
        SourceValue(source="supershyft", value=38, unit="mg/dL", date=date(2026, 9, 20)),
    )
    assert result.difference == 1
    assert result.direction == "higher"


def test_conflicting_dates_are_not_a_supported_pair():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-09-20"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
        _marker("hdl", 40, "mg/dL", "2026-06-12"),
    ]
    coverage = classify_marker_trends("Has my HDL improved?", markers)
    assert coverage["support"] == "unsupported"
    assert coverage["conflicting"] == ["hdl"]


def test_a_correct_hdl_sentence_still_gains_the_skipped_triglyceride_pair():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
        _marker("triglycerides", 240, "mg/dL", "2026-06-12"),
        _marker("triglycerides", 220, "mg/dL", "2026-09-20"),
    ]
    extra = omitted_supported_facts("Has my cholesterol improved?", markers, "HDL rose from 37 mg/dL to 38 mg/dL.")
    assert "240" in extra and "220" in extra
    assert "overall cholesterol" in extra.lower()


def test_false_absence_is_replaced_with_verified_text():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
        _marker("triglycerides", 240, "mg/dL", "2026-06-12"),
        _marker("triglycerides", 220, "mg/dL", "2026-09-20"),
    ]
    invented = "The report did not include triglycerides, and there is no earlier HDL value."
    assert contradicting_answer("Has my cholesterol improved?", markers, invented)
    final = authoritative_measurement_answer("Has my cholesterol improved?", markers)
    assert "37" in final and "38" in final and "240" in final and "220" in final
    assert "not found" not in final.lower() or "Not in the retrieved records" in final


def test_invented_unit_and_unsupported_improvement_are_rejected():
    markers = [
        _marker("creatinine", 1.06, "mg/dL", "2026-08-01"),
        _marker("creatinine", 0.9, None, "2026-09-20"),
    ]
    invented = "Creatinine improved and went down from 1.06 mg/dL to 0.9 mg/dL."
    assert contradicting_answer("Has my creatinine improved?", markers, invented)
    final = authoritative_measurement_answer("Has my creatinine improved?", markers)
    assert "improved" not in (final or "").lower()
    assert "no trend" in (final or "").lower() or "do not match" in (final or "").lower()


def test_hba1c_why_keeps_both_dates_without_claiming_a_cause():
    markers = [
        _marker("hba1c", 6.2, "%", "2026-06-12"),
        _marker("hba1c", 6.1, "%", "2026-09-20"),
    ]
    invented = "Only one measurement date is available, so there is no trend."
    assert contradicting_answer("Why is my HbA1c high?", markers, invented)
    final = authoritative_measurement_answer("Why is my HbA1c high?", markers)
    assert "6.2" in final and "6.1" in final
    assert "does not establish why" in final


def test_follow_up_uses_markers_already_in_context():
    markers = [
        _marker("hba1c", 6.2, "%", "2026-06-12"),
        _marker("hba1c", 6.1, "%", "2026-09-20"),
    ]
    final = authoritative_measurement_answer("Has it improved since last time?", markers)
    assert "6.2" in final and "6.1" in final


def test_reasoning_replaces_a_false_absence_without_a_second_call(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "openai/gpt-5-mini")
    calls = []

    def complete_structured(self, messages):
        calls.append(1)
        return LLMStructuredOutput(answer="Only one measurement date is available, so triglycerides were not found.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    message = "Has my cholesterol improved?"
    plan = build_query_plan(message)
    markers = [
        BloodMarker(id="h1", key="hdl", name="HDL", value=37, unit="mg/dL", flag="low", measured_at=date(2026, 6, 12), report_id="r1"),
        BloodMarker(id="h2", key="hdl", name="HDL", value=38, unit="mg/dL", flag="low", measured_at=date(2026, 9, 20), report_id="r2"),
        BloodMarker(id="t1", key="triglycerides", name="Triglycerides", value=240, unit="mg/dL", flag="high", measured_at=date(2026, 6, 12), report_id="r1"),
        BloodMarker(id="t2", key="triglycerides", name="Triglycerides", value=220, unit="mg/dL", flag="high", measured_at=date(2026, 9, 20), report_id="r2"),
    ]
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=plan.knowledge_scope,
        markers=markers,
        task_contract=plan.task_contract,
        in_range_summary=InRangeSummary(in_range=0, out_of_range=4, missing=0),
    )
    result = ReasoningService().run(message=message, plan=plan, context=context)
    assert calls == [1]
    assert "37" in result.answer and "38" in result.answer
    assert "240" in result.answer and "220" in result.answer
    assert "were not found" not in result.answer.lower()


def test_chat_cholesterol_answer_includes_triglyceride_history(monkeypatch):
    from fastapi.testclient import TestClient

    from app.llm.models import LLMStructuredOutput
    from app.llm.openai_compatible import OpenAICompatibleLLMClient
    from app.main import app

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "openai/gpt-5-mini")

    def complete_structured(self, messages):
        blob = "\n".join(item.get("content") or "" for item in messages)
        assert "triglycerides" in blob.lower() or "220" in blob
        return LLMStructuredOutput(answer="HDL rose from 37 mg/dL to 38 mg/dL. Total cholesterol has only one date.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    body = TestClient(app).post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "eval-user-metabolic"},
        json={"message": "Has my cholesterol improved since my previous report?"},
    ).json()
    answer = body["answer"]
    assert "37" in answer and "38" in answer
    assert "240" in answer and "220" in answer
    assert "176" in answer


def test_chat_kidney_question_compares_both_sources(monkeypatch):
    from io import BytesIO

    from fastapi.testclient import TestClient

    from app.llm.models import LLMStructuredOutput
    from app.llm.openai_compatible import OpenAICompatibleLLMClient
    from app.main import app
    from tests.helpers.pdf_fixtures import make_text_pdf

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "personal_health_privacy_profile", "safety_retention")
    monkeypatch.setattr(settings, "personal_health_approved_models", "openai/gpt-5-mini")
    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "complete_structured",
        lambda self, messages: LLMStructuredOutput(
            answer="Creatinine improved from 1.06 mg/dL to 0.9 mg/dL."
        ),
    )
    client = TestClient(app)
    headers = {"X-Cura-User-Id": "eval-user-metabolic"}
    pdf = make_text_pdf([
        "KIDNEY FUNCTION\nCreatinine 1.06 mg/dL\nReference 0.7-1.4\nUrea 32 mg/dL\nDate 2026-08-01",
        "IMPRESSION\nWithin the printed reference range.",
    ])
    uploaded = client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("kidney.pdf", BytesIO(pdf), "application/pdf")},
    )
    assert uploaded.status_code == 200
    document_id = uploaded.json()["document_id"]
    for _ in range(25):
        row = client.get(f"/api/v1/documents/{document_id}", headers=headers).json()
        if row.get("extraction_status") == "completed":
            break
    else:
        raise AssertionError(row.get("extraction_status"))
    other = client.get(f"/api/v1/documents/{document_id}", headers={"X-Cura-User-Id": "eval-user-iron"})
    assert other.status_code == 404
    body = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Has my kidney function improved?", "document_ids": [document_id]},
    ).json()
    answer = body["answer"]
    assert "1.06" in answer and "0.9" in answer
    assert "not a clinical judgment" in answer.lower()
    assert client.delete(f"/api/v1/documents/{document_id}", headers=headers).status_code == 204
    assert "supershyft" in answer.lower()


def test_cholesterol_family_includes_triglycerides():
    from app.pipeline.lab_parameters import retrieval_keys

    assert "triglycerides" in retrieval_keys("cholesterol")


def test_improved_with_an_uploaded_document_is_cross_source():
    from app.pipeline.query_planner import build_query_plan
    from app.pipeline.source_routing import apply_source_routing

    plan = build_query_plan("Has my kidney function improved?")
    routed = apply_source_routing(plan, document_ids=["doc-1"])
    assert routed.needs_cross_source is True
    assert routed.needs_user_uploaded is True
    assert routed.needs_blood is True


def test_improved_without_an_upload_stays_on_supershyft():
    from app.pipeline.query_planner import build_query_plan
    from app.pipeline.source_routing import apply_source_routing

    plan = build_query_plan("Has my cholesterol improved?")
    routed = apply_source_routing(plan, document_ids=[])
    assert routed.needs_cross_source is False


def test_privacy_and_unavailable_paths_use_the_same_verified_text():
    markers = [
        _marker("hdl", 37, "mg/dL", "2026-06-12"),
        _marker("hdl", 38, "mg/dL", "2026-09-20"),
    ]
    text = render_partial_trend("Has my cholesterol improved?", markers)
    assert "37" in text and "38" in text
    assert "mg/dL" in text
