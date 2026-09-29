#!/usr/bin/env python3
"""Live Jev evaluation. Does not run in the default pytest suite.

Usage from backend/:

    PYTHONPATH=.. python scripts/eval_jev_live.py

If OPENROUTER_API_KEY is missing, the script exits 2 and reports that live
Jev accuracy was not measured.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

from app.core.config import settings  # noqa: E402
from app.pipeline.query_planner import build_query_plan  # noqa: E402
from app.routing.jev_router import JEV_MIN_CONFIDENCE, resolve_plan  # noqa: E402


DATASET = ROOT / "backend" / "tests" / "fixtures" / "cura_capability_eval.jsonl"


def main() -> int:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    if not settings.jev_enabled:
        print("Jev is disabled (JEV_ENABLED=false). Live accuracy was not measured.")
        return 2
    if not settings.active_llm_api_key():
        print("OPENROUTER_API_KEY is not configured. Live Jev accuracy was not measured.")
        return 2

    accepted = 0
    low_conf = 0
    fallback = 0
    clarification = 0
    semantic_ok = 0
    for row in rows:
        det = build_query_plan(row["current_message"])
        plan, trace = resolve_plan(row["current_message"])
        conf = trace.decision.confidence if trace.decision else None
        if trace.fallback:
            fallback += 1
            if trace.fallback_reason == "low_confidence":
                low_conf += 1
        elif plan.intent.value == "ambiguous_clarification":
            clarification += 1
        elif conf is not None and conf >= JEV_MIN_CONFIDENCE:
            accepted += 1
        ok = (
            plan.intent.value == row["expected_intent"]
            and plan.needs_personal_data == row["personal_data_required"]
            and (not row["expected_metrics"] or plan.requested_metrics == row["expected_metrics"])
        )
        semantic_ok += int(ok)
        print(
            json.dumps(
                {
                    "id": row["id"],
                    "message": row["current_message"],
                    "expected_intent": row["expected_intent"],
                    "plan_intent": plan.intent.value,
                    "topic": plan.topic,
                    "requested_metrics": plan.requested_metrics,
                    "personal_data_required": plan.needs_personal_data,
                    "medical_evidence_required": plan.medical_evidence_required,
                    "jev_confidence": conf,
                    "fallback": trace.fallback,
                    "fallback_reason": trace.fallback_reason or plan.fallback_reason,
                    "deterministic_intent": det.intent.value,
                    "semantic_ok": ok,
                }
            )
        )
    total = len(rows)
    print(
        json.dumps(
            {
                "total": total,
                "accepted_jev": accepted,
                "low_confidence": low_conf,
                "fallback": fallback,
                "clarification": clarification,
                "fallback_rate": fallback / total if total else 0,
                "clarification_rate": clarification / total if total else 0,
                "semantic_accuracy": semantic_ok / total if total else 0,
                "threshold": JEV_MIN_CONFIDENCE,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
