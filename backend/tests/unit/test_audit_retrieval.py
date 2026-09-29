from app.contracts.common import IntentType, KnowledgeScope
from app.pipeline.intent import classify_intent, extract_topics
from app.pipeline.lab_parameters import canonicalize_marker_name, match_lab_keys, retrieval_keys
from app.pipeline.ontology import requested_metrics_from_message
from app.pipeline.query_planner import build_query_plan
from app.pipeline.personal_selection import select_latest_markers
from app.auth.models import AuthenticatedPrincipal
from app.contracts.query import QueryPlan
from integrations.mock.blood_provider import MockBloodProvider

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_unsafe_substrings_do_not_match_labs():
    assert match_lab_keys("breakfast") == []
    assert match_lab_keys("salt") == []
    assert match_lab_keys("what is a healthy breakfast") == []
    assert "ast" not in requested_metrics_from_message("What is a healthy breakfast?")
    assert "alt" not in requested_metrics_from_message("Should I eat less salt?")


def test_canonical_super_shyft_names():
    assert canonicalize_marker_name("Serum Creatinine") == "creatinine"
    assert canonicalize_marker_name("Free T3") == "t3"
    assert canonicalize_marker_name("SGPT (ALT)") == "alt"
    assert canonicalize_marker_name("Thyroid Stimulating Hormone (TSH)") == "tsh"


def test_multi_marker_t3_and_t4():
    assert match_lab_keys("What is my latest T3 & T4?") == ["t3", "t4"]
    plan = build_query_plan("What is my latest T3 and T4?")
    assert plan.requested_metrics == ["t3", "t4"]
    assert plan.topic in {"t3", "t4"}


def test_thyroid_results_are_blood_panel_not_bio_ai():
    marker, bio = extract_topics("What are my latest thyroid results?")
    assert marker == "thyroid_function"
    assert bio is None
    plan = build_query_plan("What are my latest thyroid results?")
    assert plan.needs_blood
    assert not plan.needs_bio_ai
    assert plan.topic == "thyroid_function"
    assert set(retrieval_keys(plan.topic)) == {"tsh", "t3", "t4"}


def test_thyroid_score_is_bio_ai():
    plan = build_query_plan("What is my thyroid score?")
    assert plan.needs_bio_ai
    assert not plan.needs_blood
    assert plan.topic == "thyroid"


def test_kidney_panel_expands_to_real_markers():
    plan = build_query_plan("What are my latest kidney function results?")
    assert plan.topic == "kidney_function"
    assert "kidney_function" not in retrieval_keys(plan.topic)
    assert {"creatinine", "egfr"} <= set(retrieval_keys(plan.topic))


def test_latest_marker_uses_older_report_when_newest_missing():
    from datetime import date

    from app.contracts.blood import BloodMarker, BloodReport
    from app.contracts.common import MarkerFlag

    reports = [
        BloodReport(
            report_id="old",
            report_date=date(2026, 1, 1),
            markers=[
                BloodMarker(id="f1", key="ferritin", name="Ferritin", value=45, unit="ng/mL", flag=MarkerFlag.normal)
            ],
        ),
        BloodReport(
            report_id="new",
            report_date=date(2026, 8, 1),
            markers=[
                BloodMarker(id="l1", key="ldl", name="LDL", value=140, unit="mg/dL", flag=MarkerFlag.high)
            ],
        ),
    ]
    selected, missing = select_latest_markers(reports, ["ferritin"])
    assert missing == []
    assert selected[0].value == 45
    assert selected[0].report_id == "old"


def test_latest_t3_skips_null_on_newest_report():
    principal = AuthenticatedPrincipal(subject_id="demo-user-001")
    plan = QueryPlan(
        intent=IntentType.latest_result,
        topic="t3",
        requested_metrics=["t3"],
        needs_blood=True,
        time_operation="latest_marker",
    )
    reports = MockBloodProvider().query(principal, plan)
    selected, missing = select_latest_markers(reports, ["t3"])
    assert missing == []
    assert selected[0].value == 3.1
    assert selected[0].report_id == "blood-001"


def test_chat_multi_marker_and_kidney_panel():
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest T3 and T4?"}).json()
    debug = first["meta"].get("debug") or {}
    assert set(debug.get("requested_metrics") or []) == {"t3", "t4"}
    answer = first["answer"].lower()
    assert "t3" in answer and "t4" in answer
    cid = first["conversation_id"]
    kidney = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "What are my latest kidney function results?"},
    ).json()
    kdebug = kidney["meta"].get("debug") or {}
    assert kdebug.get("query_plan_topic") == "kidney_function"
    assert "t3" not in (kidney["answer"].lower())
    assert "creatinine" in kidney["answer"].lower() or "egfr" in kidney["answer"].lower()


def test_casual_hello_does_not_use_personal_or_medical_llm():
    body = client.post("/api/v1/chat", headers=H, json={"message": "Hello"}).json()
    assert body["meta"]["intent"] == "casual_conversation"
    assert body["meta"]["llm_mode"] == "casual"
    assert "12.6" not in body["answer"]
    assert "blood report" not in body["answer"].lower() or "help" in body["answer"].lower()


def test_hypothetical_thyroid_is_general():
    plan = build_query_plan("If my thyroid is high, what should I do?")
    assert plan.knowledge_scope == KnowledgeScope.general
    assert not plan.needs_personal_data
    intent, *_ = classify_intent("If my thyroid is high, what should I do?")
    assert intent == IntentType.general_health_question


def test_mixed_ldl_and_guidance():
    plan = build_query_plan("What is my LDL and what should I do to reduce it?")
    assert plan.needs_blood
    assert plan.needs_guidance or plan.medical_evidence_required
    assert "ldl" in plan.requested_metrics


def test_bio_ai_missing_score_is_not_substituted():
    from datetime import date

    from app.auth.models import AuthenticatedPrincipal
    from app.contracts.bio_ai import BioAIReport, BioAIRisk
    from app.pipeline.context_builder import ContextBuilder
    from app.providers.registry import build_registry

    class Bio:
        def query(self, principal, plan):
            return [
                BioAIReport(
                    report_id="bio-x",
                    report_date=date(2026, 8, 1),
                    source_line="bio_ai",
                    risks=[
                        BioAIRisk(code="hypertension", name="Hypertension", score=19, status="mild"),
                    ],
                )
            ]

    registry = build_registry()
    registry.bio_ai = Bio()
    ctx = ContextBuilder(registry).build(
        AuthenticatedPrincipal(subject_id="demo-user-001"),
        QueryPlan(
            intent=IntentType.bio_ai_score,
            topic="nafld",
            requested_metrics=["nafld"],
            needs_bio_ai=True,
            knowledge_scope=KnowledgeScope.personal,
            needs_supershyft=True,
        ),
    )
    assert ctx.bio_ai_risks == []
    assert ctx.missing
    assert ctx.missing[0].reason == "score_not_available"
    from app.pipeline.renderer import DeterministicRenderer

    answer = DeterministicRenderer().render("What is my NAFLD score?", ctx)
    assert answer == "Score not available in this report."
    assert "Hypertension" not in answer


def test_what_about_creatinine_does_not_keep_t3():
    first = client.post("/api/v1/chat", headers=H, json={"message": "What is my T3?"}).json()
    cid = first["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "What about my creatinine?"},
    ).json()
    debug = second["meta"].get("debug") or {}
    assert debug.get("query_plan_topic") == "creatinine"
    assert "creatinine" in second["answer"].lower()
    assert "t3" not in second["answer"].lower()


def test_user_isolation_chat():
    a = client.post("/api/v1/chat", headers=H, json={"message": "What is my Vitamin D?"}).json()
    b = client.post(
        "/api/v1/chat",
        headers={"X-Cura-User-Id": "demo-user-002"},
        json={"message": "What is my Vitamin D?"},
    ).json()
    assert "12.6" in a["answer"]
    assert "42.0" in b["answer"]
    assert "42.0" not in a["answer"]
    assert "12.6" not in b["answer"]


def test_pcod_risk_questions_route_to_bio_ai_not_blood_summary():
    questions = (
        "Tell me my risk score for PCOD?",
        "What is my PCOD risk?",
    )
    for message in questions:
        intent, topic, name, _ = classify_intent(message)
        assert intent == IntentType.bio_ai_score, message
        assert topic == "pcos", message
        plan = build_query_plan(message)
        assert plan.needs_bio_ai, message
        assert not plan.needs_blood, message
        assert plan.requested_metrics == ["pcos"], message
        assert requested_metrics_from_message(message) == ["pcos"]


def test_pcod_risk_questions_do_not_dump_latest_cbc():
    first = client.post(
        "/api/v1/chat",
        headers=H,
        json={"message": "Tell me my risk score for PCOD?"},
    ).json()
    cid = first["conversation_id"]
    second = client.post(
        "/api/v1/chat",
        headers=H,
        json={"conversation_id": cid, "message": "What is my PCOD risk?"},
    ).json()
    for body in (first, second):
        answer = body["answer"].lower()
        assert body["meta"]["intent"] == "bio_ai_score"
        assert "prioritized findings" not in answer
        assert "haemoglobin" not in answer
        assert "hemoglobin" not in answer
        assert "neutrophils" not in answer
        assert "lymphocytes" not in answer
        assert "score not available in this report." in answer
        sources = [item.get("name") for item in (body.get("provenance") or {}).get("sources") or []]
        assert "Blood Report" not in sources


def test_select_bio_risks_matches_pcod_alias():
    from datetime import date

    from app.contracts.bio_ai import BioAIReport, BioAIRisk
    from app.pipeline.personal_selection import select_bio_risks

    report = BioAIReport(
        report_id="bio-pcos",
        report_date=date(2026, 8, 1),
        source_line="bio_ai",
        risks=[BioAIRisk(code="PCOD", name="PCOD", score=41, status="moderate")],
    )
    selected, missing = select_bio_risks(report, ["pcos"])
    assert missing == []
    assert selected[0].score == 41
    selected, missing = select_bio_risks(report, ["pcod"])
    assert missing == []
    assert selected[0].code == "PCOD"
