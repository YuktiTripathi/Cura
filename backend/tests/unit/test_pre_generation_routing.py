from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerComplexity, AnswerDepth, AnswerModelTier, IntentType, KnowledgeScope, ReasoningDepth
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.routing.model_tier import promote_for_retrieved_complexity


def test_source_conflict_promotes_standard_to_deep_before_generation():
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        knowledge_scope=KnowledgeScope.personal,
        answer_model_tier=AnswerModelTier.standard_medical,
        model_tier=AnswerModelTier.standard_medical,
        needs_cross_source=True,
    )
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        source_conflicts=[{"metric": "ldl", "name": "LDL", "values": []}],
    )
    promoted = promote_for_retrieved_complexity(plan, context)
    assert promoted.answer_model_tier == AnswerModelTier.deep_medical_reasoning
    assert promoted.complexity == AnswerComplexity.high
    assert promoted.reasoning_depth == ReasoningDepth.deep
    assert "pre_generation_deep_promotion" in promoted.model_selection_reasons


def test_simple_single_marker_interpretation_stays_standard():
    plan = QueryPlan(
        intent=IntentType.blood_marker_explanation,
        knowledge_scope=KnowledgeScope.personal,
        answer_model_tier=AnswerModelTier.standard_medical,
        model_tier=AnswerModelTier.standard_medical,
    )
    context = HealthContext(
        intent=plan.intent,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=[BloodMarker(id="1", key="hdl", name="HDL", value=42)],
    )
    promoted = promote_for_retrieved_complexity(plan, context)
    assert promoted.answer_model_tier == AnswerModelTier.standard_medical
