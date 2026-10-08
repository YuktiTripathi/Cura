#!/usr/bin/env python3
"""Semantic response examples: question -> raw answer -> backend JSON -> rendered outline.

Live (real answer model; your .env):
    CURA_RESPONSE_MODE=semantic python scripts/semantic_examples.py --user <subject_id>

Offline (mock data). The answer model is replaced by a SCRIPTED stand-in that returns,
per question, the kind of summary/blocks the prompt asks for, so the backend resolution,
validation and deterministic views can be checked end to end. The scripted text is not
CURA's prose; the values in every block are resolved by the backend from mock records.
    python scripts/semantic_examples.py --offline

Output: semantic_examples.md / .json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

QUESTIONS = [
    "Show me my latest blood report.",
    "What does my HbA1c mean?",
    "What should I actually pay attention to?",
    "What are the top 3 things I should work on?",
    "Why is my Bio-AI metabolic risk high?",
    "What is reassuring in my health data?",
    "Could my lifestyle be contributing?",
    "What nutrition changes make sense for my current results?",
    "Has my HbA1c improved?",
    "Is my TSH normal?",
    "Why am I feeling tired?",
    "Give me the short version.",
]

# Scripted stand-in outputs (offline only): meaning and evidence keys, never values.
SCRIPT = {
    "What does my HbA1c mean?": {
        "answer": "Your **HbA1c** reflects your average blood sugar over the last two to three months, and yours is above your report's range. Your glucose on the same report points the same way, so this is a consistent signal rather than a one-off.\n\nIt is worth discussing with your doctor; walking after meals and fewer refined carbs are good first steps.",
        "summary": "Your **HbA1c** shows your average blood sugar over the past 2–3 months, and yours is above your report's range.",
        "blocks": [
            {"type": "metric", "evidence": ["blood.hba1c.latest"]},
            {"type": "insight", "title": "It isn't a one-off", "text": "Your glucose on the same report points the same way, and HbA1c has risen since your last report.", "evidence": ["blood.glucose.latest", "blood.hba1c.trend"]},
        ],
    },
    "What should I actually pay attention to?": {
        "answer": "Blood sugar is the main thing to focus on, followed by your blood fats. Your iron markers are also low. Liver, kidney and thyroid results look reassuring.",
        "summary": "**Blood sugar** is the main area that needs attention, with blood fats close behind.",
        "blocks": [
            {"type": "priority_list", "title": "What stands out", "items": [
                {"title": "Blood sugar", "text": "HbA1c and glucose are both above range.", "evidence": ["blood.hba1c.latest", "blood.glucose.latest"]},
                {"title": "Blood fats", "text": "Triglycerides and LDL are high.", "evidence": ["blood.triglycerides.latest", "blood.ldl.latest"]},
                {"title": "Iron", "text": "Ferritin and haemoglobin are low.", "evidence": ["blood.ferritin.latest", "blood.hemoglobin.latest"]}]},
            {"type": "reassurance", "title": "What looks fine", "text": "Your liver, kidney and thyroid results are within range."},
        ],
    },
    "What are the top 3 things I should work on?": {
        "answer": "1. Blood sugar\n2. Blood fats\n3. Iron",
        "summary": "Here's where I'd start, in order.",
        "blocks": [
            {"type": "priority_list", "title": "Your top 3", "items": [
                {"title": "Bring blood sugar down", "evidence": ["blood.hba1c.latest"]},
                {"title": "Lower triglycerides and LDL", "evidence": ["blood.triglycerides.latest", "blood.ldl.latest"]},
                {"title": "Rebuild iron stores", "evidence": ["blood.ferritin.latest"]}]},
            {"type": "action_list", "title": "A first step for each", "items": [
                {"title": "A 10–15 minute walk after meals"}, {"title": "Swap refined grains for whole grains"},
                {"title": "Ask your doctor about the low iron"}]},
        ],
    },
    "Why is my Bio-AI metabolic risk high?": {
        "answer": "Your Bio-AI assessment rates type 2 diabetes and dyslipidemia risk high, and that matches your blood results: HbA1c, glucose and triglycerides are all above range. It is a risk estimate, not a diagnosis.",
        "summary": "Your Bio-AI risk lines up with your blood results; it is a risk estimate, not a diagnosis.",
        "blocks": [
            {"type": "risk", "title": "Risk overview", "evidence": ["bioai.type_2_diabetes", "bioai.dyslipidemia", "bioai.cardiac_health"]},
            {"type": "insight", "title": "Why this may be happening", "text": "Your HbA1c, glucose and triglycerides are all above range and point the same way.", "evidence": ["blood.hba1c.latest", "blood.glucose.latest", "blood.triglycerides.latest"]},
            {"type": "reassurance", "title": "What looks reassuring", "text": "Your HDL is within range."},
        ],
    },
    "What is reassuring in my health data?": {
        "answer": "Your liver, kidney and thyroid results are all within range, and HDL is normal.",
        "summary": "Quite a lot: your liver, kidney and thyroid results are all within range.",
        "blocks": [{"type": "reassurance", "title": "Within range", "text": "Liver enzymes, kidney function and thyroid markers are all within your report's ranges, and HDL is normal.", "evidence": ["blood.hdl.latest", "blood.tsh.latest", "blood.alt.latest"]}],
    },
    "Could my lifestyle be contributing?": {
        "answer": "It may be. You reported being rarely active, sitting more than 8 hours and mostly eating refined grains; all of these are associated with higher blood sugar and triglycerides. They are possible contributors, not proven causes.",
        "summary": "It may be: a few of the habits you reported are associated with higher blood sugar and triglycerides.",
        "blocks": [{"type": "action_list", "title": "Where small changes help most", "items": [
            {"title": "Move more often", "text": "You reported rarely exercising and sitting for long periods."},
            {"title": "Swap refined grains", "text": "Whole grains raise blood sugar more slowly."}]}],
    },
    "What nutrition changes make sense for my current results?": {
        "answer": "Focus on steadier blood sugar and lower triglycerides, and on iron-rich foods.",
        "summary": "I'd focus on foods that steady blood sugar and lower triglycerides, plus more iron.",
        "blocks": [{"type": "nutrition", "title": "Where I'd focus", "increase": ["Vegetables and pulses", "Whole grains", "Iron-rich foods such as lentils and leafy greens"], "reduce": ["Refined grains and sugary drinks", "Fried and processed snacks"], "text": "These support both your blood sugar and your blood fats; pair iron-rich foods with vitamin C."}],
    },
    "Has my HbA1c improved?": {
        "answer": "No, it has gone up since your previous report.",
        "summary": "No: your HbA1c has gone **up** since your previous report.",
        "blocks": [{"type": "comparison", "title": "Since your last report", "evidence": ["blood.hba1c.trend"]}],
    },
    "Why am I feeling tired?": {
        "answer": "Tiredness has many causes, but your low haemoglobin and ferritin are one possibility worth discussing with your doctor. Your thyroid is in range.",
        "summary": "There are many possible reasons, but your low iron markers are one worth discussing with your doctor.",
        "blocks": [
            {"type": "insight", "title": "One possibility in your results", "text": "Your haemoglobin and ferritin are below range, which can go with tiredness.", "evidence": ["blood.hemoglobin.latest", "blood.ferritin.latest"]},
            {"type": "reassurance", "text": "Your thyroid result is within range.", "evidence": ["blood.tsh.latest"]},
        ],
    },
}


def _configure(args) -> None:
    from app.core.config import settings

    settings.cura_response_mode = "semantic"
    settings.answer_cache_enabled = False
    settings.rate_limit_requests = 100000
    settings.member_daily_token_budget = 10**9
    if args.offline:
        from app.llm.models import LLMStructuredOutput
        from app.llm.openai_compatible import OpenAICompatibleLLMClient
        from app.providers.registry import set_registry

        settings.health_provider = "mock"
        settings.auth_provider = "mock"
        settings.allow_mock_header_override = True
        settings.dev_auth_header = True
        settings.supershyft_database_url = ""
        settings.jev_enabled = False
        settings.enable_llm = True
        settings.openrouter_api_key = settings.openrouter_api_key or "offline-stand-in"
        set_registry(None)
        state = {"last": None}

        def _scripted(self, messages):
            user = messages[-1]["content"]
            question = user.rsplit("User question:", 1)[-1].strip()
            scripted = SCRIPT.get(question)
            if scripted is None and question.lower().startswith("give me the short version") and state["last"]:
                prev = SCRIPT[state["last"]]
                scripted = {"answer": prev["summary"], "summary": prev["summary"], "blocks": []}
            if scripted is None:
                scripted = {"answer": "Stand-in answer.", "summary": "Stand-in answer.", "blocks": []}
            else:
                state["last"] = question if question in SCRIPT else state["last"]
            return LLMStructuredOutput(follow_up_questions=["What should I do first?"], **scripted)

        OpenAICompatibleLLMClient.complete_structured = _scripted


def _outline(semantic: dict | None) -> list[str]:
    if not semantic:
        return ["(no semantic response)"]
    lines = []
    for block in semantic["blocks"]:
        head = f"[{block['type']}{' collapsed' if block.get('collapsed') else ''}] {block.get('title') or ''}".rstrip()
        values = ", ".join(
            f"{v['label']} {v['value']}{(v.get('unit') or '')}{' (' + v['status'] + ')' if v.get('status') else ''}"
            + (f" was {v['previous']}" if v.get("previous") is not None else "")
            for v in block.get("values") or []
        )
        lines.append(head + (f" — {values}" if values else ""))
        for item in block.get("items") or []:
            item_values = ", ".join(f"{v['label']} {v['value']}{v.get('unit') or ''}" for v in item.get("values") or [])
            lines.append(f"    • {item.get('title') or item.get('text')}{' — ' + item_values if item_values else ''}")
        if block.get("increase") or block.get("reduce"):
            lines.append(f"    more: {', '.join(block['increase'])} | less: {', '.join(block['reduce'])}")
    return lines or ["(summary only)"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-companion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", default="semantic_examples")
    args = parser.parse_args()
    _configure(args)

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    conversation_id = None
    rows = []
    for question in QUESTIONS:
        # Each question starts fresh, except a style request, which continues the previous turn.
        continues = question.lower().startswith("give me the short version")
        payload = {"message": question, **({"conversation_id": conversation_id} if conversation_id and continues else {})}
        body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": args.user}, json=payload).json()
        conversation_id = body.get("conversation_id")
        rows.append({"question": question, "raw_answer": body.get("answer"), "semantic": body.get("semantic"),
                     "rendered": _outline(body.get("semantic"))})
    Path(args.out).with_suffix(".json").write_text(json.dumps(rows, indent=1))
    md = []
    for r in rows:
        md += [f"## {r['question']}", "", "**Raw answer (plain mode)**", "", r["raw_answer"] or "", "",
               "**Summary**", "", (r["semantic"] or {}).get("summary", ""), "", "**Rendered blocks**", "", "```", *r["rendered"], "```", ""]
    Path(args.out).with_suffix(".md").write_text("\n".join(md))
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
