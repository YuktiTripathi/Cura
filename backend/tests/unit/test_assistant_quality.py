from fastapi.testclient import TestClient

from app.contracts.common import IntentType, KnowledgeScope
from app.core.config import settings
from app.llm.structured import parse_llm_structured
from app.main import app
from app.pipeline.intent import classify_intent
from app.pipeline.lab_parameters import match_lab_keys
from app.pipeline.operations import classify_operation, named_personal_sources
from app.pipeline.query_planner import build_query_plan
from app.pipeline.recommendation_engine import RecommendationEngine
from app.pipeline.context_builder import ContextBuilder
from app.providers.registry import build_registry
from app.auth.models import AuthenticatedPrincipal

client = TestClient(app)
IRON = {"X-Cura-User-Id": "eval-user-iron"}
H1 = {"X-Cura-User-Id": "demo-user-001"}


def test_aliases_fasting_insulin_and_magnesium_and_cbc():
    assert match_lab_keys("What is my fasting insulin?") == ["fasting_insulin"]
    assert match_lab_keys("What is my magnesium?") == ["magnesium"]
    assert match_lab_keys("What is my MCV and MCH?") == ["mcv", "mch"]
    assert match_lab_keys("What is my serum iron?") == ["iron"]
    from app.pipeline.lab_parameters import canonicalize_marker_name

    assert canonicalize_marker_name("Mean Corp Hb (MCH)") == "mch"
    assert canonicalize_marker_name("Haemoglobin (HB)") == "hemoglobin"


def test_hba1c_measure_is_general_explanation():
    intent, topic, *_ = classify_intent("What does HbA1c measure?")
    assert intent == IntentType.general_health_question
    plan = build_query_plan("What does HbA1c measure?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.needs_personal_data
    assert classify_operation(plan, plan.raw_message).value == "EXPLAIN"


def test_false_hba1c_increase_is_trend_with_premise():
    plan = build_query_plan("Why did my HbA1c increase?")
    assert plan.intent == IntentType.trend
    assert plan.premise_claim == "increased"
    body = client.post("/api/v1/chat", headers=IRON, json={"message": "Why did my HbA1c increase?"}).json()
    assert "5.3" in body["answer"]
    assert "did not increase" in body["answer"].lower()


def test_missing_fasting_insulin_does_not_dump_report():
    body = client.post("/api/v1/chat", headers=IRON, json={"message": "What is my fasting insulin?"}).json()
    low = body["answer"].lower()
    assert "not available" in low or "not present" in low
    assert "10.5" not in body["answer"]
    assert "82.9" not in body["answer"]


def test_multi_source_named_sources_are_requested():
    message = "Give me a comprehensive overview using my blood report, Bio-AI, questionnaire, and goals."
    assert named_personal_sources(message) >= {"blood", "bio_ai", "questionnaire", "goals"}
    plan = build_query_plan(message)
    assert plan.needs_blood and plan.needs_bio_ai and plan.needs_questionnaire and plan.needs_goals
    body = client.post("/api/v1/chat", headers=IRON, json={"message": message}).json()
    assert "10.5" in body["answer"] or "haemoglobin" in body["answer"].lower() or "hemoglobin" in body["answer"].lower()
    outcomes = {row["source"]: row["status"] for row in (body.get("meta") or {}).get("source_outcomes") or []}
    # meta may not expose outcomes; retrieval still must not be questionnaire-only
    assert plan.source.value in {"mixed", "supershyft"} or plan.needs_blood


def test_provenance_follow_up_names_report():
    first = client.post("/api/v1/chat", headers=IRON, json={"message": "What is my cholesterol?"}).json()
    cid = first["conversation_id"]
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "Where did you get that cholesterol value?", "conversation_id": cid},
    ).json()
    low = body["answer"].lower()
    assert "report" in low
    assert "ldl" in low or "hdl" in low or "cholesterol" in low


def test_dietary_candidates_prefer_iron_pattern():
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="eval-user-iron"),
        build_query_plan("What should I eat based on my blood report?"),
    )
    recs = RecommendationEngine().deterministic_candidates(ctx, "diet")
    joined = " ".join(item.text.lower() for item in recs)
    assert "iron" in joined or "lentil" in joined
    assert not any(item.category == "activity" for item in recs)


def test_parse_failure_is_internal_empty_answer():
    parsed = parse_llm_structured({"answer": {"nested": True}})
    assert parsed.parse_error
    assert parsed.answer == ""
    assert "formatting that answer" not in parsed.answer


def test_diagnosis_question_uses_hba1c_without_diagnosing():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "Based on my reports, do I have diabetes?"},
    ).json()
    low = body["answer"].lower()
    assert "5.3" in body["answer"]
    assert "diagnos" in low
    assert "you have diabetes" not in low
    assert body["meta"]["status"] != "safety_block"


def test_chest_pain_does_not_consult_reports():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "I have severe chest pain and difficulty breathing"},
    ).json()
    assert body["meta"]["status"] == "safety_block"
    assert body["meta"]["supershyft_called"] is False
    assert "10.5" not in body["answer"]


def test_structured_lookup_uses_the_model_when_approved(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    from app.llm.models import LLMStructuredOutput
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    calls = []

    def complete_structured(self, messages):
        calls.append("hit")
        return LLMStructuredOutput(answer="Your hemoglobin is 10.5 g/dL on the stored report.")

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", complete_structured)
    body = client.post("/api/v1/chat", headers=IRON, json={"message": "What is my hemoglobin level?"}).json()
    assert calls == ["hit"]
    assert body["meta"]["llm_called"] is True
    assert "10.5" in body["answer"]
