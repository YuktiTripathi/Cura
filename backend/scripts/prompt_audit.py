#!/usr/bin/env python3
"""Prompt-size audit: what CURA sends to the answer model for given questions.

Uses the dev-only prompt inspector (app/llm/prompt_inspector.py) on the real request
path. Nothing about the request is changed.

Offline (mock data; only the HTTP transport is stubbed, so the real payload builder runs;
no provider usage, so tokens are tokenizer counts or chars/4 estimates):
    python scripts/prompt_audit.py --offline

Live (your .env; provider-reported input/output tokens and real latency are recorded):
    python scripts/prompt_audit.py --user <subject_id>

Writes prompt_audit.md / prompt_audit.json plus one sectioned dump per model call in
CURA_PROMPT_DEBUG_DIR (default .prompt_debug/). The dumps contain health values: local
development only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

QUESTIONS = [
    ("focus", "What does my HbA1c mean?"),
    ("simple", "What is my Vitamin D?"),
    ("medium", "Why are my triglycerides high?"),
    ("complex", "Why is my Bio-AI metabolic risk high even though some of my blood markers are normal?"),
]

# Guidance families that may be stated more than once across the request.
REPEATED = {
    "do not diagnose": r"\b(?:do not|don't|never) diagnos\w*|not a diagnosis|never as a diagnosis|as diagnoses\b",
    "do not prescribe / medication": r"\bprescrib\w*|medication|dose changes?\b",
    "use the report's own range": r"\breport(?:'s)? (?:own )?range|reference range from the user's report|range printed on the member's own report|generic range\b",
    "keep values and units unchanged": r"\b(?:keep|keeping) (?:values and units|medical terms and numbers|any number|every number)\w* (?:unchanged|exactly)|unchanged\b",
    "do not invent data": r"\b(?:never|do not|don't) (?:invent|guess)\w*|do not invent\b",
    "lead with the direct answer": r"\blead with|answer the (?:user's )?question first|first one or two sentences must answer|start with the answer\b",
    "don't list unrelated markers": r"\bunrelated (?:biomarkers|results)|do not list every|walk through every result|dump unrelated|at most a few directly related\b",
    "questionnaire is self-reported, not a lab / not a cause": r"\bquestionnaire\w*[^.]{0,80}(?:user-reported|self-reported|not (?:a )?lab|caused|cause)\b",
    "Bio-AI is an assessment, not a diagnosis": r"\bbio[- ]?ai[^.]{0,60}(?:assessment|not (?:a )?diagnos)\w*",
    "missing data: mention only if it matters": r"\bmissing (?:data|information|supporting tests)?[^.]{0,60}(?:only|once)\b",
    "no emergency language for routine labs": r"\bemergency\b|red[- ]flag\b",
    "be concise / conversational": r"\bconcise|conversational|compact\b",
    "do not repeat what was already explained": r"\balready (?:explained|given|discussed)|do not repeat\b",
    "possibilities are not causes/diagnoses": r"\bpossibilit\w+ as (?:the cause|diagnos\w*)|imply causality|never present a possibility\b",
}


def _configure(args) -> None:
    from app.core.config import settings

    settings.cura_prompt_debug = True
    settings.app_env = "development"
    settings.answer_cache_enabled = False
    settings.rate_limit_requests = 100000
    settings.member_daily_token_budget = 10**9
    settings.cura_response_mode = args.mode
    if args.offline:
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

        import app.llm.openai_compatible as client_module

        class _Response:
            status_code = 200

            def json(self):
                answer = {"answer": "Stand-in answer.", "follow_up_questions": []}
                return {"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}], "usage": {}}

        class _Transport:
            def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002 - httpx signature
                return _Response()

        client_module.get_http_client = lambda: _Transport()


def _repeats(texts: dict[str, str]) -> dict:
    found = {}
    for family, pattern in REPEATED.items():
        rx = re.compile(pattern, re.I)
        where = {k: len(rx.findall(v)) for k, v in texts.items() if rx.search(v)}
        total = sum(where.values())
        if total >= 2:
            found[family] = {"total": total, "by_component": where}
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-companion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--mode", choices=["plain", "rich"], default="plain")
    parser.add_argument("--out", default="prompt_audit")
    args = parser.parse_args()
    _configure(args)

    from fastapi.testclient import TestClient

    from app.llm import prompt_inspector
    from app.main import app

    client = TestClient(app)
    rows = []
    for label, question in QUESTIONS:
        prompt_inspector.RECENT.clear()
        started = time.perf_counter()
        body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": args.user}, json={"message": question}).json()
        wall = int((time.perf_counter() - started) * 1000)
        audits = list(prompt_inspector.RECENT)
        if not audits:
            rows.append({"label": label, "question": question, "model_called": False, "total_ms": wall})
            continue
        audit = audits[-1]
        dump = Path(audit["dump"]).read_text() if audit.get("dump") else ""
        texts = {}
        for block in re.split(r"^===== ", dump, flags=re.M)[1:]:
            title, _, text = block.partition("\n")
            texts[title.split(" (")[0].strip(" =")] = text
        usage = audit.get("provider_usage") or {}
        rows.append({
            "label": label,
            "question": question,
            "model_called": True,
            "answer_model_calls": len(audits),
            "model": audit["model"],
            "format": audit["format"],
            "token_method": audit["token_method"],
            "components": audit["components"],
            "output_schema": audit["output_schema"],
            "request_parameters": audit["request_parameters"],
            "health": audit.get("health_context_breakdown"),
            "estimated_input_tokens": audit["estimated_input_tokens"],
            "total_input_chars": audit["total_input_chars"],
            "provider_input_tokens": usage.get("input_tokens"),
            "provider_output_tokens": usage.get("output_tokens"),
            "answer_model_ms": audit["latency_ms"],
            "total_ms": wall,
            "repeated_guidance": _repeats(texts),
            "dump": audit.get("dump"),
        })
    Path(args.out).with_suffix(".json").write_text(json.dumps(rows, indent=1, default=str))
    print(json.dumps([{k: v for k, v in r.items() if k in {"label", "model", "estimated_input_tokens", "dump"}} for r in rows], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
