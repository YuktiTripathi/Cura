import json
from pathlib import Path

from app.pipeline.query_planner import build_query_plan


DATASET = Path(__file__).resolve().parents[1] / "fixtures" / "cura_capability_eval.jsonl"

METRIC_ALIASES = {
    "glucose": {"glucose", "fasting_blood_glucose"},
    "fasting_blood_glucose": {"glucose", "fasting_blood_glucose"},
    "hemoglobin": {"hemoglobin", "hb"},
}

SOURCE_FLAGS = {
    "blood_reports": "needs_blood",
    "bio_ai_report": "needs_bio_ai",
    "questionnaire": "needs_questionnaire",
    "goals": "needs_goals",
}

OP_ALIASES = {
    "latest_marker": {"RETRIEVE", "LOOKUP", "EXPLAIN"},
    "lookup": {"RETRIEVE", "LOOKUP"},
    "compare": {"COMPARE"},
    "latest_report": {"RETRIEVE", "SUMMARIZE", "EXPLAIN"},
    "summarize": {"SUMMARIZE"},
    "correlate": {"CORRELATE", "IDENTIFY_PATTERN"},
}


def _rows():
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]


def _has_metric(got: list[str], expected: str) -> bool:
    aliases = METRIC_ALIASES.get(expected, {expected})
    return any(item in got for item in aliases)


def test_capability_eval_compositional_routing():
    failures = []
    for row in _rows():
        plan = build_query_plan(row["current_message"])
        got_metrics = list(plan.requested_metrics or [])
        ops = {str(item).upper() for item in (plan.operations or [])}
        ops.add(str(plan.operation or "").upper())

        expected_metrics = row.get("expected_metrics") or row.get("expected_entities") or []
        if expected_metrics:
            missing = [item for item in expected_metrics if not _has_metric(got_metrics, item)]
            if missing:
                failures.append((row["id"], "entities", got_metrics, expected_metrics))

        expected_ops = row.get("expected_operations") or []
        if expected_ops:
            wanted = {str(item).upper() for item in expected_ops}
            if not (ops & wanted):
                failures.append((row["id"], "operations", sorted(ops), expected_ops))
        elif row.get("expected_operation"):
            aliases = OP_ALIASES.get(str(row["expected_operation"]).lower(), {str(row["expected_operation"]).upper()})
            if ops and not (ops & {item.upper() for item in aliases}):
                failures.append((row["id"], "operation", sorted(ops), row["expected_operation"]))

        source = row.get("expected_data_source")
        if source in SOURCE_FLAGS:
            if not getattr(plan, SOURCE_FLAGS[source]):
                failures.append((row["id"], "source", source, SOURCE_FLAGS[source]))
        elif source == "general":
            if plan.needs_personal_data and not row.get("personal_data_required"):
                failures.append((row["id"], "source", "general", "personal lookup"))

        for src in row.get("expected_sources") or []:
            flag = {"blood": "needs_blood", "bio_ai": "needs_bio_ai", "questionnaire": "needs_questionnaire", "goals": "needs_goals"}.get(src)
            if flag and not getattr(plan, flag):
                failures.append((row["id"], "sources", src, False))

        if plan.needs_personal_data != row["personal_data_required"]:
            failures.append((row["id"], "personal", plan.needs_personal_data, row["personal_data_required"]))
        if plan.medical_evidence_required != row["medical_evidence_required"]:
            failures.append((row["id"], "evidence", plan.medical_evidence_required, row["medical_evidence_required"]))

        expected_q = row.get("expected_question_type")
        if expected_q and plan.question_type and plan.question_type != expected_q:
            failures.append((row["id"], "question_type", plan.question_type, expected_q))
    assert failures == []
