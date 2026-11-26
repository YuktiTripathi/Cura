from datetime import date

from app.biomarkers.metabolic_age_insight import build_metabolic_age_insight
from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.contracts.questionnaire import QuestionnaireAnswer
from app.pipeline.evidence_inventory import assemble_evidence


def _marker(key, value):
    return BloodMarker(id=key, key=key, name=key, value=value, unit="mg/dL", flag=MarkerFlag.normal)


def test_metabolic_age_question_sends_the_card_comparison_and_related_context():
    context = HealthContext(
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        metabolic_age=34,
        profile_age=30,
        bio_report_date="2024-08-01",
        markers=[_marker("hba1c", 5.4), _marker("ldl", 140), _marker("tsh", 2.1)],
        bio_ai_risks=[
            BioAIRisk(code="type_2_diabetes", name="Type 2 Diabetes", score=40, status="Increased Risk"),
            BioAIRisk(code="thyroid", name="Thyroid", score=10, status="Healthy"),
        ],
        questionnaire=[
            QuestionnaireAnswer(response_id="1", assessment_instance_id="a", question_id="1", question_key="physical_activity_frequency", question="How often do you exercise?", value="rarely", response_type="choice", subject_id="m"),
            QuestionnaireAnswer(response_id="2", assessment_instance_id="a", question_id="2", question_key="sleeping_hours", question="How do you sleep?", value="poorly", response_type="choice", subject_id="m"),
            QuestionnaireAnswer(response_id="3", assessment_instance_id="a", question_id="3", question_key="unrelated_mood", question="How is your mood?", value="fine", response_type="choice", subject_id="m"),
        ],
    )
    plan = QueryPlan(intent=IntentType.bio_ai_score, raw_message="What does my metabolic age say about my health?", needs_blood=True, needs_bio_ai=True, needs_questionnaire=True)
    payload = assemble_evidence(plan, context).prompt_payload()
    expected = build_metabolic_age_insight(actual_age=30, metabolic_age=34, assessed_on="2024-08-01", today=date.today())
    comparison = payload["metabolic_comparison"]
    assert comparison["metabolic_age_years"] == 34
    assert comparison["actual_age_years"] == expected.actual_age_years
    assert comparison["direction"] == expected.direction
    assert comparison["difference_years"] == expected.difference_years
    assert comparison["assessed_on"] == "2024-08-01"
    assert "estimated" in comparison["actual_age_basis"]
    keys = {row["key"] for row in payload["measurements"]}
    assert "hba1c" in keys and "ldl" in keys and "tsh" not in keys
    codes = {row["code"] for row in payload["bio_ai_risks"]}
    assert codes == {"type_2_diabetes"}
    habits = {row["key"] for row in payload["questionnaire"]}
    assert habits == {"physical_activity_frequency", "sleeping_hours"}


def test_sleep_question_uses_the_recorded_habit_and_related_results():
    from app.pipeline.query_planner import build_query_plan

    plan = build_query_plan("How does sleep affect my health?")
    assert plan.knowledge_scope.value == "personal"
    assert plan.needs_blood and plan.needs_bio_ai and plan.needs_questionnaire
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[_marker("hba1c", 5.6), _marker("tsh", 2.0)],
        bio_ai_risks=[
            BioAIRisk(code="type_2_diabetes", name="Type 2 Diabetes", score=20, status="Healthy"),
            BioAIRisk(code="pcos", name="PCOS", score=40, status="Increased Risk"),
        ],
        questionnaire=[
            QuestionnaireAnswer(response_id="1", assessment_instance_id="a", question_id="1", question_key="sleeping_hours", question="How long do you sleep?", value="8 hours", response_type="choice", subject_id="m"),
            QuestionnaireAnswer(response_id="2", assessment_instance_id="a", question_id="2", question_key="food_groups", question="Which food groups do you eat?", value="vegetables", response_type="choice", subject_id="m"),
        ],
    )
    payload = assemble_evidence(plan, context).prompt_payload()
    assert {row["key"] for row in payload["measurements"]} == {"hba1c"}
    assert {row["code"] for row in payload["bio_ai_risks"]} == {"type_2_diabetes"}
    assert {row["key"] for row in payload["questionnaire"]} == {"sleeping_hours"}
    general = build_query_plan("How does sleep affect health?")
    assert general.knowledge_scope.value == "general"


def test_missing_metabolic_age_does_not_invent_a_comparison():
    context = HealthContext(
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        profile_age=30,
        markers=[_marker("hba1c", 5.4)],
    )
    plan = QueryPlan(intent=IntentType.bio_ai_score, raw_message="What does my metabolic age say about my health?")
    payload = assemble_evidence(plan, context).prompt_payload()
    assert "metabolic_comparison" not in payload
