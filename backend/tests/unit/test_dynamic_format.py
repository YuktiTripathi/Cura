"""Dynamic response format: consistent reasoning principles, no fixed visible template.

The answer model plans the shape of each answer inside the single answer call. These tests
check properties of what the model is given and of what reaches the member; they never
compare exact prose.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.pipeline.answer_evidence import GOAL_GUIDANCE, build_answer_evidence
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.evidence_planner import reconcile_query_plan
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan
from app.pipeline.semantic_plan import build_semantic_plan
from app.providers.registry import build_registry

client = TestClient(app)
COMPANION = "eval-user-companion"

_TEMPLATE_HEADINGS = ("What this means", "What connects", "What to focus on", "Health guidance", "Related values")
_FORMAT_WORDS = ("numbered", "bullet", "heading", "paragraph", "FACT:", "then at most", "open with")


@pytest.fixture
def model(monkeypatch):
    calls = []

    def complete(self, messages):
        calls.append(messages)
        return LLMStructuredOutput(
            answer="Model answer.",
            follow_up_questions=[
                "How does this relate to my triglycerides?",
                "Do you have any new symptoms or medications?",
                "Compare this with my previous HbA1c",
                "What should I focus on first?",
            ],
        )

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete)
    return calls


def _chat(user, message, **extra):
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": user}, json={"message": message, **extra}).json()


def _evidence(user, message):
    semantic = build_semantic_plan(message)
    plan, _ = reconcile_query_plan(build_query_plan(message), semantic)
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id=user), plan)
    ctx.semantic_plan = semantic.model_dump(mode="json") | {
        "markers": semantic.markers, "bio_ai": semantic.bio_ai, "concepts": semantic.concepts, "domains": semantic.domains,
    }
    return ctx, build_answer_evidence(ctx, message)


# ------------------------------------------------------------ guidance is purpose, not format


@pytest.mark.parametrize("mode", sorted(GOAL_GUIDANCE))
def test_goal_guidance_states_purpose_without_format(mode):
    text = GOAL_GUIDANCE[mode].lower()
    for word in _FORMAT_WORDS:
        assert word.lower() not in text, (mode, word)


def test_system_prompt_plans_format_dynamically(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "plain")
    ctx, _ = _evidence(COMPANION, "Why are my triglycerides high?")
    system = PromptBuilder().build(ctx, "", "Why are my triglycerides high?")[0]["content"]
    assert "RESPONSE PLANNING" in system and "not a fixed template" in system
    assert "minimal" in system and "detailed" in system  # density chosen by the model
    assert "themes: 3" not in system  # plain mode does not ask for UI theme cards
    for heading in _TEMPLATE_HEADINGS:
        assert f"## {heading}" not in system


def test_rich_mode_keeps_theme_contract(monkeypatch):
    monkeypatch.setattr(settings, "cura_response_mode", "rich")
    ctx, _ = _evidence(COMPANION, "How am I doing overall?")
    system = PromptBuilder().build(ctx, "", "How am I doing overall?")[0]["content"]
    assert "themes: 3" in system


FORMAT_DIVERSITY = [
    "What is my HbA1c?",
    "What does my HbA1c mean?",
    "Is that serious?",
    "Why might it be high?",
    "How does that relate to my triglycerides?",
    "Has it improved?",
    "What should I do first?",
]


def test_no_question_type_is_given_a_visible_template():
    for question in FORMAT_DIVERSITY:
        _, evidence = _evidence(COMPANION, question)
        how = evidence.payload().get("how_to_answer") or ""
        for word in _FORMAT_WORDS:
            assert word.lower() not in how.lower(), (question, word)


# ------------------------------------------------------------ conversation behaviour


def test_style_request_re_answers_previous_question(model):
    first = _chat(COMPANION, "Why are my triglycerides high?")
    body = _chat(COMPANION, "Explain it in detail.", conversation_id=first["conversation_id"])
    assert "triglycerides" in body["meta"]["requested_entities"]
    assert body["answer"] == "Model answer."
    user_turn = model[-1][1]["content"]
    assert "Explain it in detail." in user_turn  # the model sees the actual request


def test_short_version_request(model):
    first = _chat(COMPANION, "What are the top 3 things I should work on?")
    body = _chat(COMPANION, "Give me the short version.", conversation_id=first["conversation_id"])
    assert body["meta"].get("status") != "clarification_required"
    assert body["answer"] == "Model answer."


def test_follow_ups_are_the_models_own_and_specific(model):
    body = _chat(COMPANION, "What does my HbA1c mean?")
    texts = [f["text"] for f in body["follow_ups"]]
    assert 1 <= len(texts) <= 3
    assert "Do you have any new symptoms or medications?" not in texts
    assert "How does this relate to my triglycerides?" in texts


def test_plain_lookup_is_answered_by_the_model_with_context(model):
    body = _chat(COMPANION, "What is my Vitamin D?")
    assert body["answer"] == "Model answer."
    user_turn = model[-1][1]["content"]
    start = user_turn.find("ANSWER EVIDENCE JSON:")
    payload = json.loads(user_turn[start + 22: user_turn.find("\n", start + 23)])
    assert payload["primary_facts"][0]["code"] == "vitamin_d"
    # Enough context to say whether this is a major or minor part of the picture.
    assert "glucose regulation" in payload.get("other_notable_findings", [])


# ------------------------------------------------------------ different users, different emphasis


def test_same_question_different_users_selects_different_evidence():
    seen = {}
    for user in (COMPANION, "eval-user-metabolic", "demo-user-001"):
        _, evidence = _evidence(user, "What should I focus on?")
        seen[user] = [p["pattern"] for p in evidence.patterns]
    assert seen[COMPANION][0] == "glucose regulation"
    assert "iron and red blood cells" in seen[COMPANION]
    assert "iron and red blood cells" not in seen["eval-user-metabolic"]
    assert seen["demo-user-001"] != seen[COMPANION]


# ------------------------------------------------------------ gaps found by the validation conversation


def test_what_looks_reassuring_is_personal():
    _, evidence = _evidence(COMPANION, "What looks reassuring?")
    payload = evidence.payload()
    assert payload.get("reassuring_systems") or payload.get("reassuring_groups")


def test_what_changed_from_previous_report_compares():
    plan = build_semantic_plan("What changed from my previous report?")
    assert plan.primary_goal.value == "COMPARE"


def test_generic_bio_ai_risk_uses_the_assessment_not_a_missing_score():
    _, evidence = _evidence(COMPANION, "Why is my Bio-AI risk high even though some markers are normal?")
    payload = evidence.payload()
    assert "premise_check" not in payload or "not found" not in json.dumps(payload["premise_check"])
    assert {"type_2_diabetes", "dyslipidemia"} <= {f["code"] for f in evidence.primary_facts}
    lipids = next(p for p in evidence.patterns if p["pattern"] == "blood fats (lipids)")
    assert "HDL" in lipids["in_range_in_same_system"]  # the normal marker beside the abnormal ones
