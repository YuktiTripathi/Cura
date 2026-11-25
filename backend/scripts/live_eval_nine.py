"""Run the nine V2 acceptance questions against the real model, locally.

Usage (from backend/, with your own credentials in the environment, never in a file):

    export OPENROUTER_API_KEY=...        # or LLM_API_KEY
    ENABLE_LLM=true MEMBER_SNAPSHOT_ENABLED=true \
        PYTHONPATH=..:. python scripts/live_eval_nine.py [--user demo-user-001] [--out /tmp/live_eval.md]

The key is read by the app settings and is never printed, logged or written. The report holds the question,
the answer, the visible follow-ups, wall time and, when the provider reports it, token use. It does not
claim quality: read the answers yourself against docs/cura_v2/UNIFIED_MEDICAL_EDUCATION_AND_PERSONALISATION.md.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

from fastapi.testclient import TestClient

from app.core.config import settings

QUESTIONS = [
    "Why is my Vitamin B12 low?",
    "What can I do to protect my nutrition?",
    "What does my Vitamin D result mean?",
    "Why is my HDL low?",
    "How does my physical activity relate to my cholesterol?",
    "What does my thyroid Bio-AI assessment mean?",
    "What is haemoglobin?",
    "What should I eat if I follow a vegetarian diet?",
    "Explain that more simply.",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="demo-user-001")
    parser.add_argument("--out", default="live_eval.md")
    args = parser.parse_args()
    if not settings.active_llm_api_key():
        print("No model credential in the environment. Set OPENROUTER_API_KEY or LLM_API_KEY and rerun.")
        return 2
    settings.enable_llm = True
    settings.member_snapshot_enabled = True
    from app.main import app

    client = TestClient(app)
    headers = {"X-Cura-User-Id": args.user}
    lines = ["# Live evaluation", f"user: {args.user}", ""]
    conversation = None
    for number, question in enumerate(QUESTIONS, 1):
        body = {"message": question}
        if number == 9 and conversation:
            body["conversation_id"] = conversation
        started = time.perf_counter()
        response = client.post("/api/v1/chat", headers=headers, json=body).json()
        elapsed = time.perf_counter() - started
        conversation = response.get("conversation_id") or conversation
        meta = response.get("meta") or {}
        lines += [
            f"## {number}. {question}",
            f"wall seconds: {elapsed:.1f}; model called: {meta.get('llm_called')}; status: {meta.get('status')}",
            "",
            response.get("answer") or "",
            "",
            "follow ups: " + " | ".join(f.get("text", "") for f in response.get("follow_ups") or []),
            "",
        ]
    pathlib.Path(args.out).write_text("\n".join(lines))
    print(f"Wrote {args.out}. Review it yourself; nothing here asserts live quality.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
