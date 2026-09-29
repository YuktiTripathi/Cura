import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.query_planner import build_query_plan

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "eval_cases.json").read_text()
)["cases"]
H = {"X-Cura-User-Id": "demo-user-001"}
client = TestClient(app)


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["id"])
def test_production_golden_case(case):
    plan = build_query_plan(case["message"])
    body = client.post("/api/v1/chat", headers=H, json={"message": case["message"]}).json()

    if case.get("expected_intent"):
        assert body["meta"]["intent"] == case["expected_intent"]
    if case.get("expected_sources"):
        assert body["meta"]["sources_used"] == case["expected_sources"]
    if case.get("expected_status"):
        assert body["meta"]["status"] == case["expected_status"]
    if "expected_escalation" in case:
        assert body["meta"].get("escalation") == case["expected_escalation"]
    if case.get("expected_markers"):
        expected = set(case["expected_markers"])
        actual = {plan.topic} | {
            (row.get("marker") or "").lower().replace(" ", "_")
            for row in body.get("evidence", [])
        }
        assert expected & actual
    if case.get("expected_evidence"):
        assert body["evidence"]
    if case.get("expected_followups"):
        assert body["follow_ups"]
    for phrase in case.get("forbidden_substrings", []) + case.get("prohibited_claims", []):
        assert phrase.lower() not in body["answer"].lower()
    if case.get("must_include"):
        for phrase in case["must_include"]:
            assert phrase.lower() in body["answer"].lower()
    if case.get("must_include_any"):
        assert any(phrase.lower() in body["answer"].lower() for phrase in case["must_include_any"])
