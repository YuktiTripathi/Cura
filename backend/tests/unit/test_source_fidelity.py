"""Report explanations stay on the source the user asked for."""

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, QuerySource
from app.contracts.context_ref import ContextRef
from app.contracts.facts import FactKind
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.general_personalization import enforce_general_only_request
from app.pipeline.prompt_builder import _fact_kind_blocks
from app.pipeline.query_planner import build_query_plan
from app.contracts.facts import ProvenancedFact


def test_blood_explanation_drops_a_router_that_also_selected_bio_ai():
    contaminated = QueryPlan(
        intent=IntentType.report_explanation,
        source=QuerySource.mixed,
        knowledge_scope=KnowledgeScope.personal,
        needs_blood=True,
        needs_bio_ai=True,
        needs_supershyft=True,
        raw_message="Help me understand my latest blood report",
    )
    plan = enforce_general_only_request(contaminated, contaminated.raw_message)
    spec = plan.task_contract or {}
    assert spec["primary_source"] == "blood_report"
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is False
    assert plan.source == QuerySource.blood


def test_bio_explanation_does_not_require_the_blood_report():
    plan = enforce_general_only_request(
        QueryPlan(
            intent=IntentType.bio_ai_explanation,
            source=QuerySource.mixed,
            knowledge_scope=KnowledgeScope.personal,
            needs_blood=True,
            needs_bio_ai=True,
            raw_message="Help me understand my latest Bio-AI report and its main findings.",
        ),
        "Help me understand my latest Bio-AI report and its main findings.",
    )
    assert plan.task_contract["primary_source"] == "bio_ai"
    assert plan.needs_bio_ai is True
    assert plan.needs_blood is False


def test_overall_health_may_use_both_sources():
    plan = build_query_plan("How is my overall health?")
    assert plan.task_contract["primary_source"] == "mixed"
    assert plan.needs_blood and plan.needs_bio_ai


def test_homepage_blood_hint_is_a_blood_report_explanation():
    plan = build_query_plan(
        "Help me understand my latest blood report",
        context_ref=ContextRef(type="blood_report", source="supershyft"),
    )
    assert plan.intent == IntentType.report_explanation
    assert plan.needs_bio_ai is False
    assert plan.task_contract["primary_source"] == "blood_report"


def test_cholesterol_advice_is_not_a_whole_report_summary():
    from app.pipeline.narrative import wants_narrative_summary

    plan = build_query_plan("How to manage my cholesterol?")
    spec = plan.task_contract or {}
    assert spec["goal"] == "advise"
    assert spec["broad_summary"] is False
    assert wants_narrative_summary("How to manage my cholesterol?", plan) is False
    assert "ldl" in plan.requested_metrics
    assert build_query_plan("How is my overall health?").task_contract["broad_summary"] is True


def test_bio_ai_scores_are_not_labeled_as_measured_results():
    context = HealthContext(
        intent=IntentType.report_explanation,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
        facts=[
            ProvenancedFact(
                fact="ldl",
                value=140,
                source="supershyft",
                subject_id="u",
                fact_type=FactKind.measured_data,
            ),
            ProvenancedFact(
                fact="dyslipidemia",
                value=70,
                source="supershyft",
                subject_id="u",
                fact_type=FactKind.bio_ai_assessment,
            ),
        ]
    )
    block = _fact_kind_blocks(context)
    measured = block.split("BIO-AI DATA JSON")[0]
    assert "dyslipidemia" not in measured
    assert "ldl" in measured
