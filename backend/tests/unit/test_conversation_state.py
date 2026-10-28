from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.conversation_state import ConversationState, ExpectedReplyType, TurnType
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.main import app
from app.pipeline.composer import ResponseComposer
from app.pipeline.conversation_state import ConversationStateResolver, apply_to_query_plan
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_router import resolve_plan
from app.routing.schemas import JevRoutingState

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def chat(message: str, conversation_id: str | None = None):
    return client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": message, "conversation_id": conversation_id},
    ).json()


def _prior(**kwargs) -> ConversationState:
    data = dict(
        turn_type=TurnType.new_question,
        active_domain="liver_health",
        active_entities=["alt"],
        active_source="blood_report",
        previous_user_question="What does my ALT result mean?",
        previous_assistant_summary="ALT is 22 U/L and within range.",
        previous_assistant_follow_up="Do you have any new symptoms or medication or supplement changes?",
        previous_intent="blood_marker_explanation",
        expected_reply_type=ExpectedReplyType.clinical_context,
        expected_handling_path="CONTINUE_INTERPRETATION",
        recently_referenced=["alt"],
        prior_personal=True,
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


def test_alt_meaning_is_retrieve_explain_interpret():
    plan = build_query_plan("What does my ALT result mean?")
    ops = {str(item).upper() for item in (plan.operations or [])}
    assert "RETRIEVE" in ops
    assert "EXPLAIN" in ops
    assert "INTERPRET" in ops
    assert plan.intent == IntentType.blood_marker_explanation
    assert ops != {"RETRIEVE"}


def test_answer_to_assistant_keeps_alt_and_is_not_a_new_general_query():
    prior = _prior()
    state = ConversationStateResolver().resolve(
        "No symptoms, but I started a supplement last month.",
        _conv(prior),
    )
    assert state.turn_type == TurnType.answer_to_assistant
    assert state.active_domain == "liver_health"
    assert "alt" in state.active_entities
    assert "supplement_use" in state.new_context
    assert state.operations_hint[:2] == ["UPDATE_CONTEXT", "CONTINUE_INTERPRETATION"]
    plan = build_query_plan(
        "No symptoms, but I started a supplement last month.",
        conversation_state=state,
        follow_up_topic="alt",
        prior_personal=True,
    )
    assert plan.conversation_turn == "ANSWER_TO_ASSISTANT"
    assert plan.intent == IntentType.blood_marker_explanation
    assert plan.knowledge_scope == KnowledgeScope.personal
    assert plan.needs_personal_data
    assert plan.topic == "alt" or "alt" in (plan.requested_metrics or [])
    ops = {str(item).upper() for item in (plan.operations or [])}
    assert "UPDATE_CONTEXT" in ops
    assert "CONTINUE_INTERPRETATION" in ops
    assert plan.intent != IntentType.general_health_question


def test_reference_resolution_phrases():
    prior = _prior(
        active_domain="thyroid_health",
        active_entities=["tsh", "t4"],
        previous_user_question="Show my thyroid results.",
        expected_reply_type=ExpectedReplyType.none,
        expected_handling_path=None,
        previous_assistant_follow_up=None,
    )
    conv = _conv(prior)
    cases = {
        "is that concerning?": TurnType.reference_resolution,
        "what about that?": TurnType.reference_resolution,
        "why?": TurnType.reference_resolution,
        "the previous one": TurnType.reference_resolution,
        "the latest one": TurnType.reference_resolution,
        "what about the previous report?": TurnType.reference_resolution,
        "why did that change?": TurnType.reference_resolution,
        "are they consistent?": TurnType.follow_up_question,
    }
    resolver = ConversationStateResolver()
    for message, expected in cases.items():
        state = resolver.resolve(message, conv)
        assert state.turn_type == expected, message
        assert state.active_domain == "thyroid_health"
        assert "tsh" in state.active_entities
        if "previous" in message:
            assert state.resolved_references.get("the previous one") == "previous_report"
        if message in {"why?", "is that concerning?", "what about that?"}:
            assert state.resolved_references.get("that") == "tsh" or state.resolved_references.get("why") == "tsh" or state.resolved_references


def test_conversation_state_is_not_a_source_of_lab_values():
    prior = _prior(previous_assistant_summary="ALT is 999 U/L.")
    state = ConversationStateResolver().resolve("Why?", _conv(prior))
    plan = QueryPlan_from_state(state, "Why?")
    assert plan.topic != "999"
    assert "999" not in (plan.requested_metrics or [])
    assert plan.needs_personal_data
    assert plan.knowledge_scope == KnowledgeScope.personal


def QueryPlan_from_state(state: ConversationState, message: str):
    return build_query_plan(message, conversation_state=state, follow_up_topic="alt", prior_personal=True)


def test_apply_to_query_plan_does_not_copy_assistant_prose():
    prior = _prior()
    state = ConversationStateResolver().resolve("No symptoms, but I started a supplement last month.", _conv(prior))
    empty = build_query_plan("hello")
    bound = apply_to_query_plan(empty.model_copy(deep=True), state)
    assert bound.intent == IntentType.blood_marker_explanation
    assert "ALT is 22" not in (bound.raw_message or "")
    assert "supplement_use" in bound.reasoning_context


def test_jev_routing_state_carries_conversation_fields():
    state = JevRoutingState(
        current_message="No symptoms, but I started a supplement last month.",
        turn_type="ANSWER_TO_ASSISTANT",
        active_entities=["alt"],
        expected_reply_type="CLINICAL_CONTEXT",
        previous_assistant_follow_up="Do you have any new symptoms or medication or supplement changes?",
        new_context=["supplement_use"],
        operations_hint=["UPDATE_CONTEXT", "CONTINUE_INTERPRETATION"],
        resolved_references={"it": "alt"},
    )
    payload = state.model_dump(mode="json", exclude_none=True)
    assert payload["turn_type"] == "ANSWER_TO_ASSISTANT"
    assert payload["active_entities"] == ["alt"]
    assert payload["operations_hint"] == ["UPDATE_CONTEXT", "CONTINUE_INTERPRETATION"]


def test_resolve_plan_keeps_answer_to_assistant_personal(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.jev_enabled", False)
    prior = _prior()
    state = ConversationStateResolver().resolve(
        "No symptoms, but I started a supplement last month.",
        _conv(prior),
    )
    plan, _trace = resolve_plan(
        "No symptoms, but I started a supplement last month.",
        follow_up_topic="alt",
        prior_personal=True,
        conversation_state=state,
    )
    assert plan.knowledge_scope == KnowledgeScope.personal
    assert plan.intent != IntentType.general_health_question
    assert plan.needs_personal_data


def test_composer_requires_handling_path_and_skips_answer_turn():
    plan = build_query_plan("What does my ALT result mean?")
    ctx = HealthContext(
        intent=IntentType.blood_marker_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        resolved_topic="alt",
        resolved_topic_name="ALT",
    )
    composer = ResponseComposer()
    _text, suggestions, _pres = composer.compose(
        "Your ALT is 22 U/L.",
        plan=plan,
        context=ctx,
        follow_ups=[FollowUpSuggestion(text="How is the weather?", category="chit_chat")],
        llm_follow_ups=["Want a recipe?"],
    )
    # Invalid suggestions never reach the member; the row falls back to general questions
    # rather than staying empty.
    from app.pipeline.followup_generator import FALLBACK

    texts = [item.text for item in suggestions]
    assert "How is the weather?" not in texts and "Want a recipe?" not in texts
    assert texts and all(text in FALLBACK["none"] for text in texts)
    plan.conversation_turn = "ANSWER_TO_ASSISTANT"
    _text, suggestions, _pres = composer.compose(
        "Your ALT is 22 U/L.",
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
    )
    assert suggestions == []


def test_alt_meaning_then_supplement_answer_continues_liver_interpretation():
    first = chat("What does my ALT result mean?")
    ops = {str(item).upper() for item in (first["meta"].get("operations") or [])}
    assert "RETRIEVE" in ops
    assert "EXPLAIN" in ops
    assert "INTERPRET" in ops
    assert "22" in first["answer"]
    assert first["meta"]["supershyft_called"] is True
    debug = first["meta"].get("debug") or {}
    assert debug.get("turn_type") == "NEW_QUESTION"
    assert "jev_plan" in debug
    assert debug.get("retrieval_performed") is True
    assert debug.get("reasoner_called") in {True, False}
    chips = first.get("follow_ups") or []
    assert any("symptom" in (item.get("text") or "").lower() for item in chips)
    assert all(item.get("handling_path") for item in chips)

    cid = first["conversation_id"]
    second = chat("No symptoms, but I started a supplement last month.", cid)
    debug = second["meta"].get("debug") or {}
    assert debug.get("turn_type") == "ANSWER_TO_ASSISTANT"
    entities = [str(item).lower() for item in (debug.get("active_entities") or [])]
    topic = str(debug.get("active_topic") or "").lower()
    assert "alt" in entities or topic == "liver_health"
    assert second["meta"]["intent"] != "general_health_question"
    assert second["meta"]["supershyft_called"] is True
    second_ops = {str(item).upper() for item in (second["meta"].get("operations") or [])}
    assert "UPDATE_CONTEXT" in second_ops or "CONTINUE_INTERPRETATION" in second_ops
    assert "22" in second["answer"] or "alt" in second["answer"].lower()
    assert not second.get("follow_ups")


def test_thyroid_reference_sequence_refetches_values():
    first = chat("Show my thyroid results.")
    cid = first["conversation_id"]
    assert first["meta"]["supershyft_called"] is True
    blob = first["answer"].lower()
    assert "tsh" in blob or "t4" in blob or "thyroid" in blob

    second = chat("Are they consistent?", cid)
    debug = second["meta"].get("debug") or {}
    assert debug.get("turn_type") == "FOLLOW_UP_QUESTION"
    assert second["meta"]["supershyft_called"] is True
    assert second["meta"].get("question_type") != "general_education"
    assert "they" in debug.get("resolved_references") or debug.get("active_entities")

    third = chat("What about the previous report?", cid)
    debug = third["meta"].get("debug") or {}
    assert debug.get("turn_type") == "REFERENCE_RESOLUTION"
    assert debug.get("resolved_references", {}).get("the previous one") == "previous_report"
    assert third["meta"]["supershyft_called"] is True
    assert "3.1" in third["answer"] or "t3" in third["answer"].lower() or "previous" in third["answer"].lower()

    fourth = chat("Why did that change?", cid)
    debug = fourth["meta"].get("debug") or {}
    assert debug.get("turn_type") == "REFERENCE_RESOLUTION"
    assert fourth["meta"]["supershyft_called"] is True
    fourth_ops = {str(item).upper() for item in (fourth["meta"].get("operations") or [])}
    assert "TREND" in fourth_ops or "INTERPRET" in fourth_ops or fourth["meta"]["intent"] in {"trend", "blood_marker_explanation", "previous_result"}
    assert debug.get("retrieval_performed") is True


def test_named_marker_does_not_inherit_the_previous_topic():
    state = ConversationState(
        turn_type=TurnType.follow_up_question,
        active_domain="red_cell_anaemia_health",
        active_entities=["hemoglobin", "mcv"],
        prior_personal=True,
    )
    plan = build_query_plan("Has my alkaline phosphatase changed since my last report?")
    bound = apply_to_query_plan(plan, state)
    assert "hemoglobin" not in (bound.requested_metrics or [])
    assert "mcv" not in (bound.requested_metrics or [])
    assert bound.domains != ["red_cell_anaemia_health"]


def test_a_first_explanation_is_in_everyday_words():
    from app.pipeline.prompt_builder import SAFETY_INSTRUCTIONS, _asked_task

    assert "explain it in the same sentence" in SAFETY_INSTRUCTIONS
    assert "not how serious it is" in SAFETY_INSTRUCTIONS
    for question in (
        "What does my alkaline phosphatase mean?",
        "What does my HbA1c mean?",
        "What does my LDL mean?",
        "What does my vitamin D mean?",
        "What does my TSH mean?",
        "What does my creatinine mean?",
        "What does my Dyslipidemia score mean?",
    ):
        hint = _asked_task(question)
        assert "everyday words" in hint, question
        assert "another test" in hint or "chance of disease" in hint
    plain = _asked_task("What is cholesterol?")
    assert "no medical background" in plain
    assert "no personal results" in plain


def test_a_follow_up_knows_the_value_was_already_stated():
    state = ConversationState(
        turn_type=TurnType.follow_up_question,
        active_entities=["iron"],
        explained_entities=["iron"],
        biomarkers_already_discussed=["iron"],
        prior_personal=True,
    )
    plan = apply_to_query_plan(build_query_plan("Why is it low?"), state)
    spec = plan.task_contract or {}
    assert spec.get("continuation") is True
    assert spec.get("measurement_already_stated") is True
    from app.pipeline.prompt_builder import _asked_task
    from app.contracts.health_context import HealthContext
    note = _asked_task("Why is it low?", HealthContext(intent=IntentType.blood_marker_explanation, answer_depth=AnswerDepth.simple, task_contract=spec))
    assert "Do not repeat the definition" in note
    value = _asked_task("What is my exact value?", HealthContext(intent=IntentType.blood_marker_explanation, answer_depth=AnswerDepth.simple, task_contract=spec))
    assert "Give the value" in value
    assert "Do not repeat the definition or the number" not in value


def test_medication_chips_are_not_suggested():
    from app.pipeline.followup_generator import valid_question, FollowUpBrief
    brief = FollowUpBrief()
    assert valid_question("Should I start a statin?", brief) is False
    assert valid_question("Do I need medicine for this?", brief) is False
    assert valid_question("Why is it low?", brief) is True
