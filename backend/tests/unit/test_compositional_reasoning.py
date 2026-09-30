from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.core.config import settings
from app.main import app
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.derived import attach_derived_facts
from app.pipeline.planner import EntityResolver, build_task_plan, plan_needs_reasoning
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry

client = TestClient(app)
IRON = {"X-Cura-User-Id": "eval-user-iron"}
H1 = {"X-Cura-User-Id": "demo-user-001"}

PATTERN_PARAPHRASES = [
    "My Hb is 10.5, my MCV is low, and my Mentzer index is below 13. Is this a pattern in my results?",
    "Looking at my hemoglobin, my MCV, and a Mentzer index below 13, are these connected in my labs?",
    "Do my haemoglobin, mean corpuscular volume, and Mentzer index below 13 have something in common?",
]
METABOLIC_PARAPHRASES = [
    "Look at my glucose, my HbA1c, my triglycerides, my HDL, and BMI or waist if you have them. What is the overall metabolic picture?",
    "How are my fasting glucose, HbA1c, triglycerides, and HDL connected in my results?",
    "Can you review my glucose, my A1c, my TG, my HDL, and my waist together?",
]
REVIEW_PARAPHRASES = [
    "Please review my complete health using all available sources. What has changed, what is connected, what should I discuss with a doctor, and what information is missing?",
    "Give me a bigger-picture review of my blood, Bio-AI, and questionnaire: everything that changed, commonalities, doctor priorities, and gaps.",
    "Comprehensive overview of my blood, Bio-AI, and questionnaire: history, connections, priorities, and missing data.",
]


def test_entity_resolver_keeps_every_lab_and_stated_mentzer():
    entities = EntityResolver().resolve(
        "My Hb is low, MCV is low, and Mentzer index is below 13. Is this a pattern?"
    )
    codes = {item.code for item in entities}
    assert {"hemoglobin", "mcv", "mentzer"} <= codes
    stated = [item for item in entities if item.stated]
    assert any(item.code == "mentzer" and item.stated_value == 13 for item in stated)


def test_entity_resolver_keeps_metabolic_cluster():
    codes = {
        item.code
        for item in EntityResolver().resolve(
            "Look at my glucose, HbA1c, triglycerides, HDL, and waist."
        )
    }
    assert {"glucose", "hba1c", "triglycerides", "hdl", "waist"} <= codes or {
        "fasting_blood_glucose",
        "hba1c",
        "triglycerides",
        "hdl",
        "waist",
    } <= codes


def test_planner_does_not_collapse_to_first_lab():
    for message in PATTERN_PARAPHRASES:
        plan = build_query_plan(message)
        assert "hemoglobin" in plan.requested_metrics
        assert "mcv" in plan.requested_metrics
        assert "mentzer" in plan.requested_metrics
        assert plan_needs_reasoning(plan)
        ops = {item.upper() for item in plan.operations}
        assert ops & {"CORRELATE", "IDENTIFY_PATTERN", "INTERPRET", "PERSONAL_INTERPRETATION"}


def test_health_scenario_is_not_hijacked_for_named_sources():
    plan = build_query_plan(
        "Give me a comprehensive overview using my blood report, Bio-AI, questionnaire, and goals."
    )
    assert plan.needs_blood and plan.needs_bio_ai and plan.needs_questionnaire and plan.needs_goals
    assert plan.intent.value != "questionnaire_lookup"
    ops = {item.upper() for item in plan.operations}
    assert "SUMMARIZE" in ops or plan.operation == "SUMMARIZE"


def test_pattern_paraphrases_retrieve_all_measured_entities():
    principal = AuthenticatedPrincipal(subject_id="eval-user-iron")
    builder = ContextBuilder(build_registry())
    for message in PATTERN_PARAPHRASES:
        plan = build_query_plan(message)
        ctx = builder.build(principal, plan)
        keys = {m.key for m in ctx.markers}
        assert "hemoglobin" in keys
        assert "mcv" in keys
        stated = {(row.fact or "").lower() for row in ctx.user_stated}
        derived = {(row.fact or "").lower() for row in ctx.derived}
        assert "mentzer" in stated or "mentzer" in derived
        assert all((row.fact_type.value if hasattr(row.fact_type, "value") else row.fact_type) != "MEASURED_DATA" for row in ctx.user_stated)
        body = client.post("/api/v1/chat", headers=IRON, json={"message": message}).json()
        low = body["answer"].lower()
        assert "10.5" in body["answer"]
        assert "72" in body["answer"]
        assert "mentzer" in low
        assert "diagnos" not in low or "not a diagnosis" in low or "cannot diagnose" in low or "can't diagnose" in low
        assert "user-stated" in low or "you stated" in low or "derived" in low


def test_metabolic_cluster_does_not_collapse_to_one_marker():
    principal = AuthenticatedPrincipal(subject_id="eval-user-iron")
    builder = ContextBuilder(build_registry())
    for message in METABOLIC_PARAPHRASES:
        plan = build_query_plan(message)
        ctx = builder.build(principal, plan)
        keys = {m.key for m in ctx.markers}
        missing = {item.key for item in ctx.missing}
        for code in ("hba1c", "triglycerides", "hdl"):
            assert code in keys or code in missing
        assert "fasting_blood_glucose" in keys or "glucose" in keys or "glucose" in missing or "fasting_blood_glucose" in missing
        body = client.post("/api/v1/chat", headers=IRON, json={"message": message}).json()
        low = body["answer"].lower()
        assert "5.3" in body["answer"] or "hba1c" in low
        assert "triglyceride" in low or "82.9" in body["answer"] or "80" in body["answer"]
        assert "hdl" in low or "51" in body["answer"] or "52" in body["answer"]
        assert low.count("only") < 3


def test_broad_review_uses_multiple_sources_and_discloses_gaps():
    message = REVIEW_PARAPHRASES[0]
    plan = build_query_plan(message)
    assert plan.needs_blood and plan.needs_bio_ai
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="eval-user-iron"),
        plan,
    )
    assert ctx.markers
    assert ctx.comparisons or plan.history or ctx.bio_ai_risks
    body = client.post("/api/v1/chat", headers=IRON, json={"message": message}).json()
    meta = body["meta"]
    outcomes = {row["source"]: row["status"] for row in meta.get("source_outcomes") or []}
    assert meta.get("supershyft_called") is True
    assert "blood_reports" in outcomes or plan.needs_blood
    low = body["answer"].lower()
    assert "10.5" in body["answer"] or "haemoglobin" in low or "hemoglobin" in low
    assert any(token in low for token in ("missing", "not available", "not found", "gap", "questionnaire", "goal"))


def test_lookup_only_single_marker_stays_deterministic(monkeypatch):
    monkeypatch.setattr(settings, "enable_llm", True)
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    calls = []
    monkeypatch.setattr(
        OpenAICompatibleLLMClient,
        "complete_structured",
        lambda self, messages: calls.append("hit") or (_ for _ in ()).throw(AssertionError("should not call LLM")),
    )
    body = client.post("/api/v1/chat", headers=IRON, json={"message": "What is my hemoglobin level?"}).json()
    assert calls == []
    assert "10.5" in body["answer"]
    assert body["meta"]["llm_called"] is False


def test_derived_mentzer_from_mcv_and_rbc():
    plan = build_query_plan("What is my Mentzer index based on MCV and RBC?")
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="eval-user-iron"),
        plan,
    )
    attach_derived_facts(ctx, plan)
    mentzer = next((row for row in ctx.derived if row.fact == "mentzer"), None)
    assert mentzer is not None
    assert abs(float(mentzer.value) - (72.0 / 4.8)) < 0.05
