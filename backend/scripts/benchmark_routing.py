"""Benchmark deterministic routing and optional live Jev Decisions routing."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.contracts.common import IntentType, QuerySource
from app.pipeline.intent import requires_personal_record
from app.pipeline.query_planner import build_query_plan
from app.routing.jev_client import JevDecisionsClient
from app.routing.mapper import plan_from_jev
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevRoutingState, JevSource, JevTimeRange
from app.routing.validator import JevDecisionValidationError, validate_jev_decision

DATASET = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "cura_routing_eval_500.jsonl"


def _rows(limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def _state(row: dict) -> JevRoutingState:
    return JevRoutingState(
        current_message=row["current_message"],
        previous_user_message=row.get("previous_user_message"),
        previous_intent=row.get("previous_intent"),
        previous_personal_data_used=row.get("previous_personal_data_used", False),
        current_topic=row.get("current_topic"),
        uploaded_document_available=row.get("uploaded_document_available", False),
        supported_capabilities=[
            "profile",
            "blood_reports",
            "lab_results",
            "bio_ai_report",
            "bio_ai_trends",
            "health_metrics",
            "uploaded_documents",
            "nutrition_preferences",
            "health_goals",
            "questionnaires",
        ],
    )


def _decision_from_plan(plan) -> JevDecision:
    intent = {
        IntentType.general_health_question: JevIntent.general_health_question,
        IntentType.latest_result: JevIntent.lab_result_lookup,
        IntentType.previous_result: JevIntent.health_trend_analysis,
        IntentType.trend: JevIntent.health_trend_analysis,
        IntentType.blood_marker_explanation: JevIntent.lab_result_interpretation,
        IntentType.bio_ai_score: JevIntent.bio_ai_report_lookup,
        IntentType.bio_ai_explanation: JevIntent.bio_ai_report_interpretation,
        IntentType.bio_ai_comparison: JevIntent.health_trend_analysis,
        IntentType.nutrition_guidance: JevIntent.nutrition_question,
        IntentType.ambiguous_clarification: JevIntent.clarification,
        IntentType.missing_data: JevIntent.unsupported,
    }.get(plan.intent, JevIntent.general_health_question)
    source = {
        QuerySource.blood: JevSource.lab_results,
        QuerySource.bio_ai: JevSource.bio_ai_report,
        QuerySource.lifestyle: JevSource.nutrition,
        QuerySource.user_uploaded: JevSource.uploaded_documents,
        QuerySource.mixed: JevSource.multiple_sources,
    }.get(plan.source, JevSource.none)
    operation = JevOperation.general_answer
    if plan.intent == IntentType.latest_result:
        operation = JevOperation.lookup
    elif plan.intent in {IntentType.blood_marker_explanation, IntentType.bio_ai_explanation}:
        operation = JevOperation.interpret
    elif plan.intent in {IntentType.trend, IntentType.bio_ai_comparison}:
        operation = JevOperation.trend
    elif plan.intent == IntentType.previous_result:
        operation = JevOperation.compare
    elif plan.intent == IntentType.ambiguous_clarification:
        operation = JevOperation.clarify
    time_range = JevTimeRange.none
    if plan.intent == IntentType.latest_result:
        time_range = JevTimeRange.latest
    elif plan.intent == IntentType.previous_result:
        time_range = JevTimeRange.previous
    elif plan.history:
        time_range = JevTimeRange.historical
    return JevDecision(
        intent=intent,
        source=source,
        operation=operation,
        requires_personal_data=plan.needs_personal_data,
        requires_historical_data=plan.history,
        requires_document_search=plan.needs_user_uploaded,
        requires_clarification=plan.intent == IntentType.ambiguous_clarification,
        time_range=time_range,
    )


def _score(rows: list[dict], decisions: list[JevDecision], *, latency_ms: float = 0, cost: float = 0, fallback: int = 0) -> dict:
    dimensions = {
        "intent": 0,
        "requires_personal_data": 0,
        "source": 0,
        "operation": 0,
        "requires_historical_data": 0,
        "requires_document_search": 0,
        "requires_clarification": 0,
        "time_range": 0,
    }
    false_positive_personal = false_negative_personal = 0
    for row, decision in zip(rows, decisions):
        expected = row["expected"]
        actual = decision.model_dump(mode="json")
        for key in dimensions:
            dimensions[key] += int(actual[key] == expected[key])
        if decision.requires_personal_data and not expected["requires_personal_data"]:
            false_positive_personal += 1
        if not decision.requires_personal_data and expected["requires_personal_data"]:
            false_negative_personal += 1
    total = len(rows)
    return {
        "cases": total,
        "accuracy": {key: round(value / total, 4) for key, value in dimensions.items()},
        "false_positive_personal": false_positive_personal,
        "false_negative_personal": false_negative_personal,
        "average_latency_ms": round(latency_ms / total, 2) if total else 0,
        "cost_usd": round(cost, 6),
        "fallback_count": fallback,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Call OpenRouter Jev Decisions API")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = _rows(args.limit)

    deterministic: list[JevDecision] = []
    for row in rows:
        plan = build_query_plan(
            row["current_message"],
            follow_up_topic=row.get("current_topic"),
            prior_personal=row.get("previous_personal_data_used", False),
            uploaded_document_count=1 if row.get("uploaded_document_available") else 0,
        )
        deterministic.append(_decision_from_plan(plan))
    report: dict = {"dataset": str(DATASET), "deterministic": _score(rows, deterministic)}

    if args.live:
        client = JevDecisionsClient()
        raw: list[JevDecision] = []
        validated: list[JevDecision] = []
        elapsed = cost = 0.0
        fallback = 0
        for row, baseline in zip(rows, deterministic):
            state = _state(row)
            started = time.perf_counter()
            try:
                decision, response = client.decide(state)
                elapsed += (time.perf_counter() - started) * 1000
                cost += response.usage.cost or 0
                raw.append(decision)
                try:
                    checked = validate_jev_decision(
                        decision,
                        state,
                        deterministic_requires_personal=requires_personal_record(
                            row["current_message"],
                            prior_personal=row.get("previous_personal_data_used", False),
                            follow_up_topic=row.get("current_topic"),
                        ),
                    )
                    plan = plan_from_jev(
                        checked,
                        row["current_message"],
                        follow_up_topic=row.get("current_topic"),
                        uploaded_document_count=1 if row.get("uploaded_document_available") else 0,
                    )
                    validated.append(_decision_from_plan(plan))
                except JevDecisionValidationError:
                    fallback += 1
                    validated.append(baseline)
            except Exception:
                elapsed += (time.perf_counter() - started) * 1000
                fallback += 1
                raw.append(baseline)
                validated.append(baseline)
        report["jev_raw"] = _score(rows, raw, latency_ms=elapsed, cost=cost, fallback=fallback)
        report["jev_validated"] = _score(
            rows, validated, latency_ms=elapsed, cost=cost, fallback=fallback
        )

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
