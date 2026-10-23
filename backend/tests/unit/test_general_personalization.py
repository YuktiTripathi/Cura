from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.conversation_experience import ResponseBlockKind
from app.pipeline.conversation_experience import build_experience_plan
from app.pipeline.general_personalization import limit_general_personal_context
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.health_topics import evidence_bio_ai_for, extract_topics
from app.pipeline.query_planner import build_query_plan


def test_general_heart_question_requests_narrow_optional_personal_context():
    plan = build_query_plan("What is heart health?")
    assert plan.intent == IntentType.general_health_question
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.needs_general is True
    assert plan.general_personalization is True
    assert plan.needs_supershyft is False
    assert plan.needs_blood is False


def test_unrelated_general_question_does_not_fetch_personal_context():
    plan = build_query_plan("Why do people have fingerprints?")
    assert plan.intent == IntentType.general_health_question
    assert plan.general_personalization is False
    assert plan.needs_supershyft is False


def test_single_biomarker_definition_keeps_a_small_personal_connection():
    plan = build_query_plan("What is LDL?")
    assert plan.intent == IntentType.general_health_question
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.general_personalization is True
    assert plan.needs_blood is False
    assert plan.needs_supershyft is False


def test_general_and_personal_heart_questions_use_different_context():
    general = build_query_plan("What is heart health?")
    personal = build_query_plan("How is my heart health?")

    assert general.knowledge_scope == KnowledgeScope.general
    assert general.general_personalization
    assert not general.needs_personal_data
    assert personal.knowledge_scope == KnowledgeScope.personal
    assert personal.needs_blood and personal.needs_bio_ai


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
    assert "model-estimated prediction, not a diagnosis" in user
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


def test_explicit_general_only_request_never_reads_personal_records():
    plan = build_query_plan("Explain heart health without using my reports.")

    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.general_personalization
    assert not plan.needs_personal_data


def test_general_experience_does_not_render_missing_patient_results():
    plan = build_query_plan("What is heart health?")
    context = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
    )
    experience = build_experience_plan("What is heart health?", plan, context)

    assert ResponseBlockKind.missing_info not in experience.blocks


def test_general_personal_context_is_capped_and_prioritizes_significance():
    context = HealthContext(
        intent=IntentType.general_health_question,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.general,
        general_personalization=True,
        markers=[
            BloodMarker(id="ldl", key="ldl", name="LDL", value=160, unit="mg/dL", flag=MarkerFlag.high),
            BloodMarker(id="hdl", key="hdl", name="HDL", value=51, unit="mg/dL", flag=MarkerFlag.normal),
            BloodMarker(id="tg", key="triglycerides", name="Triglycerides", value=110, unit="mg/dL", flag=MarkerFlag.normal),
        ],
        bio_ai_risks=[
            BioAIRisk(code="cardiac_health", name="Cardiac health", score=65, status="elevated"),
            BioAIRisk(code="hypertension", name="Hypertension", score=12, status="low"),
        ],
    )

    limit_general_personal_context(context)

    assert len(context.markers) + len(context.bio_ai_risks) <= 3
    assert {item.key for item in context.markers} >= {"ldl"}
    assert {item.code for item in context.bio_ai_risks} >= {"cardiac_health"}


def test_supported_general_concepts_use_registry_without_separate_handlers():
    expected = {
        "What is heart health?": {"cardiac_health"},
        "What is diabetes?": {"type_2_diabetes"},
        "What is fatty liver?": {"nafld"},
        "What is obesity?": {"obesity"},
        "What is hypertension?": {"hypertension"},
        "What is dyslipidemia?": {"dyslipidemia"},
        "What is thyroid health?": {"thyroid"},
        "What is oxidative stress?": {"oxidative_stress"},
        "What is PCOS?": {"pcos"},
        "What is metabolic syndrome?": {"metabolic_syndrome"},
    }

    for question, risk_codes in expected.items():
        plan = build_query_plan(question)
        assert plan.knowledge_scope == KnowledgeScope.general, question
        assert not plan.needs_supershyft, question
        topics = extract_topics(question)
        assert risk_codes <= set(evidence_bio_ai_for(topics)), question
