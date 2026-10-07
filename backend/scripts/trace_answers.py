#!/usr/bin/env python3
"""Where is answer quality lost? Capture every stage of the answer for a question set.

For each question: semantic plan, selected evidence (what the model sees), the raw prompt,
the raw model answer, the answer after validation/safety, after the composer, and the final
visible text, plus the path (model vs deterministic template) and latency by stage.

Live (your .env with OPENROUTER_API_KEY, HEALTH_PROVIDER=supershyft):
    python scripts/trace_answers.py --user <subject_id> --mode plain
Offline (mock data; a recognisable stand-in model shows exactly what the pipeline does to
model text; no real model prose):
    python scripts/trace_answers.py --offline --user eval-user-companion --mode rich

Output: trace_<mode>.json and trace_<mode>.md. Subject ids and names are not written.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

QUESTIONS: list[list[str]] = [
    ["Show me my latest blood report."],
    ["What should I actually pay attention to in my latest report?"],
    ["What are the top 3 things I should work on?"],
    ["Why is my Bio-AI metabolic risk high?"],
    ["Why are my triglycerides high?", "Is that because of my sugar?", "What should I change first?"],
    ["What is reassuring in my report?"],
    ["Do my blood report and Bio-AI report tell the same story?"],
    ["What changed compared with my previous report?"],
    ["What should I focus on first?"],
    ["Could my lifestyle be contributing?"],
    ["Which result needs the most attention?"],
    ["Which abnormal values probably matter less?"],
    ["What should I discuss with my doctor?"],
    ["Why is my risk high even though some markers are normal?"],
    ["What is my HbA1c?"],
]

STAND_IN = (
    "STAND-IN MODEL ANSWER. This paragraph is what the answer model wrote; anything else in the final "
    "answer was added by the pipeline after the model."
)
_CAPTURE: dict = {}


def _configure(args) -> None:
    from app.core.config import settings

    settings.answer_cache_enabled = False
    settings.rate_limit_requests = 100000
    if args.mode:
        settings.cura_response_mode = args.mode
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

        def _fake(self, messages):
            _CAPTURE["prompt"] = messages
            # Name the facts the model was given (a real model would), so grounding checks
            # behave as they would in production and only real pipeline effects show.
            content = messages[1]["content"] if len(messages) > 1 else ""
            names = list(dict.fromkeys(re.findall(r'"name":"([^"]+)"', content)))[:4]
            mention = f" It discusses: {', '.join(names)}." if names else ""
            return LLMStructuredOutput(answer=STAND_IN + mention)

        OpenAICompatibleLLMClient.complete_structured = _fake
    else:
        from app.llm.openai_compatible import OpenAICompatibleLLMClient

        original = OpenAICompatibleLLMClient.complete_structured

        def _spy(self, messages):
            _CAPTURE["prompt"] = messages
            return original(self, messages)

        OpenAICompatibleLLMClient.complete_structured = _spy


def _redact(text: str, user: str) -> str:
    return (text or "").replace(user, "<subject>")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-companion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--mode", choices=["plain", "rich"], default="plain")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    _configure(args)
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    rows = []
    for turns in QUESTIONS:
        conversation_id = None
        for question in turns:
            _CAPTURE.clear()
            payload = {"message": question}
            if conversation_id:
                payload["conversation_id"] = conversation_id
            body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": args.user}, json=payload).json()
            conversation_id = body.get("conversation_id")
            meta = body.get("meta") or {}
            debug = meta.get("debug") or {}
            stages = debug.get("answer_stages") or {}
            prompt = _CAPTURE.get("prompt") or []
            rows.append({
                "question": question,
                "follow_up_of": turns[0] if question != turns[0] else None,
                "intent": meta.get("intent"),
                "semantic": {k: (debug.get("semantic_plan") or {}).get(k) for k in (
                    "primary_goal", "secondary_goals", "health_topics", "required_sources", "plan_corrections")},
                "path": stages.get("path"),
                "model_tier": stages.get("model_tier"),
                "selected_context": _redact(prompt[1]["content"], args.user) if len(prompt) > 1 else None,
                "raw_prompt_chars": sum(len(m.get("content") or "") for m in prompt),
                "raw_llm_answer": stages.get("raw_llm_answer"),
                "reasoner_answer": stages.get("reasoner_answer"),
                "post_validator_answer": stages.get("post_validator_answer"),
                "post_composer_answer": stages.get("post_composer_answer"),
                "final_answer": body.get("answer"),
                "frontend_extras": {
                    "presentation": bool(body.get("presentation")),
                    "follow_ups": len(body.get("follow_ups") or []),
                    "testing_option": bool(body.get("testing_option")),
                    "recommendations": len(body.get("recommendations") or []),
                },
                "latency_ms": {k: v for k, v in ((meta.get("timing") or {}).get("stages") or {}).items()
                               if k.endswith("_ms")},
            })
    out = Path(args.out or f"trace_{args.mode}.json")
    out.write_text(json.dumps(rows, indent=1))
    md = [f"# Answer trace ({args.mode} mode{' , offline stand-in model' if args.offline else ''})", ""]
    for r in rows:
        added = ""
        if r["raw_llm_answer"] and r["final_answer"] and r["final_answer"].strip() != r["raw_llm_answer"].strip():
            added = " — FINAL DIFFERS FROM MODEL ANSWER"
        md += [f"## {r['question']}", "",
               f"intent `{r['intent']}` · goal `{r['semantic'].get('primary_goal')}` · path `{r['path']}` · tier `{r['model_tier']}`{added}",
               "", "**Final visible answer**", "", "```", (r["final_answer"] or "").strip(), "```", "",
               f"Extras sent to the frontend: {r['frontend_extras']}", ""]
    Path(out.with_suffix(".md")).write_text("\n".join(md))
    print(f"wrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
