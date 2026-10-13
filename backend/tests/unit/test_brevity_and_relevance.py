"""Brevity, relevance and rendering: properties of what the member sees, never exact prose."""

import json

import pytest
from fastapi.testclient import TestClient

from app.contracts.common import IntentType
from app.core.config import settings
from app.llm.models import LLMStructuredOutput
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app
from app.pipeline.evidence_planner import reconcile_query_plan
from app.pipeline.prompt_builder import GENERAL_HEALTH_INSTRUCTIONS, SAFETY_INSTRUCTIONS, _system_for_mode
from app.pipeline.query_planner import build_query_plan
from app.pipeline.semantic_plan import build_semantic_plan
from app.pipeline.visible_output import clean_text, remove_em_dashes

client = TestClient(app)
USER = "eval-user-companion"
EM = "—"
NOISY = (
    f"Your Cardiac Health score is 30 {EM} your Bio-AI report classifies it as Increased. "
    "This is a risk estimate, not a diagnosis.\n\n"
    f"It means the model estimates higher risk {EM} compared with its reference population. "
    "It is not a medical diagnosis. Please discuss this with your doctor. Talk to your clinician about it. "
    "That marker was not available. Range: None to None.\n\n"
    f"Your Cardiac Health score is 30 {EM} your Bio-AI report classifies it as Increased. "
    "This is a risk estimate, not a diagnosis."
)


@pytest.fixture
def model(monkeypatch):
    seen = []

    def complete(self, messages):
        seen.append({"model": self.model, "messages": messages})
        return LLMStructuredOutput(answer=NOISY, summary=f"Short {EM} answer.", follow_up_questions=[
            f"What drives it {EM} lipids or sugar?", "Can I lower it?", "How does it compare?", "Anything else?"])

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "openrouter_api_key", settings.openrouter_api_key or "test-key")
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete)
    return seen


def _chat(message, mode="rich", monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(settings, "cura_response_mode", mode)
    return client.post("/api/v1/chat", headers={"X-Cura-User-Id": USER}, json={"message": message}).json()


def _visible_strings(body) -> str:
    parts = [body.get("answer") or ""]
    for key in ("presentation", "experience", "semantic", "follow_ups"):
        parts.append(json.dumps(body.get(key), ensure_ascii=False))
    return "\n".join(parts)


# ------------------------------------------------------------ text normalization


def test_em_dashes_are_replaced_naturally():
    assert remove_em_dashes(f"Your range is 4.0{EM}5.6%.") == "Your range is 4.0–5.6%."
    assert EM not in remove_em_dashes(f"Your HbA1c {EM} the 3-month average {EM} is high.")
    assert remove_em_dashes(f"It is high {EM} it is above range.") == "It is high. It is above range."
    assert remove_em_dashes(f"High readings {EM} especially after meals {EM} matter.") == "High readings (especially after meals) matter."
    assert "--" not in remove_em_dashes(f"A {EM} B {EM} C {EM} D")


def test_repeated_disclaimers_paragraphs_and_filler_are_removed():
    cleaned = clean_text(NOISY)
    assert EM not in cleaned
    assert cleaned.lower().count("diagnosis") == 1
    assert sum(cleaned.lower().count(w) for w in ("doctor", "clinician")) == 1  # one clinician pointer
    assert "None to None" not in cleaned and "was not available" not in cleaned
    paragraphs = [p for p in cleaned.split("\n\n") if p.strip()]
    assert len(paragraphs) == len(set(paragraphs)) == 2  # the duplicate paragraph is gone
    assert "score is 30" in cleaned  # values are never touched


@pytest.mark.parametrize("mode", ["rich", "plain", "semantic"])
def test_no_visible_em_dash_in_any_mode(model, monkeypatch, mode):
    body = _chat("What does my Cardiac Health score mean?", mode, monkeypatch)
    assert EM not in _visible_strings(body)
    assert len(body["follow_ups"]) <= 3


# ------------------------------------------------------------ prompts ask for brevity


def test_prompts_ask_for_the_shortest_complete_answer(monkeypatch):
    for mode in ("rich", "plain", "semantic"):
        monkeypatch.setattr(settings, "cura_response_mode", mode)
        system = _system_for_mode(SAFETY_INSTRUCTIONS)
        assert "shortest response that fully answers" in system
        assert "about 120 words" in system
        assert "em dash" in system and EM not in system
        assert "at most one short safety qualifier" in system.lower()
    assert "everyday words" in GENERAL_HEALTH_INSTRUCTIONS and "3 to 5 Markdown bullets" in GENERAL_HEALTH_INSTRUCTIONS
    assert EM not in GENERAL_HEALTH_INSTRUCTIONS


# ------------------------------------------------------------ relevance and rendering


@pytest.mark.parametrize("question", [
    "Am I physically active enough for my current health situation?",
    "Why is my Bio-AI metabolic risk high?",
    "What nutrition changes make sense for my current results?",
    "What does my Cardiac Health score mean?",
])
def test_no_full_blood_table_under_conversational_answers(model, monkeypatch, question):
    body = _chat(question, "rich", monkeypatch)
    pres = body.get("presentation") or {}
    assert len(pres.get("findings") or []) <= 4
    assert not pres.get("raw_findings")
    semantic = _chat(question, "semantic", monkeypatch)["semantic"]
    assert not any(b.get("collapsed") for b in semantic["blocks"])
    assert all(len(b.get("values") or []) <= 4 for b in semantic["blocks"])


def test_report_table_appears_when_explicitly_requested(monkeypatch):
    pres = _chat("Show me my latest blood report.", "rich", monkeypatch)["presentation"]
    assert pres["mode"] == "RESULT_LIST" and len(pres["findings"]) == 20
    blocks = _chat("Show me my latest blood report.", "semantic", monkeypatch)["semantic"]["blocks"]
    assert any(b.get("collapsed") and len(b["values"]) == 20 for b in blocks)


def test_found_bio_ai_score_is_not_reported_missing(model, monkeypatch):
    body = _chat("What does my Cardiac Health score mean?", "rich", monkeypatch)
    assert "not in reports" not in body["answer"].lower()
    uncertainties = (body.get("presentation") or {}).get("uncertainties") or []
    assert not any("not available" in u or "not in reports" in u for u in uncertainties)
    prompt = model[-1]["messages"][1]["content"]
    assert "cardiac_health" in prompt


@pytest.mark.parametrize("question", [
    "What do you understand from my blood reports?",
    "Summarize my blood report.",
    "What stands out in my blood tests?",
    "What should I pay attention to in my blood report?",
])
def test_blood_synthesis_reads_blood_data(model, monkeypatch, question):
    _chat(question, "plain", monkeypatch)
    prompt = model[-1]["messages"][1]["content"]
    assert '"hba1c"' in prompt or "HbA1c" in prompt  # measured blood values reach the model
    # Even when routed as an uploaded-document question with nothing attached.
    semantic = build_semantic_plan(question)
    routed = build_query_plan(question).model_copy(update={"needs_user_uploaded": True, "needs_blood": False})
    plan, _ = reconcile_query_plan(routed, semantic)
    assert plan.needs_blood


def test_bio_ai_only_routing_still_adds_blood_for_blood_questions():
    question = "What do you understand from my blood reports?"
    routed = build_query_plan(question).model_copy(update={"needs_blood": False, "needs_bio_ai": True, "intent": IntentType.bio_ai_explanation})
    plan, _ = reconcile_query_plan(routed, build_semantic_plan(question))
    assert plan.needs_blood


def test_lifestyle_prompt_carries_relevant_context_only(model, monkeypatch):
    _chat("Am I physically active enough for my current health situation?", "plain", monkeypatch)
    prompt = model[-1]["messages"][1]["content"].lower()
    for unrelated in ('"calcium"', '"basophils"', '"bilirubin"', '"mcv"', '"rdw"'):
        assert unrelated not in prompt, unrelated


def test_escalated_answers_keep_the_see_a_doctor_sentence():
    text = "This is not a diagnosis. Please see your doctor today about this result."
    assert "doctor" in clean_text(text, keep_clinician=True)


def test_generic_follow_ups_are_dropped_in_every_mode(model, monkeypatch):
    for mode in ("rich", "plain", "semantic"):
        body = _chat("What does my Cardiac Health score mean?", mode, monkeypatch)
        texts = [f["text"].lower() for f in body["follow_ups"]]
        assert not any("anything else" in t or "new symptoms" in t for t in texts)
