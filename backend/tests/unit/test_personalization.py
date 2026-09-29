from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.facts import FactKind
from app.db.goal_store import GoalStore
from app.db.session import SessionLocal
from app.main import app
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.prompt_builder import PromptBuilder
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry
from app.retrieval.router import HealthRetrievalRouter
from app.routing.mapper import plan_from_jev
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevSource, JevTimeRange

client = TestClient(app)
H1 = {"X-Cura-User-Id": "demo-user-001"}
H2 = {"X-Cura-User-Id": "demo-user-002"}


def test_general_question_does_not_load_personal_profile():
    plan = build_query_plan("What is LDL?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert plan.needs_personal_data is False
    assert plan.needs_profile is False
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert ctx.profile is None
    assert ctx.facts == []


def test_personal_vs_general_ldl_ok():
    general = build_query_plan("What is LDL?")
    personal = build_query_plan("Is my LDL okay?")
    assert general.needs_personal_data is False
    assert personal.intent == IntentType.blood_marker_explanation
    assert personal.needs_blood is True
    assert personal.medical_evidence_required is True


def test_report_explanation_routing():
    plan = build_query_plan("Explain my latest report.")
    assert plan.intent == IntentType.report_explanation
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is True
    assert plan.history is True
    assert plan.time_operation == "latest_report"


def test_health_goal_progress_routing():
    plan = build_query_plan("How am I progressing toward my health goals?")
    assert plan.intent == IntentType.health_goal_progress
    assert plan.needs_blood is True
    assert plan.needs_goals is True
    assert plan.history is True


def test_personal_profile_routing():
    plan = build_query_plan("What is my health profile?")
    assert plan.intent == IntentType.personal_profile
    assert plan.needs_lifestyle is True
    assert plan.needs_profile is True
    assert plan.needs_blood is False


def test_historical_comparison_uses_stored_values():
    plan = build_query_plan("How has my cholesterol changed?")
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    assert ctx.comparisons
    row = next((item for item in ctx.comparisons if item.topic in {"ldl", "cholesterol"}), ctx.comparisons[0])
    assert row.previous_value is not None
    assert row.current_value is not None
    assert row.previous_report_id != row.current_report_id
    assert all(fact.fact_type == FactKind.measured_data for fact in ctx.facts if fact.fact == row.topic)


def test_missing_history_does_not_invent_values():
    plan = build_query_plan("How has my vitamin D changed?")
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-002"), plan)
    invented = [c for c in ctx.comparisons if c.previous_value is not None and c.current_value is not None]
    assert invented == []


def test_cross_source_plan_keeps_separated_evidence():
    plan = build_query_plan("Considering my latest blood report and Bio-AI report, what areas should I focus on?")
    assert plan.needs_blood is True
    assert plan.needs_bio_ai is True
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    measured = [f for f in ctx.facts if f.fact_type == FactKind.measured_data]
    assert measured
    assert ctx.markers or ctx.bio_ai_risks or ctx.scenario
    messages = PromptBuilder().build(ctx, "Current topic: lipids", "What should I focus on?")
    blob = messages[1]["content"]
    assert "MEASURED_DATA JSON:" in blob
    assert "never a source of current lab values" in blob


def test_provenance_on_personal_ldl():
    plan = build_query_plan("What is my LDL?")
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    ldl = next(m for m in ctx.markers if m.key == "ldl")
    fact = next(f for f in ctx.facts if f.fact == "ldl")
    assert fact.value == ldl.value
    assert fact.report_id
    assert fact.fact_type == FactKind.measured_data
    assert fact.source


def test_user_isolation_context_and_snapshot():
    registry = build_registry()
    builder = ContextBuilder(registry)
    plan = build_query_plan("What is my LDL?")
    one = builder.build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    two = builder.build(AuthenticatedPrincipal(subject_id="demo-user-002"), plan)
    one_ids = {m.report_id for m in one.markers}
    two_ids = {m.report_id for m in two.markers}
    assert one_ids
    assert one_ids.isdisjoint(two_ids) or not two.markers
    snap1 = client.get("/api/v1/health-snapshot", headers=H1).json()
    snap2 = client.get("/api/v1/health-snapshot", headers=H2).json()
    assert snap1["subject_id"] == "demo-user-001"
    assert snap2["subject_id"] == "demo-user-002"
    one_reports = {row["report_id"] for row in snap1["recent_reports"]}
    two_reports = {row["report_id"] for row in snap2["recent_reports"]}
    if one_reports and two_reports:
        assert one_reports.isdisjoint(two_reports)


def test_goals_progress_from_actual_history():
    db = SessionLocal()
    try:
        GoalStore(db).replace_for_subject("demo-user-001", ["improve_cholesterol"])
        res = client.put(
            "/api/v1/me/goals",
            headers=H1,
            json={"goals": ["improve_cholesterol"]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["subject_id"] == "demo-user-001"
        assert body["goals"][0]["goal_code"] == "improve_cholesterol"
        progress = body["progress"][0]
        assert progress["sufficient_history"] is True
        assert progress["metrics"]
        assert all(item["fact_type"] == "MEASURED_DATA" for item in progress["metrics"])
        plan = build_query_plan("How am I progressing toward my health goals?")
        ctx = ContextBuilder(build_registry()).build(
            AuthenticatedPrincipal(subject_id="demo-user-001"),
            plan,
            db=db,
        )
        assert ctx.goal_progress
        assert ctx.goal_progress[0].sufficient_history is True
    finally:
        db.close()


def test_goals_never_leak_across_users():
    db = SessionLocal()
    try:
        GoalStore(db).replace_for_subject("demo-user-001", ["improve_metabolic_health"])
        GoalStore(db).replace_for_subject("demo-user-002", ["improve_fitness"])
        a = client.get("/api/v1/me/goals", headers=H1).json()
        b = client.get("/api/v1/me/goals", headers=H2).json()
        assert {g["goal_code"] for g in a["goals"]} == {"improve_metabolic_health"}
        assert {g["goal_code"] for g in b["goals"]} == {"improve_fitness"}
    finally:
        db.close()


def test_missing_goals_are_honest():
    plan = build_query_plan("How am I progressing toward my health goals?")
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="demo-user-002"),
        plan,
    )
    assert any(item.reason == "no_goals" for item in ctx.missing) or not ctx.goals


def test_jev_profile_and_report_mapping():
    profile = plan_from_jev(
        JevDecision(
            intent=JevIntent.personal_profile_lookup,
            source=JevSource.profile,
            operation=JevOperation.lookup,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        ),
        "What is my health profile?",
    )
    assert profile.intent == IntentType.personal_profile
    assert profile.needs_lifestyle is True
    assert profile.needs_blood is False
    report = plan_from_jev(
        JevDecision(
            intent=JevIntent.lab_result_lookup,
            source=JevSource.blood_reports,
            operation=JevOperation.summarize,
            requires_personal_data=True,
            time_range=JevTimeRange.latest,
        ),
        "Explain my latest report.",
    )
    assert report.intent == IntentType.report_explanation
    assert report.needs_blood is True
    goals = plan_from_jev(
        JevDecision(
            intent=JevIntent.personal_profile_lookup,
            source=JevSource.profile,
            operation=JevOperation.trend,
            requires_personal_data=True,
            requires_historical_data=True,
            time_range=JevTimeRange.historical,
            requested_entities=["goal"],
        ),
        "How am I progressing toward my health goals?",
    )
    assert goals.intent == IntentType.health_goal_progress
    assert goals.needs_goals is True


def test_follow_up_does_not_treat_chat_as_lab_source():
    first = client.post("/api/v1/chat", headers=H1, json={"message": "My LDL is high."})
    assert first.status_code == 200
    cid = first.json()["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H1,
        json={"message": "Compare it with my previous result.", "conversation_id": cid},
    )
    assert second.status_code == 200
    answer = second.json()["answer"]
    assert "138" in answer or "142" in answer
    assert "invent" not in answer.lower() or "previous" in answer.lower()


def test_snapshot_includes_extensible_insights_not_chat_alerts():
    body = client.get("/api/v1/health-snapshot", headers=H1).json()
    assert body["available"] is True
    assert body["latest_biomarkers"]
    assert body["bio_ai_scores"]
    assert "insight_candidates" in body
    for item in body["insight_candidates"]:
        assert item["delivery"] == "on_request"


def test_retrieval_personal_profile_does_not_require_blood():
    plan = build_query_plan("What is my health profile?")
    result = HealthRetrievalRouter(build_registry()).retrieve(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        plan,
    )
    assert result.invoked is True
    assert plan.needs_blood is False
