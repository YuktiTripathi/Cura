#!/usr/bin/env python3
"""CURA user-facing latency suite: 5 simple, 5 medium, 5 complex questions x N runs.

Measures only "request enters ChatService.chat -> CURA response ready" using the per-stage
trace attached to each response (meta.timing.stages). The answer cache is disabled so every
run is a cold model call; no evaluator/judge call is made or timed here.

Live (uses your .env: HEALTH_PROVIDER, SUPERSHYFT_DATABASE_URL, OPENROUTER_API_KEY):
    python scripts/latency_suite.py --user <subject_id> --runs 3

Offline pipeline overhead (mock data; optional simulated model latency):
    python scripts/latency_suite.py --offline --simulate-llm-ms 2500 --runs 3

Output: a table per complexity (P50/P75/P90/P95/max) and the stage that dominates, plus a
JSON file with every request's stage breakdown. Stage data contain numbers only (no PHI).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

SUITE = {
    "simple": [
        "What is my HbA1c?",
        "What is my Vitamin D?",
        "What is my BUN?",
        "Is my LDL normal?",
        "What is my triglyceride level?",
    ],
    "medium": [
        "Why is my HbA1c high?",
        "What does my HDL mean for me?",
        "Has my HbA1c improved?",
        "Am I active enough for my health?",
        "Why are my triglycerides high?",
    ],
    "complex": [
        "What should I work on first?",
        "Why is my metabolic risk high?",
        "My cholesterol looks okay, so why is my cardiac risk high?",
        "Anything in my reports I should pay attention to?",
        "How do my blood report and Bio-AI report fit together?",
    ],
}

STAGES = (
    "intent_ms", "retrieval_ms", "profile_fetch_ms", "blood_bioai_fetch_ms", "blood_fetch_ms", "bioai_fetch_ms",
    "lifestyle_fetch_ms", "questionnaire_fetch_ms", "scenario_fetch_ms", "context_only_ms", "knowledge_lookup_ms",
    "prompt_build_ms", "llm_ms", "safety_ms", "recommendation_ms", "composition_ms", "persistence_ms",
)


_SIM = {"calls": 0, "prompt_chars": 0}


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _configure(args) -> None:
    from app.core.config import settings

    if "answer_cache_enabled" in type(settings).model_fields:
        settings.answer_cache_enabled = False  # cold latency only
    else:  # older revisions: a zero TTL disables reuse
        settings.answer_cache_ttl_seconds = 0
    settings.rate_limit_requests = 100000
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
        set_registry(None)
        if args.simulate_llm_ms:
            settings.enable_llm = True
            settings.openrouter_api_key = settings.openrouter_api_key or "offline-simulation"
            delay = args.simulate_llm_ms / 1000

            def _fake(self, messages):
                _SIM["calls"] += 1
                _SIM["prompt_chars"] += sum(len(m.get("content") or "") for m in messages)
                try:
                    from app.core import perf

                    perf.count("llm_calls")
                    perf.count("provider_attempts")
                    with perf.stage("llm"):
                        time.sleep(delay)
                except ImportError:  # older revisions without the perf trace
                    time.sleep(delay)
                return LLMStructuredOutput(answer="Simulated answer for latency measurement.")

            OpenAICompatibleLLMClient.complete_structured = _fake
        else:
            settings.enable_llm = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-metabolic")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--simulate-llm-ms", type=int, default=0)
    parser.add_argument("--out", default="latency_suite_results.json")
    parser.add_argument("--mode", choices=["plain", "rich"], default=None, help="CURA_RESPONSE_MODE override")
    args = parser.parse_args()
    _configure(args)
    if args.mode:
        from app.core.config import settings as _settings

        _settings.cura_response_mode = args.mode

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    rows = []
    for run in range(args.runs):
        for complexity, questions in SUITE.items():
            for question in questions:
                _SIM.update(calls=0, prompt_chars=0)
                started = time.perf_counter()
                body = client.post(
                    "/api/v1/chat", headers={"X-Cura-User-Id": args.user}, json={"message": question}
                ).json()
                wall = int((time.perf_counter() - started) * 1000)
                stages = ((body.get("meta") or {}).get("timing") or {}).get("stages") or {}
                rows.append({"run": run, "complexity": complexity, "question_index": questions.index(question),
                             "wall_ms": wall, "sim_llm_calls": _SIM["calls"], "sim_prompt_chars": _SIM["prompt_chars"], **{k: v for k, v in stages.items() if not isinstance(v, (dict, list))}})
    Path(args.out).write_text(json.dumps(rows, indent=1))

    print(f"user-facing latency (ms), {args.runs} runs, answer cache off, no judge")
    print(f"{'complexity':10} {'n':>3} {'P50':>7} {'P75':>7} {'P90':>7} {'P95':>7} {'max':>7}  dominant stage (mean ms)")
    for complexity in SUITE:
        group = [r for r in rows if r["complexity"] == complexity]
        totals = [float(r.get("total_ms") or r["wall_ms"]) for r in group]
        means = {s: statistics.mean(float(r.get(s) or 0) for r in group) for s in STAGES}
        top = sorted(means.items(), key=lambda kv: kv[1], reverse=True)[:3]
        print(
            f"{complexity:10} {len(group):>3} {_pct(totals, .5):>7.0f} {_pct(totals, .75):>7.0f} {_pct(totals, .9):>7.0f} "
            f"{_pct(totals, .95):>7.0f} {max(totals):>7.0f}  " + ", ".join(f"{k[:-3]} {v:.0f}" for k, v in top)
        )
    llm_calls = sum(int(r.get("llm_calls") or 0) for r in rows)
    retries = sum(int(r.get("retry_count") or 0) for r in rows)
    tokens = [int(r.get("prompt_tokens") or 0) for r in rows if r.get("prompt_tokens")]
    chars = [int(r.get("prompt_chars") or r.get("sim_prompt_chars") or 0) for r in rows if r.get("prompt_chars") or r.get("sim_prompt_chars")]
    if not llm_calls:
        llm_calls = sum(int(r.get("sim_llm_calls") or 0) for r in rows)
    jev = sum(1 for r in rows if r.get("jev_called"))
    print(f"requests={len(rows)} llm_calls={llm_calls} retries={retries} jev_calls={jev} "
          f"mean_prompt_tokens={statistics.mean(tokens) if tokens else 'n/a'} "
          f"mean_prompt_chars={statistics.mean(chars) if chars else 'n/a'}")
    print(f"details: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
