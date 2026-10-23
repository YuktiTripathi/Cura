"""Score routing configs A/B/C on the hand-labeled PR7 set. Does not call a model."""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.pipeline.evidence_planner import reconcile_query_plan
from app.pipeline.query_planner import build_query_plan
from app.pipeline.safety import SafetyLayer
from app.pipeline.semantic_plan import build_semantic_plan
from app.routing.jev_router import _obvious_request
from evaluation.routing_benchmark.pr7_cases import CASES, HOLDOUT

OUT = Path(__file__).resolve().parents[2] / "evaluation" / "routing_benchmark" / "pr7_scores.json"


def family(plan) -> str:
    if plan.needs_cross_source:
        return "cross"
    if plan.needs_user_uploaded and not plan.needs_blood and not plan.needs_bio_ai:
        return "document"
    intent = plan.intent.value
    return {
        "general_health_question": "general",
        "casual_conversation": "general",
        "latest_result": "lookup",
        "blood_marker_explanation": "explain_marker",
        "report_explanation": "report",
        "broad_health_summary": "report",
        "bio_ai_score": "bio_lookup",
        "bio_ai_explanation": "bio_explain",
        "bio_ai_comparison": "bio_explain",
        "trend": "trend",
        "previous_result": "trend",
        "missing_data": "missing",
        "ambiguous_clarification": "clarify",
        "health_scenario": "report",
    }.get(intent, intent)


def sources(plan) -> set[str]:
    found = set()
    if plan.needs_blood or plan.needs_supershyft and plan.knowledge_scope.value == "personal" and not plan.needs_bio_ai and not plan.needs_user_uploaded:
        if plan.needs_blood:
            found.add("blood")
    if plan.needs_blood:
        found.add("blood")
    if plan.needs_bio_ai:
        found.add("bio")
    if plan.needs_user_uploaded:
        found.add("uploaded")
    if plan.knowledge_scope.value == "general" or plan.needs_general:
        found.add("general")
    if plan.needs_personal_data and not found:
        found.add("blood")
    return found


def path_of(plan) -> str:
    tier = getattr(plan.answer_model_tier, "value", None) or ""
    if plan.intent.value in {"latest_result", "bio_ai_score", "previous_result", "trend", "missing_data"}:
        return "lookup"
    if "DETERMINISTIC" in tier.upper() or tier == "":
        return "lookup" if plan.intent.value in {"latest_result", "bio_ai_score"} else "explain"
    return "explain"


def score_one(case: dict, plan) -> dict:
    got_intent = family(plan)
    got_sources = sources(plan)
    expected_sources = set(case["sources"])
    intent_ok = got_intent == case["intent"] or (
        case["intent"] == "safety_personal" and got_intent in {"explain_marker", "bio_explain", "lookup", "general"}
    ) or (
        case["intent"] == "isolation" and "general" in got_sources or got_intent == "general"
    ) or (
        case["intent"] == "clarify" and got_intent in {"clarify", "explain_marker", "trend", "report", "general"}
    )
    if expected_sources:
        precision = len(got_sources & expected_sources) / len(got_sources) if got_sources else 0.0
        recall = len(got_sources & expected_sources) / len(expected_sources)
    else:
        precision = 1.0 if not got_sources or got_sources == {"general"} else 0.0
        recall = 1.0
    return {
        "intent_ok": intent_ok,
        "got_intent": got_intent,
        "precision": precision,
        "recall": recall,
        "source_exact": got_sources == expected_sources or (not expected_sources and got_sources <= {"general"}),
    }


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) < 20 and pct >= 99:
        return None
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def score_set(cases: list[dict], safety: SafetyLayer) -> tuple[dict, list[dict]]:
    rows = []
    for case in cases:
        started = time.perf_counter()
        plan_c = build_query_plan(
            case["message"],
            case.get("follow_up"),
            prior_personal=bool(case.get("follow_up")),
            document_ids=["doc-1"] if case.get("document_ids") else None,
            uploaded_document_count=int(case.get("upload_count") or (1 if case.get("document_ids") else 0)),
        )
        route_ms = (time.perf_counter() - started) * 1000
        semantic = build_semantic_plan(
            case["message"],
            conversation_entities=[case["follow_up"]] if case.get("follow_up") else None,
            prior_personal=bool(case.get("follow_up")),
            has_documents=bool(case.get("document_ids")),
        )
        plan_b, changes = reconcile_query_plan(plan_c, semantic)
        obvious, _semantic = _obvious_request(plan_c, case["message"], None, ["doc-1"] if case.get("document_ids") else [])
        pre = safety.check_input(case["message"])
        safety_hit = pre.blocked and pre.category == "emergency"
        rows.append({
            "id": case["id"],
            "expected": case["intent"],
            "safety": case["safety"],
            "c": score_one(case, plan_c),
            "b": score_one(case, plan_b),
            "reconcile_changes": changes,
            "jev_would_call": not bool(obvious),
            "route_ms": round(route_ms, 2),
            "emergency_blocked": bool(safety_hit),
            "tier": str(getattr(plan_b.answer_model_tier, "value", None)),
        })

    def rate(key, field):
        return round(sum(1 for row in rows if row[key][field]) / len(rows), 3)

    def mean(key, field):
        return round(sum(row[key][field] for row in rows) / len(rows), 3)

    summary = {
        "n": len(rows),
        "intent_accuracy_b": rate("b", "intent_ok"),
        "intent_accuracy_c": rate("c", "intent_ok"),
        "source_precision_b": mean("b", "precision"),
        "source_recall_b": mean("b", "recall"),
        "source_precision_c": mean("c", "precision"),
        "source_recall_c": mean("c", "recall"),
        "source_exact_b": rate("b", "source_exact"),
        "source_exact_c": rate("c", "source_exact"),
        "reconcile_changed": sum(1 for row in rows if row["reconcile_changes"]),
        "jev_would_call": sum(1 for row in rows if row["jev_would_call"]),
        "emergency_n": sum(1 for row in rows if row["safety"] == "emergency"),
        "emergency_blocked": sum(1 for row in rows if row["safety"] == "emergency" and row["emergency_blocked"]),
        "route_p50": percentile([row["route_ms"] for row in rows], 50),
        "route_p95": percentile([row["route_ms"] for row in rows], 95),
        "route_p99": percentile([row["route_ms"] for row in rows], 99),
        "route_max": round(max(row["route_ms"] for row in rows), 2),
        "misses_b": Counter(row["expected"] for row in rows if not row["b"]["intent_ok"]),
        "helped": sum(1 for row in rows if row["b"]["intent_ok"] and not row["c"]["intent_ok"]),
        "harmed": sum(1 for row in rows if row["c"]["intent_ok"] and not row["b"]["intent_ok"]),
    }
    summary["misses_b"] = dict(summary["misses_b"])
    return summary, rows


def main() -> None:
    settings.jev_enabled = False
    settings.enable_llm = False
    safety = SafetyLayer()
    summary, rows = score_set(CASES, safety)
    hold_summary, hold_rows = score_set(HOLDOUT, safety)
    OUT.write_text(json.dumps({"summary": summary, "holdout": hold_summary, "rows": rows, "holdout_rows": hold_rows}, indent=2))
    print(json.dumps({"dev": summary, "holdout": hold_summary}, indent=2))


if __name__ == "__main__":
    main()
