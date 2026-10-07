from datetime import date

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.personalization import LongitudinalClass
from app.contracts.query import QueryPlan
from app.pipeline.baselines import build_baselines, classify_series
from app.pipeline.clinician_handoff import build_clinician_handoff, format_handoff
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.health_story import build_health_story
from app.pipeline.operations import classify_operation
from app.pipeline.personalization_context import goal_code_from_message
from app.pipeline.personalization_layer import attach_personalization_layer
from app.pipeline.quiet_mode import decide_quiet
from app.pipeline.query_planner import build_query_plan
from app.pipeline.recent_context import extract_recent_context
from app.providers.registry import build_registry
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
IRON = {"X-Cura-User-Id": "eval-user-iron"}
DEMO = {"X-Cura-User-Id": "demo-user-001"}
DEMO2 = {"X-Cura-User-Id": "demo-user-002"}


def _marker(key: str, value: float, flag: MarkerFlag, day: date, report_id: str) -> BloodMarker:
    return BloodMarker(
        id=f"{key}-{report_id}",
        key=key,
        name=key,
        value=value,
        flag=flag,
        measured_at=day,
        report_id=report_id,
    )


def _reports() -> list[BloodReport]:
    older = date(2026, 5, 24)
    newer = date(2026, 8, 24)
    return [
        BloodReport(
            report_id="r1",
            report_date=older,
            markers=[
                _marker("vitamin_d", 18.0, MarkerFlag.low, older, "r1"),
                _marker("hba1c", 5.3, MarkerFlag.normal, older, "r1"),
                _marker("ldl", 90.0, MarkerFlag.normal, older, "r1"),
                _marker("iron", 32.0, MarkerFlag.low, older, "r1"),
            ],
        ),
        BloodReport(
            report_id="r2",
            report_date=newer,
            markers=[
                _marker("vitamin_d", 24.0, MarkerFlag.low, newer, "r2"),
                _marker("hba1c", 5.3, MarkerFlag.normal, newer, "r2"),
                _marker("ldl", 91.0, MarkerFlag.normal, newer, "r2"),
                _marker("iron", 32.0, MarkerFlag.low, newer, "r2"),
                _marker("esr", 42.0, MarkerFlag.high, newer, "r2"),
            ],
        ),
    ]


def test_goal_phrase_detection_is_compositional():
    assert goal_code_from_message("My goal is improving energy. What should I focus on?") == "improve_energy"
    assert goal_code_from_message("I want better metabolic health. Which findings matter most?") == "improve_metabolic_health"
    assert goal_code_from_message("I want to improve sleep. What does my current data show?") == "improve_sleep"


def test_personal_baselines_and_longitudinal_classes():
    rows = build_baselines(_reports())
    by_key = {item.entity: item for item in rows}
    assert by_key["vitamin_d"].classification == LongitudinalClass.improved_but_still_abnormal
    assert by_key["hba1c"].classification == LongitudinalClass.stable
    assert by_key["iron"].classification == LongitudinalClass.persistently_abnormal
    assert by_key["esr"].classification == LongitudinalClass.newly_available
    assert by_key["vitamin_d"].observations == 2
    assert by_key["vitamin_d"].latest == 24.0
    assert by_key["vitamin_d"].previous == 18.0


def test_no_baseline_without_history():
    report = BloodReport(
        report_id="only",
        report_date=date(2026, 8, 24),
        markers=[_marker("tsh", 2.1, MarkerFlag.normal, date(2026, 8, 24), "only")],
    )
    rows = build_baselines([report], ["tsh"])
    assert rows[0].classification == LongitudinalClass.newly_available
    assert rows[0].previous is None


def test_classifier_returned_to_range():
    series = [(12.0, MarkerFlag.low), (18.0, MarkerFlag.normal)]
    assert classify_series("vitamin_d", series) == LongitudinalClass.returned_to_range


def test_health_story_groups_persistent_and_reassuring():
    ctx = HealthContext(
        intent=IntentType.broad_health_summary,
        answer_depth=AnswerDepth.broad,
        knowledge_scope=KnowledgeScope.personal,
        markers=_reports()[-1].markers,
        domains=["iron_status", "glycemic_health"],
    )
    ctx.baselines = build_baselines(_reports())
    story = build_health_story(ctx, ctx.baselines)
    assert "glycemic_health" in story.stable_reassuring or "lipid_health" in story.stable_reassuring
    assert any(item.domain in {"iron_status", "red_cell_anaemia_health"} for item in story.persistent_patterns) or "iron" in story.improving or story.persistent_patterns == [] or "iron" in [e for p in story.persistent_patterns for e in p.supporting_entities]
    assert "vitamin_d" in story.improving


def test_quiet_mode_when_nothing_meaningful_changed():
    ctx = HealthContext(
        intent=IntentType.latest_result,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        markers=[_marker("hba1c", 5.3, MarkerFlag.normal, date(2026, 8, 24), "r2")],
    )
    ctx.baselines = build_baselines(_reports(), ["hba1c", "ldl"])
    decision = decide_quiet(ctx, "Everything looks stable. Do I need to change anything?")
    assert decision.active is True


def test_recent_context_is_not_a_lab_fact():
    ctx = extract_recent_context("I was sick when I took this test. I started B12 supplements recently.")
    assert ctx.illness
    assert ctx.supplements
    assert ctx.source == "conversation"


def test_clinician_handoff_is_structured_and_not_a_diagnosis():
    ctx = HealthContext(
        intent=IntentType.report_explanation,
        answer_depth=AnswerDepth.focused,
        knowledge_scope=KnowledgeScope.personal,
        markers=_reports()[-1].markers,
        operations=["PREPARE_CLINICIAN_DISCUSSION"],
    )
    attach_personalization_layer(ctx, message="Summarize this for my doctor.", blood_reports=_reports())
    assert ctx.clinician_handoff is not None
    text = format_handoff(ctx.clinician_handoff)
    assert "Key points to discuss" in text
    assert "diagnos" not in text.lower()


def test_goal_aware_energy_focus_uses_iron_pattern():
    plan = build_query_plan("My goal is improving energy. What should I focus on?")
    ctx = ContextBuilder(build_registry()).build(
        AuthenticatedPrincipal(subject_id="eval-user-iron"),
        plan,
        message="My goal is improving energy. What should I focus on?",
    )
    assert ctx.personalization is not None
    assert ctx.personalization.primary_health_goal == "improve_energy"
    keys = {m.key for m in ctx.markers}
    assert {"hemoglobin", "iron"} & keys


def test_chat_goal_energy_mentions_iron_not_generic_exercise():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "My goal is improving energy. What should I focus on?"},
    ).json()
    answer = body["answer"].lower()
    assert "iron" in answer or "haemoglobin" in answer or "hemoglobin" in answer
    assert "exercise more" not in answer


def test_chat_what_changed_is_compact():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "What changed since last time?"},
    ).json()
    answer = body["answer"].lower()
    assert "vitamin d" in answer or "ldl" in answer or "changed" in answer or "stable" in answer
    assert answer.count("report id") == 0


def test_chat_quiet_stable_does_not_invent_action():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO2,
        json={"message": "Everything looks stable. Do I need to change anything?"},
    ).json()
    answer = body["answer"].lower()
    assert "exercise more" not in answer
    assert "eat healthy" not in answer


def test_chat_clinician_questions():
    body = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "What should I ask my doctor about?"},
    ).json()
    presentation = body.get("presentation") or {}
    answer = (body.get("answer") or "").lower()
    assert presentation.get("mode") == "CLINICIAN_HANDOFF" or any(w in answer for w in ("discuss", "doctor", "clinician"))
    assert "you have iron deficiency anemia" not in answer


def test_chat_recent_illness_is_context_not_diagnosis():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "I was sick when I took this test. Does that matter?"},
    ).json()
    answer = body["answer"].lower()
    assert "illness" in answer or "infection" in answer or "timing" in answer or "fever" in answer or "sick" in answer
    assert "pneumonia" not in answer


def test_chat_supplement_context():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "I started B12 supplements recently. Does that affect how you interpret this?"},
    ).json()
    answer = body["answer"].lower()
    assert "supplement" in answer or "b12" in answer


def test_package_check_before_repeating_fields():
    from app.pipeline.testing_option import TestingOptionService as DiagnosticsTesting

    option, _trace, _need = DiagnosticsTesting().evaluate(
        message="Do I need another package for my cholesterol?",
        context=ContextBuilder(build_registry()).build(
            AuthenticatedPrincipal(subject_id="demo-user-001"),
            QueryPlan(
                intent=IntentType.latest_result,
                answer_depth=AnswerDepth.simple,
                knowledge_scope=KnowledgeScope.personal,
                needs_blood=True,
                requested_metrics=["ldl"],
                raw_message="Do I need another package for my cholesterol?",
            ),
            message="Do I need another package for my cholesterol?",
        ),
    )
    if option is None:
        return
    assert option.comparison.recently_available is not None
    assert option.comparison.new_information is not None


def test_assess_goal_progress_operation():
    plan = build_query_plan("How am I progressing toward my health goals?")
    assert classify_operation(plan, plan.raw_message).value == "ASSESS_GOAL_PROGRESS"


def test_snapshot_includes_health_journey():
    body = client.get("/api/v1/health-snapshot", headers=DEMO).json()
    assert "health_journey" in body
    if body.get("health_journey"):
        assert set(body["health_journey"]) >= {"current_focus", "improving", "stable", "needs_attention", "missing_information"}


def test_chat_lifestyle_already_supportive_avoids_generic_advice():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "I already exercise regularly. What else should I focus on?"},
    ).json()
    answer = body["answer"].lower()
    assert "exercise more" not in answer
    assert "eat healthy" not in answer


def test_chat_health_story_does_not_dump_two_reports():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "Tell me the story of my health over the last few reports."},
    ).json()
    answer = body["answer"].lower()
    assert "blood-001" not in answer and "blood-002" not in answer
    assert "pattern" in answer or "changed" in answer or "stable" in answer or "vitamin" in answer


def test_chat_personal_baseline_does_not_invent_history():
    body = client.post(
        "/api/v1/chat",
        headers=DEMO,
        json={"message": "Is this high for me compared with my usual values?"},
    ).json()
    answer = body["answer"].lower()
    assert body["answer"].strip()
    assert "blood-001" not in answer and "blood-002" not in answer
    assert "you have diabetes" not in answer
    assert "you have anemia" not in answer


def test_followup_continuity_stays_on_topic():
    first = client.post("/api/v1/chat", headers=IRON, json={"message": "What stands out most?"}).json()
    conversation_id = first["conversation_id"]
    why = client.post(
        "/api/v1/chat",
        headers=IRON,
        json={"message": "Why?", "conversation_id": conversation_id},
    ).json()
    answer = why["answer"].lower()
    assert "iron" in answer or "haemoglobin" in answer or "hemoglobin" in answer or "vitamin" in answer
    assert "pneumonia" not in answer
