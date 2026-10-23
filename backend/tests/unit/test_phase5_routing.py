"""Routing and non-lab document regressions for general vs personal questions."""

from types import SimpleNamespace

from app.contracts.common import IntentType, KnowledgeScope
from app.documents.query_policy import wants_document_summary
from app.pipeline.document_answer import _summary_answer
from app.pipeline.query_planner import build_query_plan


def test_definition_questions_stay_general():
    for message in (
        "What is Vitamin D?",
        "What is LDL cholesterol?",
        "What causes high LDL?",
        "What is HbA1c used to measure?",
    ):
        plan = build_query_plan(message)
        assert plan.intent == IntentType.general_health_question, message
        assert plan.knowledge_scope == KnowledgeScope.general, message
        assert not plan.needs_supershyft, message
        assert not plan.needs_blood, message


def test_personal_ldl_questions_use_records():
    result = build_query_plan("What is my LDL?")
    assert result.needs_personal_data
    why = build_query_plan("Why is my LDL high?")
    assert why.needs_personal_data
    told = build_query_plan("My doctor told me about LDL")
    assert not told.needs_supershyft


def test_pronoun_free_follow_up_stays_general():
    plan = build_query_plan(
        "What lifestyle changes can help lower LDL?",
        follow_up_topic="ldl",
        prior_personal=True,
    )
    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.needs_supershyft


def test_discharge_summary_reaches_the_answer():
    assert wants_document_summary("Summarize this discharge summary")
    row = SimpleNamespace(
        id="doc-1",
        chunks=[SimpleNamespace(text="Discharged on lisinopril 10 mg daily. Follow up in two weeks.")],
    )
    context = SimpleNamespace(document_id="doc-1", structured_facts=[], pageindex_status="absent")
    answer = _summary_answer([row], [context], "Summarize this discharge summary")
    assert "lisinopril" in answer.answer
