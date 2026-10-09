from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan


def test_general_heart_question_keeps_general_objective_but_requests_scoped_context():
    plan = build_query_plan("What is heart health?")
    assert plan.intent == IntentType.general_health_question
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.needs_general is True
    assert plan.general_personalization is True
    assert plan.needs_supershyft is True
    assert set(plan.requested_metrics) & {"ldl", "hdl", "cardiac_health"}
    assert plan.semantic_scoped is True


def test_unrelated_general_question_does_not_fetch_personal_context():
    plan = build_query_plan("Why do people have fingerprints?")
    assert plan.intent == IntentType.general_health_question
    assert plan.general_personalization is False
    assert plan.needs_supershyft is False


def test_prompt_teaches_first_and_carries_only_small_verified_context():
    ctx = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
        general_personalization=True,
        requested_entity_codes=["ldl", "cardiac_health"],
        markers=[
            BloodMarker(
                id="m1",
                key="ldl",
                name="LDL",
                value=145,
                unit="mg/dL",
                flag=MarkerFlag.high,
            ),
            BloodMarker(
                id="m2",
                key="vitamin_d",
                name="Vitamin D",
                value=24,
                unit="ng/mL",
                flag=MarkerFlag.low,
            ),
        ],
        bio_ai_risks=[
            BioAIRisk(code="cardiac_health", name="Cardiac Health", score=72, status="elevated")
        ],
    )
    system, user = [item["content"] for item in PromptBuilder().build(ctx, "", "What is heart health?")]
    assert "Answer the general concept first" in system
    assert "VERIFIED RELEVANT PERSONAL CONTEXT" in user
    assert '"name":"LDL"' in user and '"score":72.0' in user
    assert "Bio-AI prediction, not a diagnosis" in user
    assert "Vitamin D" not in user


def test_no_personal_context_does_not_announce_missing_data():
    ctx = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
    )
    user = PromptBuilder().build(ctx, "", "What is hydration?")[1]["content"]
    assert "without mentioning this absence" in user
    assert "VERIFIED RELEVANT PERSONAL CONTEXT" not in user
