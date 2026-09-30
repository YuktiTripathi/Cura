from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.main import app
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.health_domains import HealthDomainResolver, match_domains
from app.pipeline.planner import EntityResolver, infer_selectors, plan_needs_reasoning
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}

THYROID_PARAPHRASES = [
    "Show me my latest thyroid-related results.",
    "How is my thyroid?",
    "What are my thyroid markers?",
]
KIDNEY_PARAPHRASES = [
    "Are my kidney markers internally consistent?",
    "How is my kidney health?",
    "Look at my kidney results together.",
]
ABNORMAL_PARAPHRASES = [
    "Which abnormalities in my latest report could be related?",
    "Which abnormal values in my latest blood report could be connected?",
]
HIGH_PARAPHRASES = [
    "What markers are high?",
    "Which markers are high in my latest report?",
]
REVIEW_PARAPHRASES = [
    "Review my complete health.",
    "What are my biggest current health concerns?",
]
B12_PARAPHRASES = [
    "My B12 is high. What could explain it?",
    "What could explain my vitamin B12 being high?",
]


def test_thyroid_is_a_health_domain_not_a_biomarker():
    domains = {item.code for item in match_domains("How is my thyroid?")}
    assert "thyroid_health" in domains
    kinds = {item.kind.value for item in EntityResolver().resolve("How is my thyroid?")}
    assert "HEALTH_DOMAIN" in kinds
    assert "thyroid" not in {item.code for item in EntityResolver().resolve("How is my thyroid?") if item.kind.value == "BIOMARKER"}


def test_thyroid_related_results_retrieve_panel():
    for message in THYROID_PARAPHRASES:
        plan = build_query_plan(message)
        assert "thyroid_health" in plan.domains or plan.topic == "thyroid_function"
        assert {"tsh", "t3", "t4"} <= set(plan.requested_metrics) or {"tsh", "t4"} <= set(plan.requested_metrics)
        ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
        keys = {m.key for m in ctx.markers}
        assert {"tsh", "t4"} <= keys or {"tsh", "t3"} <= keys
        low = " ".join(keys).lower()
        assert "thyroid is not available" not in low
        body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
        answer = body["answer"].lower()
        assert "thyroid is not available" not in answer
        assert "tsh" in answer or "2.1" in body["answer"] or "t3" in answer or "t4" in answer


def test_kidney_markers_expand_and_interpret():
    for message in KIDNEY_PARAPHRASES:
        plan = build_query_plan(message)
        assert "kidney_health" in plan.domains or plan.topic == "kidney_function"
        assert "creatinine" in plan.requested_metrics
        assert "egfr" in plan.requested_metrics
        assert plan_needs_reasoning(plan)
        ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
        keys = {m.key for m in ctx.markers}
        assert "creatinine" in keys
        assert "egfr" in keys
        body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
        assert "that marker is not available" not in body["answer"].lower()
        assert "0.92" in body["answer"] or "creatinine" in body["answer"].lower()


def test_abnormalities_use_selector_not_a_diagnosis_handler():
    for message in ABNORMAL_PARAPHRASES:
        plan = build_query_plan(message)
        assert "ABNORMAL" in plan.selectors
        assert plan.needs_blood
        ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
        flags = {getattr(m.flag, "value", m.flag) for m in ctx.markers}
        assert flags <= {"high", "low", "critical"} or not ctx.markers
        assert any(m.key in {"ldl", "triglycerides", "vitamin_d", "vitamin_b12", "fasting_blood_glucose"} for m in ctx.markers)
        body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
        assert body["meta"].get("status") != "safety_block"
        assert "diagnosis_request" not in (body["meta"].get("safety_flags") or [])


def test_high_selector_is_not_a_diagnosis():
    for message in HIGH_PARAPHRASES:
        plan = build_query_plan(message)
        assert "HIGH" in plan.selectors
        assert plan.needs_blood
        body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
        assert body["meta"].get("status") != "safety_block"
        assert "ldl" in body["answer"].lower() or "138" in body["answer"] or "high" in body["answer"].lower()


def test_questionnaire_plus_abnormal_labs():
    message = "My questionnaire says I exercise moderately and sleep 7–9 hours. Is there still anything in my labs worth attention?"
    plan = build_query_plan(message)
    assert plan.needs_questionnaire or "questionnaire" in (plan.data_sources or [])
    assert plan.needs_blood
    assert "ABNORMAL" in plan.selectors
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert ctx.markers


def test_b12_explanation_reaches_reasoner(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    calls = []

    def fake_structured(self, messages):
        calls.append(messages)
        from app.llm.models import LLMStructuredOutput

        return LLMStructuredOutput(answer="B12 can be high for several non-diagnostic reasons.", claims=[], follow_up_questions=[])

    monkeypatch.setattr(OpenAICompatibleLLMClient, "complete_structured", fake_structured)
    for message in B12_PARAPHRASES:
        calls.clear()
        plan = build_query_plan(message)
        assert "vitamin_b12" in plan.requested_metrics
        assert plan_needs_reasoning(plan)
        body = client.post("/api/v1/chat", headers=H, json={"message": message}).json()
        assert "154" in body["answer"] or "b12" in body["answer"].lower()
        assert calls or body["meta"].get("llm_called") is True


def test_complete_health_is_global_scope():
    for message in REVIEW_PARAPHRASES:
        plan = build_query_plan(message)
        assert "overall_health" in plan.domains or plan.needs_blood
        assert plan.needs_blood and plan.needs_bio_ai


def test_missing_ferritin_does_not_dump_report():
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is my ferritin?"}).json()
    low = body["answer"].lower()
    assert "ferritin" in low
    assert "138" not in body["answer"]
    assert "ldl" not in low
    assert "not available" in low or "not present" in low or "couldn't find" in low or "not found" in low


def test_what_does_thyroid_do_is_general():
    plan = build_query_plan("What does thyroid do?")
    assert not plan.needs_personal_data
    body = client.post("/api/v1/chat", headers=H, json={"message": "What does thyroid do?"}).json()
    assert body["meta"].get("supershyft_called") is not True
    assert "12.6" not in body["answer"]


def test_lifestyle_does_not_search_blood_markers():
    plan = build_query_plan("How is my lifestyle?")
    assert "lifestyle_recovery" in plan.domains
    assert not plan.needs_blood
    assert plan.needs_questionnaire or plan.needs_lifestyle or plan.needs_profile


def test_domain_expansion_keeps_optional_missing_separate():
    expansion = HealthDomainResolver().expand("How is my thyroid?")
    assert "tsh" in expansion.primary or "t4" in expansion.primary
    optional = set(expansion.supporting + expansion.all_optional())
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        build_query_plan("How is my thyroid?"),
    )
    assert ctx.markers
    missing_keys = {item.key for item in ctx.missing}
    assert "thyroid" not in missing_keys
    assert "thyroid_health" not in missing_keys


def test_selectors_are_independent_of_domains():
    selectors = infer_selectors("Which markers are high in my latest report?")
    assert any(item.value == "HIGH" for item in selectors)
    plan = build_query_plan("Which markers are high in my latest report?")
    assert "HIGH" in plan.selectors
    assert "type_2_diabetes" not in plan.requested_metrics
