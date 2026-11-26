"""V2.3 passages must reach the assembled model request, by the same rule in every environment.

The model call is replaced, so this checks the exact messages CURA would send, not a helper in isolation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.main import app
from app.llm.openai_compatible import OpenAICompatibleLLMClient

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}
QUESTION = "What does HbA1c measure?"


def _captured_request(monkeypatch, question: str = QUESTION, env: str = "development") -> str:
    seen: list = []

    def fake(self, messages, *args, **kwargs):
        seen.append(messages)
        raise LLMUnavailableError("captured for test")

    monkeypatch.setattr(settings, "enable_llm", True)
    monkeypatch.setattr(settings, "app_env", env)
    # The real client is replaced at the network edge: these are the messages CURA would send.
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", fake)
    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete", fake)
    client.post("/api/v1/chat", headers=H, json={"message": question})
    assert seen, "no model request was assembled"
    return "\n".join(m.get("content", "") for m in seen[-1] if isinstance(m, dict))


def test_v23_passages_reach_the_request_without_an_approval_notice(monkeypatch):
    text = _captured_request(monkeypatch)
    assert "CURATED KNOWLEDGE (V2.3)" in text
    assert "HbA1c" in text.split("CURATED KNOWLEDGE (V2.3)", 1)[1]
    assert "pending clinical review" not in text
    assert "No curated knowledge was supplied" not in text


def test_production_uses_the_same_retrieval_as_development(monkeypatch):
    from app.biomarkers import medical_registry as lib

    question, keys, sides = "Why could my HbA1c be high?", ["hba1c", "fasting_sugar"], {"hba1c": "high"}
    monkeypatch.setattr(settings, "app_env", "development")
    dev = lib.chat_passages(question, keys, sides)
    monkeypatch.setattr(settings, "app_env", "production")
    prod = lib.chat_passages(question, keys, sides)
    assert dev and dev == prod


def test_rejected_rows_are_never_used():
    from app.biomarkers import medical_registry as lib

    assert not lib.eligible_for_chat({"review_status": "rejected"})
    assert lib.eligible_for_chat({"review_status": "pending_clinical_review"})
    assert not lib.eligible_for_chat(None)


def test_unverified_threshold_notes_are_not_sent(monkeypatch):
    from app.biomarkers import medical_registry as lib

    row = lib.biomarker_content()["tsh"]
    assert row.get("reference_range_note")
    assert not lib.claim_verified(row["content_key"], "reference_range_note", row["reference_range_note"])
    lines = lib.chat_passages("What does my TSH result mean?", ["tsh"], {"tsh": "high"})
    assert not any("lab range and clinical thresholds" in x for x in lines)
    verified = lib.chat_passages("What does my HbA1c result mean?", ["hba1c"], {"hba1c": "high"})
    assert any("5.7 to 6.4%" in x for x in verified)


def _knowledge(text: str) -> str:
    assert "CURATED KNOWLEDGE (V2.3)" in text
    return text.split("CURATED KNOWLEDGE (V2.3)", 1)[1]


def test_cause_questions_receive_explained_factors_not_bare_names(monkeypatch):
    block = _knowledge(_captured_request(monkeypatch, "Why could my HbA1c be high?"))
    assert "how influencing factors act" in block
    assert "Very low iron: Very low iron can make HbA1c read falsely high" in block


def test_result_questions_receive_threshold_note_and_a_misconception(monkeypatch):
    block = _knowledge(_captured_request(monkeypatch, "What does my HbA1c result mean?"))
    assert "5.7 to 6.4%" in block  # diagnostic threshold, kept apart from the lab range
    assert "an in-range result may reflect" in block  # this member's HbA1c is in range


def test_relationship_questions_receive_what_the_pair_shows(monkeypatch):
    from app.biomarkers import medical_registry as lib

    lines = lib.chat_passages("How are my ferritin and haemoglobin related?", ["ferritin", "hemoglobin_hb"])
    joined = " ".join(lines)
    assert "confirms iron-deficiency anaemia" in joined


def test_budget_scales_with_question_complexity():
    from app.biomarkers import medical_registry as lib

    simple = lib.chat_passages("What is HbA1c?", ["hba1c"])
    broad = lib.chat_passages(
        "Explain my results: HbA1c, triglycerides and HDL",
        ["hba1c", "triglycerides", "hdl_cholesterol_direct"],
        {"hba1c": "high", "triglycerides": "high", "hdl_cholesterol_direct": "low"},
    )
    size = lambda lines: sum(len(x) for x in lines) // 4
    assert size(simple) <= lib.BASE_BUDGET["definition"] + 50
    assert size(simple) < size(broad) <= lib.MAX_BUDGET + 100
    joined = " ".join(broad)
    for name in ("HbA1c", "Triglycerides", "HDL"):
        assert f"{name}" in joined
    assert "Relationship with triglycerides" in joined  # the pair the person asked about together


def test_entries_are_never_sent_whole():
    from app.biomarkers import medical_registry as lib

    row = lib.biomarker_content()["hdl_cholesterol_direct"]
    lines = lib.chat_passages("How can I improve my HDL?", ["hdl_cholesterol_direct"], {"hdl_cholesterol_direct": "low"})
    fx = [x["how_it_acts"] for x in row["factor_explanations"]]
    joined = " ".join(lines)
    assert sum(1 for f in fx if f.rstrip(".") in joined) <= 4
    assert "everyday steps that may help" in joined
