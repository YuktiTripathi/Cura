"""CURA as a health companion, not a report renderer (behaviors, not exact prose).

User ``eval-user-companion`` (mock data): HbA1c 9.1 % and glucose 214.47 mg/dL (no fasting
label) high; triglycerides 266, LDL 162, total cholesterol 248 high; HDL 44 normal; iron /
red-cell pattern (hemoglobin, MCV, MCH low, RDW high, ferritin low); vitamin D 27 low;
liver, kidney and thyroid in range; previous report in April; Bio-AI type 2 diabetes,
dyslipidemia and cardiac risk high; questionnaire: rarely active, refined grains.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, MarkerFlag
from app.contracts.health_context import HealthContext
from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.pipeline.answer_evidence import build_answer_evidence
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.evidence_planner import reconcile_query_plan
from app.pipeline.grounding import GroundingChecker
from app.pipeline.health_patterns import find_patterns, related_markers
from app.pipeline.query_planner import build_query_plan
from app.pipeline.semantic_plan import Personalization, ReasoningGoal, build_semantic_plan
from app.pipeline.validator import _drop_unsupported
from app.providers.registry import build_registry

client = TestClient(app)
USER_ID = "eval-user-companion"
H = {"X-Cura-User-Id": USER_ID}
MODEL_ANSWER = (
    "Your glucose control stands out most: your HbA1c and glucose are both above your report's range, "
    "and your triglycerides point in the same direction. Your liver and kidney markers are reassuring. "
    "I'd focus on glucose control first."
)


@pytest.fixture
def model(monkeypatch):
    """A stand-in answer model, so the tests see what the pipeline does around the model."""
    seen = {}

    def complete(self, messages):
        seen["messages"] = messages
        return LLMStructuredOutput(answer=MODEL_ANSWER)

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete)
    return seen


@pytest.fixture
def plain(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "plain")


def _chat(message, **extra):
    return client.post("/api/v1/chat", headers=H, json={"message": message, **extra}).json()


def _evidence(message, conversation=None):
    semantic = build_semantic_plan(message)
    plan, _ = reconcile_query_plan(build_query_plan(message), semantic)
    related = related_markers(list(semantic.markers)) if semantic.markers and semantic.primary_goal.value not in {"LOOKUP", "COMPARE"} else []
    if related:
        plan = plan.model_copy(update={
            "requested_metrics": list(dict.fromkeys([*(plan.requested_metrics or semantic.markers), *related])),
            "display_entities": list(plan.display_entities or semantic.markers),
        })
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id=USER_ID), plan)
    ctx.semantic_plan = semantic.model_dump(mode="json") | {
        "markers": semantic.markers, "bio_ai": semantic.bio_ai, "concepts": semantic.concepts,
        "domains": semantic.domains, "conversation_markers": conversation or [], "related_markers": related,
    }
    return build_answer_evidence(ctx, message)


# ------------------------------------------------------------ routing


@pytest.mark.parametrize(
    "message",
    [
        "What are the top 3 things I should work on?",
        "Which abnormal values probably matter less?",
        "Which result needs the most attention?",
        "What should I fix first?",
    ],
)
def test_priority_questions_route_to_prioritization(message):
    plan = build_semantic_plan(message)
    assert plan.primary_goal == ReasoningGoal.prioritize
    assert plan.personalization == Personalization.required
    assert not plan.clarification_needed


def test_top_3_is_not_a_number_clarification():
    body = _chat("What are the top 3 things I should work on?")
    assert body["meta"].get("status") != "clarification_required"
    assert "which test is that number from" not in body["answer"].lower()


def test_bare_number_is_still_clarified():
    assert build_semantic_plan("Is 120 bad?").clarification_needed


def test_four_question_types_get_different_handling():
    shapes = {q: build_semantic_plan(q).primary_goal for q in (
        "Show me my blood report.",
        "What should I actually pay attention to?",
        "What are the top 3 things I should work on?",
        "Why are my triglycerides high?",
    )}
    assert shapes["Show me my blood report."] == ReasoningGoal.lookup
    assert shapes["What should I actually pay attention to?"] == ReasoningGoal.synthesize
    assert shapes["What are the top 3 things I should work on?"] == ReasoningGoal.prioritize
    assert shapes["Why are my triglycerides high?"] == ReasoningGoal.causes


# ------------------------------------------------------------ the model's answer is the answer


@pytest.mark.parametrize(
    "message",
    [
        "What should I actually pay attention to in my latest report?",
        "What are the top 3 things I should work on?",
        "Why is my Bio-AI metabolic risk high?",
        "Why are my triglycerides high?",
    ],
)
def test_plain_mode_final_answer_is_the_model_answer(model, plain, message):
    body = _chat(message)
    assert body["answer"] == MODEL_ANSWER
    assert body["meta"]["response_mode"] == "plain"
    assert body["presentation"] is None
    assert body["follow_ups"] == [] and body["testing_option"] is None and body["recommendations"] == []


def test_rich_mode_does_not_splice_stock_text_into_model_answer(model):
    body = _chat("What should I actually pay attention to in my latest report?")
    assert body["answer"].startswith(MODEL_ANSWER)
    assert "highest-yield next step" not in body["answer"]
    assert "was not in reports" not in body["answer"]
    assert body["meta"]["response_mode"] == "rich"


def test_missing_expanded_entities_are_not_appended(model, plain):
    answer = _chat("Why is my Bio-AI metabolic risk high?")["answer"]
    for noise in ("Fasting insulin", "not in reports", "score not available", "was not found"):
        assert noise not in answer


def test_follow_up_reasons_with_the_model(model, plain):
    first = _chat("Why are my triglycerides high?")
    body = _chat("Is that because of my sugar?", conversation_id=first["conversation_id"])
    assert body["answer"] == MODEL_ANSWER  # not a value lookup template
    assert "triglycerides" in body["meta"]["requested_entities"]


# ------------------------------------------------------------ what the model is given


def test_triglycerides_context_is_relevant_not_a_dump():
    evidence = _evidence("Why are my triglycerides high?")
    primary = {f["code"] for f in evidence.primary_facts}
    supporting = {f["code"] for f in evidence.supporting_facts}
    assert primary == {"triglycerides"}
    assert {"hba1c", "glucose"} & supporting
    payload = json.dumps(evidence.payload()).lower()
    for unrelated in ('"alt"', "uric acid", '"bun"', '"tsh"', "calcium", "ferritin"):
        assert unrelated not in payload, unrelated


def test_priorities_are_patterns_ranked_by_significance():
    evidence = _evidence("What are the top 3 things I should work on?")
    patterns = [p["pattern"] for p in evidence.patterns]
    assert patterns[:2] == ["glucose regulation", "blood fats (lipids)"]
    assert "iron and red blood cells" in patterns[:3]
    assert patterns.index("vitamins") > 2  # a borderline vitamin D does not outrank the main patterns
    assert len(evidence.primary_facts) <= 3
    leads = [f["code"] for f in evidence.primary_facts]
    assert not ({"hba1c", "glucose"} <= set(leads))  # one lead per pattern, not two glucose slots
    systems = {r["system"] for r in evidence.reassuring}
    assert {"liver enzymes", "kidney function"} <= systems


def test_glucose_without_fasting_label_is_used_not_reported_missing():
    evidence = _evidence("Is my sugar high?")
    assert "glucose" in {f["code"] for f in evidence.primary_facts}
    notes = json.dumps(evidence.uncertainty_facts).lower()
    assert "fasting" in notes and "not available" not in notes


def test_follow_up_context_carries_previous_marker():
    evidence = _evidence("Is that because of my sugar?", conversation=["triglycerides"])
    assert "triglycerides" in {f["code"] for f in evidence.supporting_facts}


def test_patterns_mark_reassuring_systems():
    from app.contracts.blood import BloodMarker as BM

    markers = [
        BM(id="1", key="alt", name="ALT", value=28, unit="U/L", reference_low=7, reference_high=56, flag=MarkerFlag.normal),
        BM(id="2", key="hba1c", name="HbA1c", value=9.1, unit="%", reference_low=4.0, reference_high=5.6, flag=MarkerFlag.high),
    ]
    patterns, reassuring = find_patterns(markers, [])
    assert patterns[0]["pattern"] == "glucose regulation"
    assert reassuring == [{"system": "liver enzymes", "in_range": ["ALT"]}]


# ------------------------------------------------------------ grounding keeps good answers


def _ctx():
    return HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.simple,
        markers=[BloodMarker(id="1", key="hba1c", name="HbA1c", value=9.1, unit="%", reference_low=4.0,
                             reference_high=5.6, flag=MarkerFlag.high)],
    )


@pytest.mark.parametrize(
    "text",
    [
        "Your HbA1c is 9.1%, which reflects your average glucose over the last 2-3 months.",
        "Your HbA1c of 9.1% fits with a higher type 2 diabetes risk; walking 30 minutes after meals can help.",
        "Here are the top 3 things to focus on.",
    ],
)
def test_explanatory_numbers_are_not_treated_as_invented_values(text):
    assert GroundingChecker().unsupported_number_sentences(text, _ctx()) == []


def test_invented_value_removes_only_that_sentence():
    text = (
        "Your HbA1c is above your report's range. Your HbA1c is 7.4%. "
        "It reflects your average glucose over several months. Glucose control is the first thing to work on."
    )
    issues = GroundingChecker().unsupported_number_sentences(text, _ctx())
    assert issues and issues[0][1] == "7.4"
    kept = _drop_unsupported(text, issues)
    assert "7.4" not in kept and "first thing to work on" in kept


# ------------------------------------------------------------ deterministic paths in plain mode


def test_plain_report_listing_shows_results(plain):
    answer = _chat("Show me my latest blood report.")["answer"]
    assert "HbA1c: 9.1 %" in answer and "Outside your report's range" in answer
    assert "Within range:" in answer


def test_plain_lookup_is_a_natural_sentence(plain):
    answer = _chat("What is my HbA1c?")["answer"]
    assert answer.startswith("Your HbA1c is 9.1%")
    assert "above your report's range (4.0–5.6%)" in answer
