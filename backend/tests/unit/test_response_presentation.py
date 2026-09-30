from fastapi.testclient import TestClient

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType
from app.contracts.health_context import HealthContext
from app.main import app
from app.pipeline.context_builder import ContextBuilder
from app.pipeline.health_domains import HealthDomainResolver
from app.pipeline.presentation import infer_response_mode, sanitize_internal_ids
from app.pipeline.query_planner import build_query_plan
from app.providers.registry import build_registry

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}


def test_sanitize_strips_internal_report_ids():
    text = "Your latest TSH (report blood-002 on 2026-08-18) is 2.1. See bioai-a."
    cleaned = sanitize_internal_ids(text)
    assert "blood-002" not in cleaned
    assert "bioai-a" not in cleaned
    assert "(report" not in cleaned.lower()
    assert "which report" in sanitize_internal_ids("Which report would you like me to use?").lower()


def test_list_only_is_result_list_without_interpretation():
    plan = build_query_plan("List only my latest thyroid-related results.")
    assert plan.response_mode == "RESULT_LIST" or plan.operations == ["RETRIEVE"] or "INTERPRET" not in (plan.operations or [])
    body = client.post("/api/v1/chat", headers=H, json={"message": "List only my latest thyroid-related results."}).json()
    pres = body.get("presentation") or {}
    assert pres.get("mode") in {"RESULT_LIST", "DOMAIN_SUMMARY", "SINGLE_VALUE"}
    assert not pres.get("interpretation")
    answer = body["answer"].lower()
    assert "tsh" in answer or "2.1" in body["answer"]
    assert "diagnos" not in answer


def test_internal_ids_hidden_from_answers_but_kept_in_evidence():
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is my latest Vitamin D?"}).json()
    assert "12.6" in body["answer"]
    assert "blood-002" not in body["answer"]
    assert "blood-2" not in body["answer"].lower()
    assert "(report" not in body["answer"].lower()
    assert any(item["report_id"] == "blood-002" for item in body["evidence"])
    names = [s["name"] for s in body["provenance"]["sources"]]
    assert any("blood report" in name.lower() for name in names)
    assert any("Aug 2026" in name or "18 Aug" in name for name in names)
    pres = body["presentation"]
    assert pres["mode"] == "SINGLE_VALUE"
    assert pres["findings"]
    assert all("blood-002" not in (pres.get("summary") or "") for _ in [0])
    assert pres["findings"][0]["source_id"] == "blood-002"


def test_domain_query_displays_primary_entities_not_reasoning_context():
    expansion = HealthDomainResolver().expand("How is my liver?")
    assert "alt" in expansion.display_entities() or "alt" in expansion.primary
    assert "bmi" in expansion.reasoning_context() or "waist" in expansion.profile
    plan = build_query_plan("How is my liver?")
    assert "bmi" not in (plan.display_entities or [])
    ctx = ContextBuilder(build_registry()).build(AuthenticatedPrincipal(subject_id="demo-user-001"), plan)
    keys = {m.key for m in ctx.markers}
    body = client.post("/api/v1/chat", headers=H, json={"message": "How is my liver?"}).json()
    pres = body["presentation"]
    labels = " ".join(item["label"].lower() for item in pres.get("findings") or [])
    answer = body["answer"].lower()
    assert "alt" in labels or "alt" in answer or "ast" in labels or "bilirubin" in labels
    finding_keys = " ".join(pres.get("display_entities") or [])
    assert "bmi" not in finding_keys
    assert "waist" not in labels
    assert "bmi" not in answer
    assert "waist" not in answer


def test_meaning_request_uses_interpretation_mode():
    plan = build_query_plan("My B12 is high. What could explain it?")
    mode = infer_response_mode(
        plan,
        HealthContext(intent=plan.intent, answer_depth=plan.answer_depth, domains=list(plan.domains or [])),
        "My B12 is high. What could explain it?",
    )
    assert mode.value == "INTERPRETATION"
    body = client.post("/api/v1/chat", headers=H, json={"message": "My B12 is high. What could explain it?"}).json()
    assert body["presentation"]["mode"] == "INTERPRETATION"
    assert body["presentation"].get("interpretation") or "b12" in body["answer"].lower()


def test_simple_lookup_stays_concise():
    body = client.post("/api/v1/chat", headers=H, json={"message": "What is my TSH?"}).json()
    assert body["presentation"]["mode"] == "SINGLE_VALUE"
    assert "this is not a diagnosis" not in body["answer"].lower()
    assert len(body["answer"]) < 400


def test_high_selector_is_result_list():
    plan = build_query_plan("What markers are high?")
    assert plan.response_mode == "RESULT_LIST" or "HIGH" in plan.selectors
    body = client.post("/api/v1/chat", headers=H, json={"message": "What markers are high?"}).json()
    assert body["presentation"]["mode"] in {"RESULT_LIST", "DOMAIN_SUMMARY"}
    assert "diagnos" not in body["answer"].lower()
    assert body["presentation"].get("interpretation") in {None, ""}


def test_complex_review_is_structured_overview():
    body = client.post("/api/v1/chat", headers=H, json={"message": "Review my complete health."}).json()
    pres = body["presentation"]
    assert pres["mode"] == "HEALTH_OVERVIEW"
    assert pres.get("summary_style") == "NARRATIVE_HEALTH_SUMMARY"
    assert pres.get("overall_summary") or pres.get("summary")
    assert 3 <= len(pres.get("themes") or []) <= 5
    assert pres.get("findings") == []
    assert pres.get("raw_findings")
