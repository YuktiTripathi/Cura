from fastapi.testclient import TestClient

from app.contracts.common import IntentType, KnowledgeScope
from app.core.copy import PERSONAL_DATA_UNAVAILABLE
from app.main import app
from app.pipeline.intent import classify_intent, requires_personal_record
from app.pipeline.query_planner import build_query_plan

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}

GENERAL_EXAMPLES = [
    "What is LDL?",
    "What is HDL?",
    "What is the difference between HDL and LDL?",
    "What lifestyle changes can help lower LDL?",
    "What foods can help lower cholesterol?",
    "Why can LDL become high?",
    "What are common reasons HDL can be low?",
    "How does exercise affect cholesterol?",
    "What is a healthy cholesterol level?",
    "What does high LDL generally mean?",
    "What are the common causes of high cholesterol?",
]

PERSONAL_EXAMPLES = [
    "What is my LDL?",
    "What is my cholesterol level?",
    "Is my LDL high?",
    "What was my LDL last time?",
    "Has my cholesterol improved?",
    "Compare my latest and previous cholesterol.",
    "What does my blood report say about LDL?",
    "Based on my LDL result, what should I do?",
    "What lifestyle changes should I make based on my LDL level?",
    "What should I do about my LDL of 165?",
    "Show me my cholesterol trend.",
]


def test_general_examples_keep_general_objective_with_optional_scoped_context():
    for msg in GENERAL_EXAMPLES:
        assert requires_personal_record(msg) is False, msg
        plan = build_query_plan(msg)
        assert plan.intent == IntentType.general_health_question, msg
        assert plan.knowledge_scope == KnowledgeScope.general, msg
        assert plan.general_personalization, msg
        assert plan.needs_supershyft, msg


def test_personal_examples_require_records():
    for msg in PERSONAL_EXAMPLES:
        assert requires_personal_record(msg) is True, msg
        plan = build_query_plan(msg)
        assert plan.needs_personal_data, msg
        assert plan.knowledge_scope == KnowledgeScope.personal, msg


def test_hdl_ldl_then_personal_lifestyle_followup_uses_member_data():
    # "...lower MY LDL levels?" asks for advice for this member: the semantic planner marks
    # personalization REQUIRED (same answer would differ per member), so records are read.
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is the difference between HDL and LDL?"})
    body = first.json()
    assert body["meta"]["intent"] == "general_health_question"
    assert body["meta"]["intent"] == "general_health_question"
    cid = body["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={
            "conversation_id": cid,
            "message": "What lifestyle changes can help lower my LDL levels?",
        },
    ).json()
    assert second["meta"]["requires_personal_data"] is True
    assert second["meta"]["supershyft_called"] is True
    assert PERSONAL_DATA_UNAVAILABLE not in second["answer"]


def test_my_ldl_then_how_can_i_lower_it_can_stay_personal():
    plan = build_query_plan("How can I lower it?", follow_up_topic="ldl", prior_personal=True)
    assert plan.needs_personal_data
    assert plan.topic == "ldl"


def test_my_ldl_then_generic_lifestyle_without_pronoun_is_general():
    plan = build_query_plan(
        "What lifestyle changes can help lower LDL?",
        follow_up_topic="ldl",
        prior_personal=True,
    )
    assert plan.intent == IntentType.general_health_question
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.general_personalization


def test_is_it_high_after_personal_is_personal():
    plan = build_query_plan("Is it high?", follow_up_topic="ldl", prior_personal=True)
    assert plan.needs_personal_data


def test_previous_after_personal_is_historical():
    plan = build_query_plan("What was it previously?", follow_up_topic="ldl", prior_personal=True)
    assert plan.intent == IntentType.previous_result
    assert plan.history
    assert plan.needs_personal_data


def test_the_previous_one_after_personal_is_historical():
    plan = build_query_plan("What was the previous one?", follow_up_topic="ldl", prior_personal=True)
    assert plan.intent == IntentType.previous_result
    assert plan.history
    assert plan.needs_personal_data


def test_why_it_high_after_general_stays_general():
    intent, topic, *_ = classify_intent("Why can it become high?", follow_up_topic="ldl", prior_personal=False)
    assert intent == IntentType.general_health_question
    plan = build_query_plan("Why can it become high?", follow_up_topic="ldl", prior_personal=False)
    assert not plan.needs_personal_data


def test_improve_my_hdl_after_general_difference_is_personal():
    # Advice on improving the member's own HDL is personalized (spec: same question,
    # different useful answer per member). The earlier general turn does not force it general.
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is the difference between HDL and LDL?"})
    cid = first.json()["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "How can I improve my HDL?"},
    ).json()
    assert second["meta"]["requires_personal_data"] is True
    assert PERSONAL_DATA_UNAVAILABLE not in second["answer"]
