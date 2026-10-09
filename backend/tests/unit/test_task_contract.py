from app.contracts.common import IntentType
from app.pipeline.query_planner import build_query_plan
from app.pipeline.task_contract import build_task_contract


def test_insulin_resistance_is_not_a_medication_refusal():
    from app.pipeline.topic_risk import high_risk_topics

    assert "medication" not in high_risk_topics("What is insulin resistance?")
    assert "medication" in high_risk_topics("What dose of insulin should I take?")
    from app.core.config import settings

    assert settings.cura_test_suggestions_enabled is False


def test_modular_prompt_is_smaller_and_selects_the_bio_ai_module(monkeypatch):
    from app.contracts.common import AnswerDepth, KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.core.config import settings
    from app.pipeline.prompt_builder import PromptBuilder, _system_for_mode, SAFETY_INSTRUCTIONS
    from app.pipeline.prompt_modules import CORE, modules_for

    monkeypatch.setattr(settings, "cura_prompt_variant", "modular")
    context = HealthContext(
        intent=build_query_plan("Why is my diabetes risk high?").intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        task_contract=build_query_plan("Why is my diabetes risk high?").task_contract,
        evidence_package={"measurements": [], "bio_ai_risks": [{"name": "Type 2 diabetes", "score": 17}], "missing": []},
    )
    messages = PromptBuilder().build(context, "", "Why is my diabetes risk high?")
    system = messages[0]["content"]
    assert "BIO-AI" in system.upper() or "Bio-AI" in system
    assert "75" in system
    assert len(system) < len(_system_for_mode(SAFETY_INSTRUCTIONS))
    assert len(CORE) < 3200
    assert "BIO_AI_EXPLANATION" in modules_for(context, "Why is my diabetes risk high?") or "forecast" in system
    assert "Type 2 diabetes" not in system
    legacy = _system_for_mode(SAFETY_INSTRUCTIONS)
    assert "answer" in system and "claims" in system
    assert len(legacy) > len(system)
    from app.pipeline.numeric_grounding import unsupported_adjacent_numbers

    package = {"measurements": [{"name": "HDL", "value": 42, "unit": "mg/dL", "reference_low": 40, "reference_high": 60}]}
    assert unsupported_adjacent_numbers("HDL is 42 mg/dL, which is a common lipid.", package) == []
    assert unsupported_adjacent_numbers("About 20 percent of adults have questions.", package) == []
    assert "unsupported_adjacent_number" in unsupported_adjacent_numbers("HDL is 90 mg/dL.", package)
    plan = build_query_plan("Is my HDL good?")
    assert plan.task_contract["response_type"] == "MARKER_LOOKUP"
    assert plan.needs_blood
    assert not plan.needs_general
    plan = build_query_plan("Check my blood report and tell which values are outside range?")
    assert plan.needs_blood
    assert not plan.needs_user_uploaded
    assert plan.knowledge_scope.value == "personal"
    assert "ABNORMAL" in {item.upper() for item in plan.selectors}


def test_bio_ai_score_list_does_not_become_a_blood_lookup():
    plan = build_query_plan("What are my Bio-AI risk scores?")
    assert plan.intent == IntentType.bio_ai_score
    assert plan.needs_bio_ai
    assert not plan.needs_blood


def test_discrepancy_requires_both_sources():
    contract = build_task_contract("My liver enzymes are normal but Bio-AI shows high liver risk. Why?")
    assert contract.response_type == "CROSS_SOURCE_EXPLANATION"
    plan = build_query_plan("My liver enzymes are normal but Bio-AI shows high liver risk. Why?")
    assert plan.needs_blood and plan.needs_bio_ai


def test_source_routing_cannot_drop_a_required_blood_source():
    plan = build_query_plan("Check my blood report and tell which values are outside range?")
    plan.needs_blood = False
    plan.needs_user_uploaded = True
    from app.pipeline.source_routing import apply_source_routing

    kept = apply_source_routing(plan)
    assert kept.needs_blood
    assert not kept.needs_user_uploaded


def test_bio_ai_package_excludes_blood_measurements():
    from app.contracts.bio_ai import BioAIRisk
    from app.contracts.common import AnswerDepth, KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.pipeline.evidence_inventory import assemble_evidence

    plan = build_query_plan("What are my Bio-AI risk scores?")
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[],
        bio_ai_risks=[BioAIRisk(code="diabetes", name="Type 2 diabetes", score=17, status="Healthy")],
    )
    package = assemble_evidence(plan, context)
    assert package.bio_ai_risks
    assert package.measurements == []

    plan = build_query_plan("Why is my diabetes risk high?")
    assert plan.needs_bio_ai and plan.needs_blood
    assert plan.knowledge_scope.value == "personal"


def test_prompt_uses_verified_evidence_once():
    from app.contracts.bio_ai import BioAIRisk
    from app.contracts.blood import BloodMarker
    from app.contracts.common import AnswerDepth, KnowledgeScope, MarkerFlag
    from app.contracts.health_context import HealthContext
    from app.pipeline.evidence_inventory import assemble_evidence
    from app.pipeline.prompt_builder import PromptBuilder

    plan = build_query_plan("What are my Bio-AI risk scores?")
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        task_contract=plan.task_contract,
        markers=[
            BloodMarker(id="1", key="hdl", name="HDL", value=40, unit="mg/dL", flag=MarkerFlag.low),
        ],
        bio_ai_risks=[BioAIRisk(code="type_2_diabetes", name="Type 2 diabetes", score=17, status="Healthy")],
    )
    package = assemble_evidence(plan, context)
    context.evidence_package = package.prompt_payload()
    messages = PromptBuilder().build(context, "earlier turn", plan.raw_message or "")
    body = messages[1]["content"]
    assert "VERIFIED PATIENT EVIDENCE" in body
    assert "PERSONAL HEALTH CONTEXT" not in body
    assert "Type 2 diabetes" in body
    assert "HDL" not in body
    assert package.blocked_answer is None


def test_missing_bio_ai_does_not_invent_scores():
    from app.contracts.common import AnswerDepth, KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.pipeline.evidence_inventory import assemble_evidence

    plan = build_query_plan("What are my Bio-AI risk scores?")
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
    )
    package = assemble_evidence(plan, context)
    assert package.blocked_answer
    assert package.bio_ai_risks == []


def test_quality_gate_flags_a_denied_score_and_an_invented_number():
    from app.contracts.common import AnswerDepth, KnowledgeScope
    from app.contracts.health_context import HealthContext
    from app.pipeline.quality_gate import review_answer

    plan = build_query_plan("What are my Bio-AI risk scores?")
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        evidence_package={
            "bio_ai_risks": [{"name": "Type 2 diabetes", "score": 17, "status": "AVAILABLE"}],
            "measurements": [],
            "missing": [],
        },
    )
    denied = review_answer("Those scores are not available.", plan, context)
    assert "bio_ai_scores_denied" in denied.flags or "requested_score_omitted" in denied.flags
    invented = review_answer("Type 2 diabetes is 88.", plan, context)
    assert "unsupported_number" in invented.flags
