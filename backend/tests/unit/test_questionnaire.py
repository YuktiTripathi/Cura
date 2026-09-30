from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.facts import FactKind
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry
from app.retrieval.router import HealthRetrievalRouter
from app.routing.jev_router import JEV_MIN_CONFIDENCE
from app.routing.mapper import plan_from_jev
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevSource, JevTimeRange
from app.routing.validator import validate_jev_decision
from app.routing.schemas import JevRoutingState

Q1 = AuthenticatedPrincipal(subject_id="demo-user-q1")
Q2 = AuthenticatedPrincipal(subject_id="demo-user-q2")
U001 = AuthenticatedPrincipal(subject_id="demo-user-001")


def _retrieve(principal, plan):
    return HealthRetrievalRouter(build_registry()).retrieve(principal, plan)


def test_user_retrieves_own_questionnaire_response():
    plan = build_query_plan("What did I answer about my sleep?")
    assert plan.needs_questionnaire is True
    assert plan.needs_blood is False
    result = _retrieve(Q1, plan)
    assert result.questionnaire_called is True
    assert result.ihr_called is False
    keys = {answer.question_key for item in result.questionnaire_instances for answer in item.answers}
    assert "sleeping_hours" in keys
    assert all(item.subject_id == "demo-user-q1" for item in result.questionnaire_instances)


def test_user_cannot_retrieve_another_users_questionnaire():
    plan = build_query_plan("What did I answer about my sleep?")
    own = _retrieve(Q1, plan)
    other = _retrieve(Q2, plan)
    own_values = {answer.value for item in own.questionnaire_instances for answer in item.answers}
    other_values = {answer.value for item in other.questionnaire_instances for answer in item.answers}
    assert own_values
    assert other_values
    assert own_values != other_values
    assert all(item.subject_id == "demo-user-q1" for item in own.questionnaire_instances)
    assert all(item.subject_id == "demo-user-q2" for item in other.questionnaire_instances)


def test_latest_questionnaire_response_is_selected():
    plan = build_query_plan("What did I answer about my sleep?")
    result = _retrieve(Q1, plan)
    assert len(result.questionnaire_instances) == 1
    instance = result.questionnaire_instances[0]
    assert instance.assessment_instance_id == "q1-latest"
    sleep = next(answer for answer in instance.answers if answer.question_key == "sleeping_hours")
    assert sleep.value == "7-8 hours"


def test_historical_questionnaire_responses_remain_available():
    plan = build_query_plan("Have my sleep habits changed?")
    assert plan.needs_questionnaire is True
    assert plan.history is True
    result = _retrieve(Q1, plan)
    ids = [item.assessment_instance_id for item in result.questionnaire_instances]
    assert ids == ["q1-older", "q1-latest"]
    values = [
        next(answer.value for answer in item.answers if answer.question_key == "sleeping_hours")
        for item in result.questionnaire_instances
    ]
    assert values == ["5-6 hours", "7-8 hours"]


def test_missing_questionnaire_data_is_handled():
    plan = build_query_plan("What did I answer about my sleep?")
    ctx = ContextBuilder(build_registry()).build(U001, plan)
    assert ctx.questionnaire == []
    assert any(item.key == "questionnaire" for item in ctx.missing)


def test_general_medical_questions_do_not_query_questionnaires():
    plan = build_query_plan("What is LDL?")
    assert plan.needs_questionnaire is False
    result = _retrieve(U001, plan)
    assert result.questionnaire_called is False
    assert result.skipped_reason == "general_no_personal_data"


def test_explicit_questionnaire_questions_do_query():
    plan = build_query_plan("What are my dietary habits according to my questionnaire?")
    assert plan.intent == IntentType.questionnaire_lookup
    assert plan.needs_questionnaire is True
    assert plan.source == QuerySource.questionnaire
    result = _retrieve(Q1, plan)
    assert result.questionnaire_called is True
    keys = {answer.question_key for item in result.questionnaire_instances for answer in item.answers}
    assert "diet_preference" in keys


def test_sleep_without_questionnaire_wording_is_not_questionnaire():
    plan = build_query_plan("What is my sleep?")
    assert plan.needs_questionnaire is False


def test_blood_and_questionnaire_retrieve_both_sources():
    plan = build_query_plan("Considering my LDL and my questionnaire responses, what should I change?")
    assert plan.needs_blood is True
    assert plan.needs_questionnaire is True
    assert plan.medical_evidence_required is True
    result = _retrieve(Q1, plan)
    assert result.ihr_called is True
    assert result.questionnaire_called is True
    assert result.blood_reports
    assert result.questionnaire_instances


def test_bio_ai_and_questionnaire_retrieve_both_sources():
    plan = build_query_plan("What is my dyslipidemia score and what did I answer in my questionnaire?")
    assert plan.needs_bio_ai is True
    assert plan.needs_questionnaire is True
    result = _retrieve(Q1, plan)
    assert result.ihr_called is True
    assert result.questionnaire_called is True
    assert result.bio_ai_reports
    assert result.questionnaire_instances


def test_blood_bio_questionnaire_and_evidence_together():
    plan = build_query_plan(
        "Considering my LDL, dyslipidemia score, and questionnaire responses, what should I focus on?"
    )
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is True
    assert plan.needs_questionnaire is True
    assert plan.medical_evidence_required is True
    ctx = ContextBuilder(build_registry()).build(Q1, plan)
    prompt = "\n".join(item["content"] for item in PromptBuilder().build(ctx, "", plan.raw_message))
    assert "PERSONAL BLOOD DATA" in prompt
    assert "QUESTIONNAIRE RESPONSES" in prompt
    assert "BIO-AI DATA" in prompt
    assert ctx.markers
    assert ctx.questionnaire
    assert ctx.bio_ai_risks or ctx.facts


def test_questionnaire_facts_have_provenance_and_are_not_lab_measurements():
    plan = build_query_plan("What did I answer about my sleep?")
    ctx = ContextBuilder(build_registry()).build(Q1, plan)
    q_facts = [fact for fact in ctx.facts if fact.fact_type == FactKind.questionnaire_response]
    assert q_facts
    for fact in q_facts:
        assert fact.source == "questionnaire"
        assert fact.fact_type != FactKind.measured_data
        assert fact.response_id
        assert fact.question_id
        assert fact.questionnaire_id
        assert any("provenance=SuperShyft" in note for note in fact.notes)
    assert all(fact.fact_type != FactKind.measured_data or fact.fact != "sleeping_hours" for fact in ctx.facts)


def test_follow_up_reuses_questionnaire_context():
    first = build_query_plan("What did I answer about my sleep?")
    assert first.needs_questionnaire is True
    follow = build_query_plan("What about alcohol?", follow_up_topic=first.topic or "sleep", prior_personal=True)
    assert follow.needs_questionnaire is True
    assert follow.topic in {"alcohol", "alcohol_frequency"}
    result = _retrieve(Q1, follow)
    keys = {answer.question_key for item in result.questionnaire_instances for answer in item.answers}
    assert "alcohol_frequency" in keys


def test_jev_questionnaire_mapping_and_confidence_gate_unchanged():
    assert JEV_MIN_CONFIDENCE == 0.80
    decision = JevDecision(
        intent=JevIntent.questionnaire_lookup,
        source=JevSource.questionnaire,
        operation=JevOperation.lookup,
        requires_personal_data=True,
        time_range=JevTimeRange.latest,
        requested_entities=["sleep"],
        confidence=0.91,
    )
    plan = plan_from_jev(decision, "What did I answer about my sleep?")
    assert plan.intent == IntentType.questionnaire_lookup
    assert plan.needs_questionnaire is True
    assert plan.needs_blood is False
    assert plan.source == QuerySource.questionnaire

    mixed = JevDecision(
        intent=JevIntent.questionnaire_interpretation,
        source=JevSource.multiple_sources,
        operation=JevOperation.interpret,
        requires_personal_data=True,
        requested_metrics=["ldl"],
        time_range=JevTimeRange.latest,
        confidence=0.88,
    )
    mixed_plan = plan_from_jev(mixed, "Considering my LDL and my questionnaire responses, what should I change?")
    assert mixed_plan.needs_questionnaire is True
    assert mixed_plan.needs_blood is True
    assert mixed_plan.medical_evidence_required is True

    state = JevRoutingState(
        current_message="Show my questionnaire",
        supported_capabilities=["questionnaires"],
    )
    allowed = validate_jev_decision(decision, state, deterministic_requires_personal=True)
    assert allowed.intent == JevIntent.questionnaire_lookup
    assert allowed.requires_clarification is False


def test_health_snapshot_summarizes_questionnaire_without_raw_dump():
    from app.pipeline.health_snapshot import build_personal_health_snapshot

    snap = build_personal_health_snapshot(Q1, build_registry())
    assert snap.lifestyle_summary is not None
    assert snap.lifestyle_summary.sleep_pattern is not None
    assert snap.lifestyle_summary.sleep_pattern.fact_type == FactKind.questionnaire_response
    assert snap.lifestyle_summary.sleep_pattern.value == "7-8 hours"
    q_events = [event for event in (snap.timeline.events if snap.timeline else []) if event.event_type == "questionnaire"]
    assert q_events
    empty = build_personal_health_snapshot(U001, build_registry())
    assert empty.lifestyle_summary is None


def test_chat_renders_questionnaire_answers():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.providers.registry import set_registry

    client = TestClient(app)
    set_registry(None)
    try:
        body = client.post(
            "/api/v1/chat",
            headers={"X-Cura-User-Id": "demo-user-q1"},
            json={"message": "What did I answer about my sleep?"},
        ).json()
        assert "7-8 hours" in body["answer"]
        assert "laboratory" in body["answer"].lower()
        names = [item["name"] for item in (body.get("provenance") or {}).get("sources") or []]
        assert "Health Questionnaire" in names
    finally:
        set_registry(None)
