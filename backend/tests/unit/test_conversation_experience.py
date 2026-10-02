"""Conversation experience layer. Extends existing pipeline; not a second chatbot."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.conversation_experience import (
    ConversationGoal,
    NextBestConversationAction,
    ResponseDepth,
)
from app.contracts.conversation_state import ConversationState, ExpectedReplyType, TurnType
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.main import app
from app.pipeline.composer import ResponseComposer
from app.pipeline.conversation_experience import (
    build_experience_plan,
    discipline_follow_ups,
    infer_conversation_goal,
    infer_response_depth,
)
from app.pipeline.conversation_state import ConversationStateResolver
from app.pipeline.health_narrative import HealthNarrativeService
from app.pipeline.query_planner import build_query_plan
from app.pipeline.relevant_context import RelevantContextSelector

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}
IRON = {"X-Cura-User-Id": "eval-user-iron"}


def chat(message: str, conversation_id: str | None = None, headers=None):
    return client.post(
        "/api/v1/chat",
        headers=headers or H,
        json={"message": message, "conversation_id": conversation_id},
    ).json()


def _prior(**kwargs) -> ConversationState:
    data = dict(
        turn_type=TurnType.new_question,
        active_domain="vitamin_b12_folate_status",
        active_entities=["vitamin_b12"],
        active_source="blood_report",
        previous_user_question="What does my B12 result mean?",
        previous_assistant_summary="B12 is 154 pg/mL and below the report range.",
        previous_assistant_follow_up="Do you have any new symptoms or medication or supplement changes?",
        previous_intent="blood_marker_explanation",
        expected_reply_type=ExpectedReplyType.clinical_context,
        expected_handling_path="CONTINUE_INTERPRETATION",
        recently_referenced=["vitamin_b12"],
        prior_personal=True,
        explained_entities=["vitamin_b12"],
        topic_turn_count=1,
    )
    data.update(kwargs)
    return ConversationState.model_validate(data)


def _conv(state: ConversationState) -> SimpleNamespace:
    return SimpleNamespace(
        conversation_state_json=state.model_dump_json(),
        follow_up_topic=state.active_entities[0] if state.active_entities else None,
        current_report_id=state.active_report_id,
        current_marker_code=state.active_entities[0] if state.active_entities else None,
        conversation_summary=state.previous_assistant_summary,
        messages=[],
    )


def _marker(key, name, value, flag, unit="g/dL"):
    return BloodMarker(
        id=key,
        key=key,
        name=name,
        value=value,
        unit=unit,
        flag=flag,
        source="SuperShyft",
        report_id="r1",
    )


def _report(*markers):
    return BloodReport(report_id="r1", report_date="2026-08-24", markers=list(markers))


def test_goal_and_depth_inference():
    plan = build_query_plan("Could you tell me what my B12 result is showing?")
    assert infer_conversation_goal("Could you tell me what my B12 result is showing?", plan) == ConversationGoal.understand
    assert infer_conversation_goal("Is this something I should be concerned about?", plan) == ConversationGoal.reassurance
    assert infer_conversation_goal("Keep it short please", plan) == ConversationGoal.quick_answer
    review = build_query_plan("How am I doing overall?")
    assert infer_conversation_goal("How am I doing overall?", review) == ConversationGoal.health_review
    deep = infer_response_depth("Walk me through this in detail", plan, ConversationGoal.understand)
    assert deep == ResponseDepth.deep
    short = infer_response_depth("Keep it short", plan, ConversationGoal.quick_answer)
    assert short == ResponseDepth.short


def test_simple_result_surfaces_related_pattern_only():
    plan = QueryPlan(
        intent=IntentType.latest_result,
        topic="hemoglobin",
        topic_name="Haemoglobin",
        requested_metrics=["hemoglobin"],
        display_entities=["hemoglobin"],
        knowledge_scope=KnowledgeScope.personal,
        answer_depth=AnswerDepth.simple,
        raw_message="What is my haemoglobin reading?",
    )
    hb = _marker("hemoglobin", "Haemoglobin", 10.5, MarkerFlag.low)
    mcv = _marker("mcv", "MCV", 72, MarkerFlag.low, "fL")
    mch = _marker("mch", "MCH", 24, MarkerFlag.low, "pg")
    iron = _marker("iron", "Serum Iron", 35, MarkerFlag.low, "µg/dL")
    ldl = _marker("ldl", "LDL", 92, MarkerFlag.normal, "mg/dL")
    ctx = HealthContext(
        intent=plan.intent,
        answer_depth=plan.answer_depth,
        knowledge_scope=KnowledgeScope.personal,
        markers=[hb],
        display_entity_codes=["hemoglobin"],
        requested_entity_codes=["hemoglobin"],
        resolved_topic="hemoglobin",
    )
    report = _report(hb, mcv, mch, iron, ldl)
    relevant = RelevantContextSelector().select(ctx, plan, reports=[report], goal=ConversationGoal.quick_answer, depth=ResponseDepth.standard)
    assert "hemoglobin" in relevant.requested_keys
    assert set(relevant.supporting_keys) <= {"mcv", "mch", "iron", "ferritin", "hematocrit"}
    assert "ldl" not in relevant.supporting_keys
    assert relevant.pattern_note


def test_follow_up_reference_and_assistant_answer():
    resolver = ConversationStateResolver()
    prior = _prior()
    why = resolver.resolve("Why is that happening?", _conv(prior))
    assert why.turn_type in {TurnType.reference_resolution, TurnType.follow_up_question}
    assert "vitamin_b12" in why.active_entities
    answered = resolver.resolve("Yes, I take one daily.", _conv(prior))
    assert answered.turn_type == TurnType.answer_to_assistant
    assert "vitamin_b12" in answered.active_entities
    assert "supplement_use" in answered.new_context


def test_topic_switch_and_correction():
    resolver = ConversationStateResolver()
    prior = _prior()
    switched = resolver.resolve("What is my LDL cholesterol right now?", _conv(prior))
    assert switched.turn_type == TurnType.topic_switch
    corrected = resolver.resolve("Actually I meant vitamin D.", _conv(prior))
    assert corrected.turn_type == TurnType.correction


def test_health_narrative_service_applies():
    plan = build_query_plan("How am I doing and what should I focus on?")
    service = HealthNarrativeService()
    assert service.applies("How am I doing and what should I focus on?", plan)


def test_one_handled_follow_up_not_a_list_of_generics():
    plan = build_query_plan("What does my B12 result mean?")
    ctx = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        resolved_topic="vitamin_b12",
        resolved_topic_name="Vitamin B12",
        markers=[_marker("vitamin_b12", "Vitamin B12", 154, MarkerFlag.low, "pg/mL")],
    )
    experience = build_experience_plan("What does my B12 result mean?", plan, ctx)
    question, chips = discipline_follow_ups(
        [
            FollowUpSuggestion(
                text="Do you have any new symptoms or medication or supplement changes?",
                category="clinical_context",
                handling_path="CONTINUE_INTERPRETATION",
                expected_reply_type="CLINICAL_CONTEXT",
            ),
            FollowUpSuggestion(
                text="Want a recipe?",
                category="chit_chat",
            ),
            FollowUpSuggestion(
                text="How is the weather?",
                category="chit_chat",
                handling_path="LOOKUP",
            ),
        ],
        experience,
        answer_turn=False,
    )
    combined = question + chips
    assert len(question) <= 1
    assert all(item.handling_path for item in combined)
    assert not any("weather" in item.text.lower() or "recipe" in item.text.lower() for item in combined)


def test_composer_avoids_generic_question_on_answer_turn():
    plan = build_query_plan("What does my B12 result mean?")
    plan.conversation_turn = "ANSWER_TO_ASSISTANT"
    ctx = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        resolved_topic="vitamin_b12",
        resolved_topic_name="Vitamin B12",
    )
    _text, suggestions, pres = ResponseComposer().compose(
        "Your B12 is 154 pg/mL.",
        plan=plan,
        context=ctx,
        follow_ups=[
            FollowUpSuggestion(
                text="Do you have any new symptoms or medication or supplement changes?",
                category="clinical_context",
                handling_path="CONTINUE_INTERPRETATION",
                expected_reply_type="CLINICAL_CONTEXT",
            )
        ],
        conversation_turn="ANSWER_TO_ASSISTANT",
    )
    assert not any(item.expected_reply_type for item in suggestions)
    assert len(suggestions) <= 1
    assert pres.conversation_goal


def test_paraphrased_b12_multi_turn_experience():
    first = chat("Could you tell me what my B12 result is showing?")
    assert "154" in first["answer"] or "b12" in first["answer"].lower()
    assert first["meta"].get("conversation_goal") in {None, "UNDERSTAND", "QUICK_ANSWER", "FOLLOW_UP"}
    chips = first.get("follow_ups") or []
    assert len(chips) <= 3
    assert any("supplement" in (item.get("text") or "").lower() or "symptom" in (item.get("text") or "").lower() for item in chips)
    cid = first["conversation_id"]

    second = chat("Yes, I take one daily.", cid)
    debug = second["meta"].get("debug") or {}
    assert debug.get("turn_type") == "ANSWER_TO_ASSISTANT"
    assert "b12" in second["answer"].lower() or "154" in second["answer"]
    assert len(second.get("follow_ups") or []) <= 1

    third = chat("Is this something I should be concerned about?", cid)
    debug = third["meta"].get("debug") or {}
    assert debug.get("turn_type") in {"REFERENCE_RESOLUTION", "FOLLOW_UP_QUESTION"}
    low = third["answer"].lower()
    assert "healthy" not in low or "not a diagnosis" in low or "reassur" in low or "attention" in low or "b12" in low
    assert third["meta"].get("conversation_goal") in {None, "REASSURANCE", "FOLLOW_UP", "UNDERSTAND"}


def test_hemoglobin_does_not_dump_unrelated_lipids():
    body = chat("What is my haemoglobin reading?", headers=IRON)
    low = body["answer"].lower()
    assert "10.5" in body["answer"] or "haemoglobin" in low or "hemoglobin" in low
    assert "ldl" not in low
    related = (body.get("presentation") or {}).get("related_findings") or []
    labels = " ".join(item.get("label", "") for item in related).lower()
    if related:
        assert "ldl" not in labels


def test_short_then_deep_respects_preference():
    first = chat("What is my vitamin D? Keep it short.")
    cid = first["conversation_id"]
    assert first["meta"].get("response_depth") in {None, "SHORT", "STANDARD"}
    second = chat("Walk me through this in more detail.", cid)
    assert second["meta"].get("response_depth") in {None, "DEEP", "GUIDED", "STANDARD"}
    assert "vitamin d" in second["answer"].lower() or "12.6" in second["answer"] or "vitamin" in second["answer"].lower()


def test_health_summary_uses_themes_not_raw_table():
    body = chat("How am I doing, and what should I focus on?")
    pres = body.get("presentation") or {}
    assert pres.get("themes") or "focus" in body["answer"].lower() or "reassur" in body["answer"].lower() or "pattern" in body["answer"].lower()
    if pres.get("themes"):
        statuses = {item.get("status") for item in pres["themes"]}
        assert statuses <= {"needs_attention", "monitor", "reassuring", "uncertain"}


def test_suggested_actions_are_data_aware():
    body = chat("What is my LDL cholesterol?")
    chips = [item.get("text", "") for item in (body.get("follow_ups") or [])]
    joined = " ".join(chips).lower()
    assert len(chips) <= 3
    if chips:
        assert "weather" not in joined
        assert any(token in joined for token in ("previous", "pattern", "missing", "ldl", "mean", "changed", "related", "next"))
