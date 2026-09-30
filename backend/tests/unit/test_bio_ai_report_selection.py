from datetime import date, datetime

from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.query import QueryPlan
from app.llm.models import LLMStructuredOutput
from app.llm.structured import parse_llm_structured
from app.main import app
from app.pipeline.bio_ai_selection import select_bio_ai_report
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.query_planner import build_query_plan
from app.pipeline.renderer import DeterministicRenderer, render_bio_ai_score_list
from app.providers.registry import build_registry, set_registry

client = TestClient(app)
H1 = {"X-Cura-User-Id": "demo-user-001"}
H2 = {"X-Cura-User-Id": "demo-user-002"}


def _risk(code: str, name: str, score: float, status: str = "moderate") -> BioAIRisk:
    return BioAIRisk(code=code, name=name, score=score, status=status)


def _report(
    report_id: str,
    report_date: date,
    risks: list[BioAIRisk],
    *,
    completed_at=None,
    source_line: str = "bio_ai",
    assessment_instance_id: str | None = None,
) -> BioAIReport:
    return BioAIReport(
        report_id=report_id,
        report_date=report_date,
        source_line=source_line,  # type: ignore[arg-type]
        risks=risks,
        completed_at=completed_at,
        assessment_instance_id=assessment_instance_id,
    )


def _plan(message: str, **updates) -> QueryPlan:
    plan = build_query_plan(message)
    return plan.model_copy(update=updates) if updates else plan


def _registry_with_bio(reports: list[BioAIReport]):
    registry = build_registry()

    class Bio:
        def query(self, principal, plan):
            owned = list(reports)
            if plan.report_id:
                owned = [
                    item
                    for item in owned
                    if item.report_id == plan.report_id or item.report_id == f"bioai-{plan.report_id}"
                ]
            return owned

    registry.bio_ai = Bio()
    return registry


SAME_DATE_A = _report(
    "bioai-a",
    date(2026, 9, 24),
    [_risk("dyslipidemia", "Dyslipidemia", 40), _risk("cardiac_health", "Cardiac health", 30)],
    assessment_instance_id="inst-a",
)
SAME_DATE_B = _report(
    "bioai-b",
    date(2026, 9, 24),
    [_risk("dyslipidemia", "Dyslipidemia", 46), _risk("cardiac_health", "Cardiac health", 48)],
    source_line="advanced_bio_ai",
    assessment_instance_id="inst-b",
)
EARLIER = _report(
    "bioai-old",
    date(2026, 8, 1),
    [_risk("dyslipidemia", "Dyslipidemia", 12), _risk("cardiac_health", "Cardiac health", 11)],
    completed_at=datetime(2026, 8, 1, 9, 0),
    assessment_instance_id="inst-old",
)
LATER = _report(
    "bioai-new",
    date(2026, 9, 10),
    [_risk("dyslipidemia", "Dyslipidemia", 22), _risk("cardiac_health", "Cardiac health", 18)],
    completed_at=datetime(2026, 9, 10, 16, 30),
    assessment_instance_id="inst-new",
)


def test_select_single_report():
    choice = select_bio_ai_report([EARLIER], _plan("What are my risk scores?"))
    assert choice.report is EARLIER
    assert not choice.ambiguous


def test_select_latest_when_dates_differ():
    choice = select_bio_ai_report([EARLIER, LATER], _plan("What are my risk scores?"))
    assert choice.report is LATER
    assert not choice.ambiguous


def test_select_ambiguous_when_dates_match():
    choice = select_bio_ai_report([SAME_DATE_A, SAME_DATE_B], _plan("What are my risk scores?"))
    assert choice.report is None
    assert {item.report_id for item in choice.ambiguous} == {"bioai-a", "bioai-b"}


def test_select_explicit_date():
    choice = select_bio_ai_report(
        [EARLIER, LATER],
        _plan("What are my risk scores from August 1?"),
        message="What are my risk scores from August 1?",
    )
    assert choice.report is EARLIER


def test_select_explicit_report_id():
    choice = select_bio_ai_report(
        [SAME_DATE_A, SAME_DATE_B],
        _plan("What are my risk scores from bioai-a?"),
        message="What are my risk scores from bioai-a?",
    )
    assert choice.report is SAME_DATE_A


def test_select_conversation_report():
    choice = select_bio_ai_report(
        [SAME_DATE_A, SAME_DATE_B],
        _plan("What is my Dyslipidemia score?"),
        conversation_report_id="bioai-b",
    )
    assert choice.report is SAME_DATE_B


def test_context_one_report_uses_score_list():
    ctx = ContextBuilder(_registry_with_bio([EARLIER])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What are my risk scores?"),
    )
    assert ctx.status == "ok"
    scores = {item.code: item.score for item in ctx.bio_ai_risks}
    assert scores["dyslipidemia"] == 12
    assert all(item.report_id == "bioai-old" for item in ctx.bio_ai_risks)
    assert all(item.assessment_instance_id == "inst-old" for item in ctx.bio_ai_risks)
    answer = render_bio_ai_score_list(ctx.bio_ai_risks)
    assert "Your Bio-AI Report" in answer
    assert "12" in answer
    assert "11" in answer


def test_context_different_dates_selects_latest_only():
    ctx = ContextBuilder(_registry_with_bio([EARLIER, LATER])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What are my risk scores?"),
    )
    assert ctx.status == "ok"
    scores = {item.code: item.score for item in ctx.bio_ai_risks}
    assert scores["dyslipidemia"] == 22
    assert 12 not in scores.values()
    assert {item.report_id for item in ctx.bio_ai_risks} == {"bioai-new"}
    assert {item.assessment_instance_id for item in ctx.bio_ai_risks} == {"inst-new"}


def test_context_identical_dates_do_not_merge_scores():
    ctx = ContextBuilder(_registry_with_bio([SAME_DATE_A, SAME_DATE_B])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What are my risk scores?"),
    )
    assert ctx.status == "ambiguous"
    assert ctx.bio_ai_risks == []
    assert {item.report_id for item in ctx.disambiguation} == {"bioai-a", "bioai-b"}
    assert {item.assessment_instance_id for item in ctx.disambiguation} == {"inst-a", "inst-b"}
    answer = DeterministicRenderer().render("What are my risk scores?", ctx)
    assert "which report" in answer.lower()
    assert "24 Sep" in answer or "September 24" in answer
    assert "40" not in answer
    assert "46" not in answer
    assert "30" not in answer
    assert "48" not in answer


def test_context_explicit_date_selects_matching_report():
    ctx = ContextBuilder(_registry_with_bio([EARLIER, LATER])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What is my Dyslipidemia score from 2026-08-01?"),
    )
    assert ctx.status == "ok"
    assert [item.score for item in ctx.bio_ai_risks] == [12]
    assert ctx.bio_ai_risks[0].report_id == "bioai-old"


def test_context_explicit_report_reference_selects_that_report():
    ctx = ContextBuilder(_registry_with_bio([SAME_DATE_A, SAME_DATE_B])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What is my Dyslipidemia score from bioai-b?"),
    )
    assert ctx.status == "ok"
    assert [item.score for item in ctx.bio_ai_risks] == [46]
    assert ctx.bio_ai_risks[0].report_id == "bioai-b"
    assert ctx.bio_ai_risks[0].assessment_instance_id == "inst-b"


def test_dyslipidemia_uses_selected_report_only():
    ctx = ContextBuilder(_registry_with_bio([EARLIER, LATER])).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        _plan("What is my Dyslipidemia score?"),
    )
    assert ctx.status == "ok"
    assert len(ctx.bio_ai_risks) == 1
    assert ctx.bio_ai_risks[0].code == "dyslipidemia"
    assert ctx.bio_ai_risks[0].score == 22
    assert ctx.bio_ai_risks[0].report_id == "bioai-new"
    answer = render_bio_ai_score_list(ctx.bio_ai_risks)
    assert "22" in answer
    assert "12" not in answer


def test_chat_one_report_is_deterministic_score_list():
    body = client.post("/api/v1/chat", headers=H2, json={"message": "What are my risk scores?"}).json()
    assert body["meta"]["status"] == "ok"
    assert body["meta"]["llm_mode"] == "structured_bio_ai"
    assert body["meta"]["llm_called"] is False
    assert "Your Bio-AI Report" in body["answer"]
    assert "11" in body["answer"]
    assert "9" in body["answer"]
    assert "I had trouble formatting that answer." not in body["answer"]


def test_chat_same_date_risk_scores_never_hit_llm(monkeypatch):
    from app.core.config import settings
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    monkeypatch.setattr(settings, "enable_llm", True)
    called = {"structured": 0}

    def boom(self, messages):
        called["structured"] += 1
        return LLMStructuredOutput(
            answer="",
            parse_error="non_string_answer:dict",
        )

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", boom)
    body = client.post("/api/v1/chat", headers=H1, json={"message": "What are my risk scores?"}).json()
    assert called["structured"] == 0
    assert body["meta"]["llm_called"] is False
    assert body["meta"]["status"] == "ambiguous"
    assert "which report" in body["answer"].lower()
    assert "9 Jul" in body["answer"]
    assert "bioai-a" not in body["answer"]
    assert "bioai-b" not in body["answer"]
    assert "I had trouble formatting that answer." not in body["answer"]
    assert "30" not in body["answer"]
    assert "48" not in body["answer"]


def test_chat_same_date_dyslipidemia_does_not_merge():
    body = client.post("/api/v1/chat", headers=H1, json={"message": "What is my Dyslipidemia score?"}).json()
    assert body["meta"]["status"] == "ambiguous"
    assert "40" not in body["answer"] or "46" not in body["answer"]
    assert "40" not in body["answer"]
    assert "46" not in body["answer"]
    assert "which report" in body["answer"].lower()


def test_chat_explicit_report_reference_selects_bioai_a():
    body = client.post(
        "/api/v1/chat",
        headers=H1,
        json={"message": "What is my Dyslipidemia score from bioai-a?"},
    ).json()
    assert body["meta"]["status"] == "ok"
    assert "40" in body["answer"]
    assert "46" not in body["answer"]
    assert any(item["report_id"] == "bioai-a" for item in body["evidence"])


def test_chat_explicit_context_ref_selects_bioai_b():
    body = client.post(
        "/api/v1/chat",
        headers=H1,
        json={
            "message": "What are my risk scores?",
            "context_ref": {"type": "bio_ai_report", "source": "supershyft", "report_id": "bioai-b"},
        },
    ).json()
    assert body["meta"]["status"] == "ok"
    assert "48" in body["answer"]
    assert "46" in body["answer"]
    assert "30" not in body["answer"]
    assert "40" not in body["answer"]


def test_chat_different_dates_select_latest(monkeypatch):
    registry = _registry_with_bio([EARLIER, LATER])
    set_registry(registry)
    try:
        body = client.post("/api/v1/chat", headers=H1, json={"message": "What are my risk scores?"}).json()
        assert body["meta"]["status"] == "ok"
        assert "22" in body["answer"]
        assert "18" in body["answer"]
        assert "12" not in body["answer"]
        assert all(item["report_id"] == "bioai-new" for item in body["evidence"])
    finally:
        set_registry(None)


def test_non_string_answer_is_contract_violation(caplog):
    parsed = parse_llm_structured(
        {
            "answer": {
                "hypertension": {"score": 16, "status": "Healthy"},
                "dyslipidemia": {"score": 3, "status": "Healthy"},
            }
        }
    )
    assert parsed.answer == ""
    assert parsed.parse_error == "non_string_answer:dict"
    assert "llm_structured_output_contract_violation" in caplog.text
    assert "non_string_answer:dict" in caplog.text
