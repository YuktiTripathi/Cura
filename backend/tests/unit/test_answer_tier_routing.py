"""Answer-model tier policy: FAST / STANDARD / DEEP chosen per turn from reasoning needs.

Properties, not phrases: the same scorer decides every question; tiers follow reasoning
load (markers, sources, contrast, breadth, prioritisation, conversation), not intent alone
and not clinical severity; one answer call per turn; same CURA prompt for every model.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts.common import AnswerModelTier
from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.llm.registry import model_id_for_tier
from app.main import app
from app.pipeline import service as service_module
from app.pipeline.semantic_plan import build_semantic_plan
from app.routing.model_tier import assess_answer_complexity

client = TestClient(app)
USER = "eval-user-companion"
FAST, STANDARD, DEEP = AnswerModelTier.fast_reasoning, AnswerModelTier.standard_medical, AnswerModelTier.deep_medical_reasoning


def _tier(question: str, **kwargs) -> AnswerModelTier:
    return assess_answer_complexity(question, build_semantic_plan(question), **kwargs).tier


@pytest.fixture
def model(monkeypatch):
    calls: list[dict] = []

    def complete(self, messages):
        calls.append({"model": self.model, "messages": messages})
        return LLMStructuredOutput(answer="Stand-in answer.")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete)
    return calls


@pytest.fixture
def routing(monkeypatch):
    records: list[dict] = []
    original = service_module.model_routing_record

    def spy(response, eval_turn):
        record = original(response, eval_turn)
        records.append(record)
        return record

    monkeypatch.setattr(service_module, "model_routing_record", spy)
    return records


def _chat(message, conversation_id=None):
    body = {"message": message, **({"conversation_id": conversation_id} if conversation_id else {})}
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": USER}, json=body).json()


# ------------------------------------------------------------ the policy on its own


@pytest.mark.parametrize("question", ["What is my Vitamin D?", "What is my HbA1c?", "Is my TSH normal?", "Show me my LDL."])
def test_straightforward_questions_are_fast(question):
    assert _tier(question) == FAST


@pytest.mark.parametrize("question", [
    "What does my HbA1c mean?",
    "Why are my triglycerides high?",
    "Could my sleep be affecting my glucose?",
    "What should I pay attention to in this report?",
])
def test_personal_interpretation_is_standard(question):
    assert _tier(question) == STANDARD


@pytest.mark.parametrize("question", [
    "Why is my Bio-AI diabetes risk high even though some blood markers are normal?",
    "How do my HbA1c, glucose, triglycerides and lifestyle fit together?",
    "Compare my latest and previous reports and tell me what has actually improved or worsened.",
    "What are my top health priorities across blood, Bio-AI and lifestyle data?",
])
def test_cross_source_synthesis_is_deep(question):
    assert _tier(question) == DEEP


def test_same_topic_different_complexity_gets_different_tiers():
    # Both are about glucose control; only the reasoning they need differs.
    simple = "What is my HbA1c?"
    complex_ = ("My HbA1c rose despite weight loss and normal fasting glucose. "
                "My Bio-AI diabetes risk also increased. Why?")
    assert _tier(simple) == FAST
    assert _tier(complex_) == DEEP


def test_clinical_severity_alone_does_not_buy_the_deep_model():
    assert _tier("My HbA1c is 9.1%. What does that mean?") == STANDARD
    assert _tier(
        "My HbA1c is 9.1%, my glucose is high, my triglycerides are high, my Bio-AI diabetes risk is 70, "
        "and I exercise daily. Why is this happening?"
    ) == DEEP


@pytest.mark.parametrize("question,allowed", [
    ("What about my sugar?", {FAST, STANDARD}),  # vague, no reasoning cue
    ("Is that bad?", {FAST, STANDARD}),
    ("What should I focus on first?", {STANDARD}),  # prioritisation without cross-source breadth
    ("Which findings are most important and which abnormalities are probably minor?", {DEEP}),
    ("Has my HbA1c improved?", {STANDARD}),  # single-marker trend
    ("What changed across my reports, and which changes actually matter for my diabetes risk?", {DEEP}),
])
def test_ambiguous_and_borderline_questions(question, allowed):
    assert _tier(question) in allowed


def test_follow_up_context_raises_reasoning_load():
    plain = assess_answer_complexity("Why is my HbA1c high?", build_semantic_plan("Why is my HbA1c high?"))
    follow = assess_answer_complexity("Why is my HbA1c high?", build_semantic_plan("Why is my HbA1c high?"), conversation_markers=["glucose", "triglycerides"], continuing=True)
    assert follow.score > plain.score
    assert "follow_up_needs_prior_context" in follow.reasons


def test_routing_set_is_balanced_and_scored_by_the_same_policy():
    cases = json.loads((Path(__file__).resolve().parents[2] / "data" / "model_routing_set.json").read_text())["cases"]
    assert {t: sum(c["tier"] == t for c in cases) for t in ("fast", "standard", "deep")} == {"fast": 20, "standard": 20, "deep": 20}
    single = [c for c in cases if len(c["turns"]) == 1]
    agree = sum(_tier(c["turns"][0]).name.split("_")[0] == {"fast": "fast", "standard": "standard", "deep": "deep"}[c["tier"]] for c in single)
    assert agree / len(single) >= 0.85


# ------------------------------------------------------------ through the pipeline


def test_tier_is_recalculated_per_turn_with_context_and_one_call_each(model, routing):
    first = _chat("What is my HbA1c?")
    assert routing[-1]["answer_tier"] == "fast" and len(model) == 1
    assert model[-1]["model"] == model_id_for_tier(FAST)

    second = _chat("What does that mean?", first["conversation_id"])
    assert routing[-1]["answer_tier"] == "standard" and len(model) == 2
    assert "hba1c" in second["meta"]["requested_entities"]  # context carried across the switch

    third = _chat("But my fasting glucose looks okay and my Bio-AI diabetes risk is high. Why?", first["conversation_id"])
    assert routing[-1]["answer_tier"] == "deep" and len(model) == 3  # one answer call per turn
    assert model[-1]["model"] == model_id_for_tier(DEEP)
    assert third["conversation_id"] == first["conversation_id"]
    # The deep model sees the earlier turns and the member's HbA1c value.
    user_turn = model[-1]["messages"][-1]["content"]
    assert "9.1" in user_turn
    assert routing[-1]["escalated"] is False


def test_every_model_gets_the_same_cura_prompt(model, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    seen = {}
    for forced in ("fast", "standard", "deep"):
        monkeypatch.setattr(settings, "cura_force_answer_tier", forced)
        _chat("Why are my triglycerides high?")
        seen[forced] = model[-1]
    assert {v["model"] for v in seen.values()} == {model_id_for_tier(t) for t in (FAST, STANDARD, DEEP)}
    systems = {v["messages"][0]["content"] for v in seen.values()}
    assert len(systems) == 1  # identity, safety and format guidance do not change with the model


def test_force_tier_is_ignored_in_production(monkeypatch):
    from app.routing.model_tier import forced_answer_tier

    monkeypatch.setattr(settings, "cura_force_answer_tier", "deep")
    monkeypatch.setattr(settings, "app_env", "production")
    assert forced_answer_tier() is None
    monkeypatch.setattr(settings, "app_env", "development")
    assert forced_answer_tier() == DEEP
    monkeypatch.setattr(settings, "cura_force_answer_tier", "")
    assert forced_answer_tier() is None  # no override by default


def test_routing_telemetry_has_no_phi(model, routing):
    _chat("Why are my triglycerides high?")
    record = routing[-1]
    for key in ("intent", "complexity_score", "answer_tier", "answer_model", "routing_reason", "answer_model_ms",
                "total_ms", "escalated", "initial_tier", "input_tokens", "output_tokens", "estimated_cost_usd"):
        assert key in record
    text = json.dumps(record)
    assert "266" not in text and "triglycerides high" not in text.lower()


def test_routing_is_not_shown_to_the_member(model, monkeypatch):
    body = _chat("Why are my triglycerides high?")
    assert "gpt" not in body["answer"].lower() and "gemini" not in body["answer"].lower()
    assert "model_routing" not in (body["meta"].get("debug") or {})
    monkeypatch.setattr(settings, "cura_model_routing_debug", True)
    monkeypatch.setattr(settings, "app_env", "development")
    debug = _chat("Why are my triglycerides high?")["meta"].get("debug") or {}
    assert debug["model_routing"]["answer_tier"] == "standard"


def test_deep_failure_is_honest_not_a_weaker_answer(monkeypatch, routing):
    from app.core.errors import LLMUnavailableError

    def down(self, messages):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", down)
    body = _chat("Why is my Bio-AI diabetes risk high even though some blood markers are normal?")
    assert "could not be generated" in body["answer"].lower()
    assert "type 2 diabetes" in body["answer"].lower()
