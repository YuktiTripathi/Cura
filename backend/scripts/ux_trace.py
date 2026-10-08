#!/usr/bin/env python3
"""Where does verbosity come from? Trace one question through every visible stage.

For each question: intent, sources, markers/context passed to the model, raw model
answer, post-safety answer, final backend answer, frontend-visible components,
input/output tokens and latency.

Live (real model, your .env):   python scripts/ux_trace.py --user <id> [--mode rich|plain|semantic]
Offline (mock data; a fixed VERBOSE stand-in answer, identical across runs, so any
change in the final answer comes from the pipeline, not the model):
                                python scripts/ux_trace.py --offline
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
    "What does my Cardiac Health score mean?",
    "What happens if my Vitamin D is low?",
    "Am I physically active enough for my current health situation?",
    "What do you understand from my blood reports?",
]
EM = "—"
# A deliberately verbose answer in the style of the reported screenshots.
VERBOSE = (
    f"Cardiovascular health can be influenced by many different factors {EM} and the available evidence does not establish a single cause.\n\n"
    f"Your result is above its reference level {EM} this is a risk estimate, not a diagnosis. "
    "It is not a medical diagnosis and clinician interpretation is required. "
    "Please discuss this with your doctor. You may also want to talk to your clinician.\n\n"
    "That marker was not available. Reference range: None to None.\n\n"
    f"Cardiovascular health can be influenced by many different factors {EM} and the available evidence does not establish a single cause."
)
_CAPTURE: dict = {}


def _configure(args) -> None:
    from app.core.config import settings

    settings.answer_cache_enabled = False
    settings.rate_limit_requests = 100000
    settings.member_daily_token_budget = 10**9
    settings.cura_response_mode = args.mode
    from app.llm.openai_compatible import OpenAICompatibleLLMClient

    if args.offline:
        from app.llm.models import LLMStructuredOutput
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
            _CAPTURE.update(messages=messages, model=self.model, raw=VERBOSE)
            self.last_usage = {"input_tokens": sum(len(m["content"]) for m in messages) // 4, "output_tokens": len(VERBOSE) // 4}
            return LLMStructuredOutput(answer=VERBOSE, follow_up_questions=["Do you have any new symptoms?", "What drives it?"])

        OpenAICompatibleLLMClient.complete_structured = _fake
    else:
        original = OpenAICompatibleLLMClient.complete_structured

        def _spy(self, messages):
            result = original(self, messages)
            _CAPTURE.update(messages=messages, model=self.model, raw=result.answer)
            return result

        OpenAICompatibleLLMClient.complete_structured = _spy


def _context_markers(messages) -> dict:
    user = messages[-1]["content"] if messages else ""
    start = user.find("ANSWER EVIDENCE JSON:")
    if start >= 0:
        payload = json.loads(user[start + 22: user.find("\n", start + 23)])
        codes = lambda key: [f.get("code") for f in payload.get(key) or []]
        return {"primary": codes("primary_facts"), "supporting": codes("supporting_facts"),
                "patterns": [p.get("pattern") for p in payload.get("patterns") or []],
                "questionnaire": bool(payload.get("questionnaire_context"))}
    codes = sorted(set(re.findall(r'"(?:key|code)":"([a-z0-9_]+)"', user)))
    return {"codes_in_prompt": codes[:30], "count": len(codes)}


def _words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-companion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--mode", choices=["rich", "plain", "semantic"], default="rich")
    parser.add_argument("--out", default="ux_trace.json")
    args = parser.parse_args()
    _configure(args)
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    rows = []
    for question in QUESTIONS:
        _CAPTURE.clear()
        started = time.perf_counter()
        body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": args.user}, json={"message": question}).json()
        wall = int((time.perf_counter() - started) * 1000)
        meta = body.get("meta") or {}
        stages = ((meta.get("debug") or {}).get("answer_stages")) or {}
        pres = body.get("presentation") or {}
        messages = _CAPTURE.get("messages") or []
        rows.append({
            "question": question,
            "intent": meta.get("intent"),
            "sources": meta.get("sources_used"),
            "model": _CAPTURE.get("model"),
            "context_passed": _context_markers(messages),
            "raw_llm_answer": _CAPTURE.get("raw"),
            "post_safety_answer": stages.get("post_validator_answer"),
            "final_answer": body.get("answer"),
            "final_words": _words(body.get("answer")),
            # Visible fields only: meta.debug keeps the raw model text on purpose.
            "em_dash_in_final": EM in json.dumps({k: v for k, v in body.items() if k != "meta"}, ensure_ascii=False),
            "frontend": {
                "mode": pres.get("mode"),
                "findings": [f.get("label") for f in pres.get("findings") or []],
                "raw_findings_folded": len(pres.get("raw_findings") or []),
                "uncertainties": pres.get("uncertainties") or [],
                "follow_ups": [f.get("text") for f in body.get("follow_ups") or []],
                "semantic_blocks": [b.get("type") for b in (body.get("semantic") or {}).get("blocks") or []],
            },
            "input_tokens": meta.get("input_tokens"),
            "output_tokens": meta.get("output_tokens"),
            "prompt_chars": sum(len(m.get("content") or "") for m in messages),
            "latency_ms": wall,
        })
    Path(args.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(json.dumps(rows, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
