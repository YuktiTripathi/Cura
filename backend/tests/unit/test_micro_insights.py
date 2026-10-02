from app.contracts.blood import BloodMarker
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.micro_insights import compose_micro_insight


def _context(marker: BloodMarker) -> HealthContext:
    return HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[marker],
    )


def test_micro_insight_describes_report_range_without_llm():
    context = _context(BloodMarker(
        id="1", key="hdl", name="HDL", value=42, unit="mg/dL",
        reference_low=40, reference_high=60, flag=MarkerFlag.normal,
    ))
    plan = QueryPlan(intent=IntentType.latest_result, knowledge_scope=KnowledgeScope.personal, needs_blood=True)
    text = compose_micro_insight(plan=plan, context=context, presentation=None, llm_called=False)
    assert text
    assert "reference range" in text
    assert "lower end" in text


def test_micro_insight_is_not_added_after_llm_reasoning():
    context = _context(BloodMarker(id="1", key="ldl", name="LDL", value=140, unit="mg/dL", flag=MarkerFlag.high))
    plan = QueryPlan(intent=IntentType.latest_result, knowledge_scope=KnowledgeScope.personal, needs_blood=True)
    assert compose_micro_insight(plan=plan, context=context, presentation=None, llm_called=True) is None
