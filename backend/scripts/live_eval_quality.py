"""Response quality evaluation against the live configured model. Run locally with your own credential.

    export OPENROUTER_API_KEY=...          # or LLM_API_KEY; read by app settings, never printed or written
    cd backend
    ENABLE_LLM=true MEMBER_SNAPSHOT_ENABLED=true PYTHONPATH=..:. \
        python scripts/live_eval_quality.py --out /tmp/quality_eval.md [--user demo-user-001] [--contrasting]

For every question it records: the model that answered, the assembled system prompt, the dynamic user
context, the RAW model answer, the FINAL validated answer, the follow-ups, the post-generation steps that
changed the text, latency and token use (including cached tokens). It asserts nothing about quality: read it.
The contrasting section sends identical measurements with different verified profiles straight to the model.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from fastapi.testclient import TestClient

from app.core.config import settings

QUESTIONS = [
    "What is Vitamin B12?",
    "Why is my Vitamin B12 low?",
    "Why is my B12 low despite eating animal foods?",
    "How does my physical activity relate to my cholesterol?",
    "Why is my cardiac risk increased?",
    "What should I eat based on my reports?",
    "Explain how my thyroid works.",
    "How are TSH, T3 and T4 connected?",
    "Why is my vitamin D low?",
    "Explain that more simply.",
]
CONTRAST = [
    ("Why is my Vitamin B12 low?", [("vegetarian", {"diet_preference": "Vegetarian"}), ("non vegetarian", {"diet_preference": "Non vegetarian"})]),
    ("Why is my HDL low?", [("inactive", {"physical_activity_frequency": "Rarely", "exercise_frequency_week": "0-1 days"}), ("active", {"physical_activity_frequency": "Daily", "exercise_frequency_week": "5-6 days"})]),
]


def _install_recorder(calls: list[dict]):
    from app.llm import openai_compatible as oc

    original = oc.OpenAICompatibleLLMClient.complete_structured

    def recorded(self, messages):
        started = time.perf_counter()
        error = None
        result = None
        try:
            result = original(self, messages)
            return result
        except Exception as exc:  # noqa: BLE001
            error = type(exc).__name__
            raise
        finally:
            calls.append({
                "model": getattr(self, "model", None),
                "system": next((m["content"] for m in messages if m["role"] == "system"), ""),
                "user": next((m["content"] for m in messages if m["role"] == "user"), ""),
                "raw_answer": getattr(result, "answer", None),
                "raw_follow_ups": getattr(result, "follow_up_questions", None),
                "seconds": round(time.perf_counter() - started, 2),
                "usage": dict(getattr(self, "last_usage", {}) or {}),
                "error": error,
            })

    oc.OpenAICompatibleLLMClient.complete_structured = recorded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="demo-user-001")
    parser.add_argument("--out", default="quality_eval.md")
    parser.add_argument("--contrasting", action="store_true")
    args = parser.parse_args()
    if not settings.active_llm_api_key():
        print("No model credential in the environment. Set OPENROUTER_API_KEY or LLM_API_KEY and rerun.")
        return 2
    settings.enable_llm = True
    settings.member_snapshot_enabled = True
    calls: list[dict] = []
    _install_recorder(calls)
    from app.main import app

    client = TestClient(app)
    headers = {"X-Cura-User-Id": args.user}
    out = ["# Response quality evaluation (live model)", f"user: {args.user}", ""]
    conversation = None
    for number, question in enumerate(QUESTIONS, 1):
        calls.clear()
        body = {"message": question}
        if question.startswith("Explain that") and conversation:
            body["conversation_id"] = conversation
        started = time.perf_counter()
        response = client.post("/api/v1/chat", headers=headers, json=body).json()
        wall = time.perf_counter() - started
        conversation = response.get("conversation_id") or conversation
        meta = response.get("meta") or {}
        answered = next((c for c in reversed(calls) if c["raw_answer"]), None)
        out += [f"## {number}. {question}", f"wall seconds {wall:.1f}; status {meta.get('status')}; model calls {len(calls)}"]
        if answered:
            out += [
                f"model {answered['model']}; call seconds {answered['seconds']}; usage {json.dumps(answered['usage'])}",
                "", "### System prompt", "```", answered["system"], "```",
                "### Dynamic context (user message)", "```", answered["user"], "```",
                "### Raw model answer", answered["raw_answer"], "",
                "raw follow ups: " + " | ".join(answered["raw_follow_ups"] or []),
            ]
        else:
            out += ["No model answer was produced (unavailable or fallback); the final answer below is deterministic."]
        trace = ((meta.get("debug") or {}).get("answer_transformations") or [])
        out += [
            "", "### Final validated answer", response.get("answer") or "", "",
            "final follow ups: " + " | ".join(f.get("text", "") for f in response.get("follow_ups") or []),
            "post-generation steps that changed the text: " + (json.dumps(trace) if trace else "none reported"),
            "raw equals final: " + str(bool(answered) and (answered["raw_answer"] or "").strip() == (response.get("answer") or "").strip()),
            "",
        ]
    if args.contrasting:
        # This block is not a CURA chat evaluation. It calls the model directly with two profiles.
        out += [
            "# Contrasting profiles (direct model call, not the CURA chat pipeline)",
            "The sections above came from POST /api/v1/chat. The sections below skip routing, retrieval, safety and grounding.",
            "",
        ]
        from app.llm.factory import get_llm_client
        from app.pipeline.prompt_builder import PromptBuilder
        from tests.unit.test_answer_quality import _context

        out += ["The profiles below use identical measurements and are not passed through POST /api/v1/chat.", ""]
        llm = get_llm_client(personal_health=True)
        for question, profiles in CONTRAST:
            for label, answers in profiles:
                ctx = _context(question, answers)
                messages = PromptBuilder().build(ctx, "", question)
                calls.clear()
                try:
                    result = llm.complete_structured(messages) if llm else None
                    text = getattr(result, "answer", "") if result else "no client"
                except Exception as exc:  # noqa: BLE001
                    text = f"model error: {type(exc).__name__}"
                out += [f"## {question} | {label}", text, ""]
    pathlib.Path(args.out).write_text("\n".join(out))
    print(f"Wrote {args.out}. Review it yourself; nothing here asserts live quality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
