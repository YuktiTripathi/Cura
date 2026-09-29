import json
from pathlib import Path

from app.pipeline.query_planner import build_query_plan


DATASET = Path(__file__).resolve().parents[1] / "fixtures" / "cura_capability_eval.jsonl"


def _rows():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]


def test_capability_eval_deterministic_routing():
    failures = []
    for row in _rows():
        plan = build_query_plan(row["current_message"])
        if plan.intent.value != row["expected_intent"]:
            failures.append((row["id"], "intent", plan.intent.value, row["expected_intent"]))
        if row["expected_topic"] and plan.topic not in {row["expected_topic"], *(row["expected_metrics"] or [])}:
            failures.append((row["id"], "topic", plan.topic, row["expected_topic"]))
        expected_metrics = row["expected_metrics"]
        if expected_metrics and plan.requested_metrics != expected_metrics:
            failures.append((row["id"], "metrics", plan.requested_metrics, expected_metrics))
        if plan.needs_personal_data != row["personal_data_required"]:
            failures.append((row["id"], "personal", plan.needs_personal_data, row["personal_data_required"]))
        if plan.medical_evidence_required != row["medical_evidence_required"]:
            failures.append((row["id"], "evidence", plan.medical_evidence_required, row["medical_evidence_required"]))
    assert failures == []
