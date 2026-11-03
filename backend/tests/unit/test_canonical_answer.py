"""Rich mode keeps the safety-checked answer, and follow-ups stay on topic."""

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.llm.models import LLMStructuredOutput
from app.pipeline.composer import ResponseComposer
from app.pipeline.followup_generator import on_topic
from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS
from app.pipeline.query_planner import build_query_plan
from app.pipeline.service import _topic_follow_ups
from app.contracts.followup import FollowUpSuggestion


def _ctx() -> HealthContext:
    return HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
    )


def test_rich_compose_keeps_every_paragraph():
    approved = "Your CRP is mildly above the report range.\n\nThis can happen with inflammation. It is not a diagnosis."
    text, _, presentation = ResponseComposer().compose(
        approved,
        plan=QueryPlan(intent=IntentType.latest_result, raw_message="What does my CRP mean?", needs_blood=True, topic="crp"),
        context=_ctx(),
        llm_result=LLMStructuredOutput(answer="UNSAFE original that must not be shown."),
    )
    assert text == approved
    assert presentation.summary == approved
    assert presentation.overall_summary is None
    assert "UNSAFE" not in text


def test_crp_follow_ups_drop_hba1c_from_either_source():
    message = "What is CRP?"
    answer = "CRP is a protein that can rise with inflammation."
    mixed = [
        "Can a recent infection temporarily raise my CRP?",
        "Which fruits are suitable for my HbA1c?",
        "Can a recent infection temporarily raise my CRP?",
    ]
    assert on_topic(mixed, message, answer) == ["Can a recent infection temporarily raise my CRP?"]
    kept = _topic_follow_ups(
        [FollowUpSuggestion(text=item, category="suggested") for item in mixed],
        message,
        answer,
    )
    assert [item.text for item in kept] == ["Can a recent infection temporarily raise my CRP?"]


def test_personal_prompt_follow_up_rules_agree():
    assert "up to 4" in SAFETY_INSTRUCTIONS
    assert "2 or 3," not in SAFETY_INSTRUCTIONS
    assert "Do not force every answer into bullets" in SAFETY_INSTRUCTIONS
    assert "The whole answer is bullets. Every line starts with" not in SAFETY_INSTRUCTIONS


def test_internal_codes_are_removed_from_prose():
    from app.pipeline.presentation import sanitize_internal_ids

    text = "Oxidative stress is a higher group (bioai.oxidative_stress) on this report."
    assert "bioai." not in sanitize_internal_ids(text)
    assert "Oxidative stress" in sanitize_internal_ids(text)


def test_general_question_gets_topic_follow_ups():
    from app.pipeline.followup_generator import general_continuations, on_topic

    chips = general_continuations("What is insulin resistance?")
    assert chips
    assert len(chips) <= 3
    kept = on_topic(chips, "What is insulin resistance?", "Insulin resistance means cells respond less to insulin.")
    assert kept


def test_general_question_does_not_require_personal_data():
    plan = build_query_plan("What is CRP?")
    assert plan.needs_personal_data is False
