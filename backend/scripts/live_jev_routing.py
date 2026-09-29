"""Live Jev routing probe. Requires OPENROUTER_API_KEY. Prints traces only, not secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routing.jev_router import resolve_plan

CASES = [
    ("standalone", "What is the difference between HDL and LDL?", False, None, "", None, None),
    ("standalone", "What lifestyle changes can help lower my LDL levels?", False, None, "", None, None),
    ("standalone", "What is my LDL?", False, None, "", None, None),
    ("standalone", "Is my LDL high?", False, None, "", None, None),
    ("standalone", "What was my LDL previously?", False, None, "", None, None),
    ("standalone", "What foods can help lower cholesterol?", False, None, "", None, None),
    ("standalone", "How can I improve my HDL?", False, None, "", None, None),
    ("standalone", "What does my blood report say about LDL?", False, None, "", None, None),
    (
        "after personal LDL",
        "What about mine?",
        True,
        "ldl",
        "Prior: user asked what is my LDL (personal result).",
        "What is my LDL?",
        "latest_result",
    ),
    (
        "after personal LDL",
        "What was the previous one?",
        True,
        "ldl",
        "Prior: user asked what is my LDL (personal result).",
        "What is my LDL?",
        "latest_result",
    ),
    (
        "after general HDL vs LDL",
        "What lifestyle changes can help lower my LDL levels?",
        False,
        "ldl",
        "Prior: difference between HDL and LDL (general education).",
        "What is the difference between HDL and LDL?",
        "general_health_question",
    ),
]


def main() -> int:
    rows = []
    for label, message, prior, topic, summary, previous, previous_intent in CASES:
        plan, trace = resolve_plan(
            message,
            conversation_summary=summary,
            previous_user_message=previous,
            previous_intent=previous_intent,
            follow_up_topic=topic,
            prior_personal=prior,
        )
        decision = trace.decision
        row = {
            "case": label,
            "message": message,
            "jev_called": trace.called,
            "fallback": trace.fallback,
            "fallback_reason": trace.fallback_reason,
            "jev_intent": decision.intent.value if decision else None,
            "jev_source": decision.source.value if decision else None,
            "jev_requires_personal_data": None if not decision else decision.requires_personal_data,
            "jev_requires_retrieval": None if not decision else decision.requires_retrieval,
            "plan_intent": plan.intent.value,
            "plan_source": plan.source.value,
            "needs_personal_data": plan.needs_personal_data,
            "needs_supershyft": plan.needs_supershyft,
            "history": plan.history,
            "latency_ms": trace.latency_ms,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=True))
    return 0 if all(r["jev_called"] for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
