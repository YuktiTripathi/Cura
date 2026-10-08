#!/usr/bin/env python3
"""Answer-model routing report: which tier and model each question gets, and why.

Runs data/model_routing_set.json (20 FAST / 20 STANDARD / 20 DEEP; multi-turn cases are
real conversations) through the normal chat pipeline and records, per scored turn, the
routing telemetry CURA logs in production (tier, model, complexity score, reasons,
latency, tokens, cost). Nothing here changes routing.

Offline (mock data, stand-in model; routing, distribution and pipeline overhead only):
    python scripts/model_routing_report.py --offline

Live (your .env: OPENROUTER_API_KEY, real or mock health data):
    python scripts/model_routing_report.py --user <subject_id>

Model comparison, evaluation only (the SAME questions forced through each tier with
CURA_FORCE_ANSWER_TIER semantics; answers saved for manual scoring of correctness,
personalization, reasoning depth and hallucination):
    python scripts/model_routing_report.py --user <subject_id> --compare-models --sample 12

Output: model_routing_report.json and .md (no message text from users other than the
fixed test questions; no health values).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))

SET_PATH = ROOT / "data" / "model_routing_set.json"


def _configure(args) -> None:
    from app.core.config import settings

    settings.answer_cache_enabled = False
    settings.rate_limit_requests = 100000
    settings.member_daily_token_budget = 10**9  # an evaluation run is not one member's day
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
            from app.core import perf

            perf.count("llm_calls")
            CALLS.append(self.model)
            # Estimated usage (prompt characters / 4; a typical 250-token answer) so the cost
            # arithmetic runs through the real pricing code. Real usage comes from the provider.
            chars = sum(len(m.get("content") or "") for m in messages)
            self.last_usage = {"input_tokens": chars // 4, "output_tokens": 250}
            return LLMStructuredOutput(answer="Stand-in answer.")

        OpenAICompatibleLLMClient.complete_structured = _fake
    else:
        from app.llm.openai_compatible import OpenAICompatibleLLMClient

        original = OpenAICompatibleLLMClient.complete_structured

        def _count(self, messages):
            CALLS.append(self.model)
            return original(self, messages)

        OpenAICompatibleLLMClient.complete_structured = _count


CALLS: list[str] = []


def _run_case(client, user: str, turns: list[str], records: list) -> tuple[dict | None, dict, int]:
    conversation_id = None
    body: dict = {}
    calls_before = 0
    for question in turns:
        calls_before = len(CALLS)
        payload = {"message": question, **({"conversation_id": conversation_id} if conversation_id else {})}
        started = time.perf_counter()
        body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": user}, json=payload).json()
        body["_wall_ms"] = int((time.perf_counter() - started) * 1000)
        conversation_id = body.get("conversation_id")
    return (records[-1] if records else None), body, len(CALLS) - calls_before


def _pct(values, p):
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="eval-user-companion")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--mode", choices=["plain", "rich"], default="plain")
    parser.add_argument("--compare-models", action="store_true")
    parser.add_argument("--sample", type=int, default=12)
    parser.add_argument("--out", default="model_routing_report")
    args = parser.parse_args()
    _configure(args)

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app
    from app.pipeline import service as service_module

    records: list = []
    original = service_module.model_routing_record

    def _spy(response, eval_turn):
        record = original(response, eval_turn)
        records.append(record)
        return record

    service_module.model_routing_record = _spy
    client = TestClient(app)
    cases = json.loads(SET_PATH.read_text())["cases"]

    rows = []
    for case in cases:
        records.clear()
        record, body, calls = _run_case(client, args.user, case["turns"], records)
        record = record or {"answer_tier": "deterministic", "routing_reason": []}
        rows.append({
            "question": case["turns"][-1],
            "context_turns": len(case["turns"]) - 1,
            "expected": case["tier"],
            "selected": record.get("answer_tier"),
            "model": record.get("answer_model"),
            "score": record.get("complexity_score"),
            "reasons": record.get("routing_reason"),
            "escalated": record.get("escalated"),
            "fallback_used": record.get("fallback_used"),
            "answer_model_calls": calls,
            "answer_model_ms": record.get("answer_model_ms"),
            "total_ms": record.get("total_ms") or body.get("_wall_ms"),
            "input_tokens": record.get("input_tokens"),
            "output_tokens": record.get("output_tokens"),
            "estimated_cost_usd": record.get("estimated_cost_usd"),
        })

    comparison = []
    if args.compare_models:
        sample = [c for c in cases if len(c["turns"]) == 1]
        step = max(1, len(sample) // max(1, args.sample))
        for case in sample[::step][: args.sample]:
            for forced in ("fast", "standard", "deep"):
                settings.cura_force_answer_tier = forced
                records.clear()
                record, body, calls = _run_case(client, args.user, case["turns"], records)
                comparison.append({
                    "question": case["turns"][-1], "expected": case["tier"], "forced": forced,
                    "model": (record or {}).get("answer_model"), "answer": body.get("answer"),
                    "answer_model_ms": (record or {}).get("answer_model_ms"), "total_ms": (record or {}).get("total_ms"),
                    "input_tokens": (record or {}).get("input_tokens"), "output_tokens": (record or {}).get("output_tokens"),
                    "estimated_cost_usd": (record or {}).get("estimated_cost_usd"),
                    # Fill these in by hand (1-5): correctness, personalization, reasoning depth; hallucination yes/no.
                    "scores": {"correctness": None, "personalization": None, "reasoning_depth": None, "hallucination": None},
                })
        settings.cura_force_answer_tier = ""

    by_tier = defaultdict(list)
    for r in rows:
        by_tier[r["selected"]].append(r)
    summary = {}
    for tier, group in by_tier.items():
        ms = [r["answer_model_ms"] for r in group if r["answer_model_ms"] is not None]
        tot = [r["total_ms"] for r in group if r["total_ms"] is not None]
        tin = [r["input_tokens"] for r in group if r["input_tokens"]]
        tout = [r["output_tokens"] for r in group if r["output_tokens"]]
        cost = [r["estimated_cost_usd"] for r in group if r["estimated_cost_usd"] is not None]
        summary[tier] = {
            "share": round(100 * len(group) / len(rows), 1),
            "p50_total_ms": _pct(tot, .5), "p90_total_ms": _pct(tot, .9),
            "p50_model_ms": _pct(ms, .5), "p90_model_ms": _pct(ms, .9),
            "avg_input_tokens": round(statistics.mean(tin)) if tin else None,
            "avg_output_tokens": round(statistics.mean(tout)) if tout else None,
            "avg_cost_usd": round(statistics.mean(cost), 6) if cost else None,
        }
    agreement = sum(r["expected"] == r["selected"] for r in rows)
    confusion = Counter((r["expected"], r["selected"]) for r in rows)

    out = Path(args.out)
    out.with_suffix(".json").write_text(json.dumps({"rows": rows, "summary": summary, "comparison": comparison}, indent=1))
    md = [f"# Answer-model routing ({'offline stand-in' if args.offline else 'live'}, {args.mode} mode)", "",
          f"Agreement with expected tier: {agreement}/{len(rows)}", "",
          "| expected → selected | n |", "|---|---|", *[f"| {e} → {s} | {n} |" for (e, s), n in sorted(confusion.items())], "",
          "| tier | share | P50 total | P90 total | P50 model | P90 model | in tok | out tok | cost |", "|---|---|---|---|---|---|---|---|---|",
          *[f"| {t} | {v['share']}% | {v['p50_total_ms']} | {v['p90_total_ms']} | {v['p50_model_ms']} | {v['p90_model_ms']} | "
            f"{v['avg_input_tokens']} | {v['avg_output_tokens']} | {v['avg_cost_usd']} |" for t, v in sorted(summary.items())], "",
          "| question | expected | selected | model | score | reasons | calls |", "|---|---|---|---|---|---|---|",
          *[f"| {r['question']}{' (turn ' + str(r['context_turns'] + 1) + ')' if r['context_turns'] else ''} | {r['expected']} | "
            f"{r['selected']} | {r['model']} | {r['score']} | {', '.join(r['reasons'] or [])} | {r['answer_model_calls']} |" for r in rows]]
    out.with_suffix(".md").write_text("\n".join(md))
    print("\n".join(md[:6 + len(confusion) + 4 + len(summary)]))
    print(f"wrote {out.with_suffix('.json')} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
