"""Cross-source questions leave the single-score fast path. Plain score lookups stay there."""

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.query import QueryPlan
from app.routing.model_tier import _lookup_only, asks_blood_and_score_relationship


def _plan(message: str) -> QueryPlan:
    return QueryPlan(
        raw_message=message,
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        topic="oxidative_stress",
    )


def test_the_three_weak_questions_are_relationships():
    questions = [
        "My report has Creatinine. Does that support or argue with the Oxidative Stress score?",
        "My report has HbA1c. Does that support or argue with the Oxidative Stress score?",
        "How does my HbA1c result sit next to the Bio-AI Dyslipidemia estimate?",
    ]
    for question in questions:
        assert asks_blood_and_score_relationship(question)
        assert _lookup_only(_plan(question), interpret=False, list_only=False, metric_count=1, ops=set()) is False


def test_plain_score_and_blood_lookups_stay_fast():
    assert asks_blood_and_score_relationship("What is my diabetes risk score?") is False
    assert _lookup_only(_plan("What is my diabetes risk score?"), interpret=False, list_only=False, metric_count=1, ops=set()) is True
    assert asks_blood_and_score_relationship("What is my HbA1c?") is False


def test_disagreement_and_missing_relationship_shapes():
    assert asks_blood_and_score_relationship("Why is my diabetes risk high when my blood sugar is normal?")
    assert asks_blood_and_score_relationship("Does creatinine support the Oxidative Stress score?")
    assert asks_blood_and_score_relationship("Do my HbA1c and triglycerides explain the diabetes risk score?")
