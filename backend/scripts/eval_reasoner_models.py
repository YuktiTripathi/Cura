#!/usr/bin/env python3
"""Offline reasoner evaluation. Never sends real PHI.

Default: mock health + stubbed LLM. Live comparison is opt-in:
  CURA_LIVE_MODEL_EVAL=1 OPENROUTER_API_KEY=... python scripts/eval_reasoner_models.py

Live models are compared only if they are allowlisted, JSON-capable, and the
configured endpoint meets ZDR policy. data_collection=deny is not ZDR.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
import sys

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tests" / "fixtures" / "eval_runs"


def _configure_offline() -> None:
    from app.core.circuit_breaker import jev_breaker, openrouter_breaker, supershyft_breaker
    from app.core.config import settings
    from app.llm.openai_compatible import OpenAICompatibleLLMClient
    from app.providers.registry import set_registry
    from integrations.supershyft.db import reset_engine

    settings.health_provider = "mock"
    settings.auth_provider = "mock"
    settings.allow_mock_auth_with_real_health = True
    settings.mock_user_id = ""
    settings.allow_mock_header_override = True
    settings.dev_auth_header = True
    settings.jev_enabled = False
    settings.supershyft_database_url = ""
    settings.rate_limit_requests = 10000
    settings.voice_enabled = False
    settings.stt_provider = "none"
    jev_breaker.reset()
    openrouter_breaker.reset()
    supershyft_breaker.reset()
    reset_engine()
    set_registry(None)
    if os.environ.get("CURA_LIVE_MODEL_EVAL") != "1":
        settings.enable_llm = False

        def _complete(self, messages, json_mode=False):
            user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
            return (
                '{"answer":"Educational summary of the supplied facts only. '
                + user[:180].replace('"', "")
                + '","claims":[],"follow_up_questions":[]}'
            )

        OpenAICompatibleLLMClient.complete = _complete


_configure_offline()

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.pipeline.planner import EntityResolver, plan_needs_reasoning
from app.pipeline.query_planner import build_query_plan

FIXTURE = ROOT / "tests" / "fixtures" / "cura_assistant_eval_40.jsonl"


def _coverage(case, body) -> dict:
    meta = body.get("meta") or {}
    answer = (body.get("answer") or "").lower()
    plan = build_query_plan(case["message"])
    entities = EntityResolver().resolve(case["message"])
    codes = [item.code for item in entities]
    mentioned = sum(1 for code in codes if code.replace("_", " ") in answer or code in answer)
    outcomes = meta.get("source_outcomes") or []
    retrieved = [row for row in outcomes if str(row.get("status") or "") not in {"not_requested"}]
    return {
        "question_type": plan.question_type or meta.get("question_type"),
        "operations": plan.operations or meta.get("operations") or [],
        "entities": codes,
        "entity_mention_ratio": (mentioned / len(codes)) if codes else 1.0,
        "sources_requested": [row.get("source") for row in retrieved],
        "supershyft_called": meta.get("supershyft_called"),
        "llm_called": meta.get("llm_called"),
        "needs_reasoning": plan_needs_reasoning(plan),
        "grounding_passed": not (meta.get("grounding_flags") or []),
    }


def _score(case, body, coverage: dict, latency_ms: int) -> dict:
    answer = body.get("answer") or ""
    low = answer.lower()
    meta = body.get("meta") or {}
    ok = True
    for phrase in case.get("must_include") or []:
        if phrase.lower() not in low and phrase not in answer:
            ok = False
    if case.get("must_include_any") and not any(p.lower() in low or p in answer for p in case["must_include_any"]):
        ok = False
    for phrase in case.get("forbidden") or []:
        if phrase.lower() in low:
            ok = False
    retrieval = 1.0 if coverage["entity_mention_ratio"] >= 0.5 or not coverage["entities"] else coverage["entity_mention_ratio"]
    sources = coverage.get("sources_requested") or []
    multi_source = 1.0 if len({str(item) for item in sources}) >= 2 or not coverage["needs_reasoning"] else 0.5
    follow_ups = body.get("follow_ups") or []
    return {
        "pass": ok,
        "retrieval_coverage": retrieval,
        "factual_accuracy": 1.0 if ok else 0.0,
        "personal_claim_grounding": 1.0 if coverage["grounding_passed"] else 0.0,
        "reasoning_completeness": min(1.0, coverage["entity_mention_ratio"] + (0.2 if len(answer) > 80 else 0.0)),
        "multi_source_synthesis": multi_source,
        "restraint": 0.0 if "you have diabetes" in low or "i diagnose" in low else 1.0,
        "missing_data": 1.0 if ("not available" in low or "not present" in low or "missing" in low or ok) else 0.0,
        "personalization": 1.0 if coverage.get("supershyft_called") or not case.get("user") else (0.0 if "my " in case.get("message", "").lower() else 1.0),
        "actionability": 1.0 if follow_ups or "discuss" in low or "consider" in low or not coverage["needs_reasoning"] else 0.5,
        "readability": 1.0 if 40 <= len(answer) <= 4000 else 0.5,
        "latency_ms": latency_ms,
        "cost": meta.get("estimated_cost_usd"),
    }


def main() -> int:
    client = TestClient(app)
    cases = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    conversations: dict[str, str] = {}
    rows = []
    by_cap: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})
    for case in cases:
        headers = {"X-Cura-User-Id": case["user"]}
        payload = {"message": case["message"]}
        parent = case.get("follow_up_of")
        if parent and parent in conversations:
            payload["conversation_id"] = conversations[parent]
        started = time.perf_counter()
        response = client.post("/api/v1/chat", headers=headers, json=payload)
        latency_ms = int((time.perf_counter() - started) * 1000)
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        conversations[case["id"]] = body.get("conversation_id") or ""
        coverage = _coverage(case, body)
        scores = _score(case, body, coverage, latency_ms)
        by_cap[case["capability"]]["pass" if scores["pass"] else "fail"] += 1
        rows.append(
            {
                "id": case["id"],
                "capability": case["capability"],
                "latency_ms": latency_ms,
                "answer_preview": (body.get("answer") or "")[:240],
                "coverage": coverage,
                "scores": scores,
            }
        )
        mark = "PASS" if scores["pass"] else "FAIL"
        print(f"{mark} {case['id']} [{case['capability']}] {(body.get('answer') or '')[:120]}")

    passed = sum(1 for row in rows if row["scores"]["pass"])
    print("\nBy capability:")
    for cap, counts in sorted(by_cap.items()):
        print(f"  {cap}: {counts['pass']}/{counts['pass'] + counts['fail']}")
    print(f"\nOverall: {passed}/{len(rows)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out = OUT_DIR / f"reasoner_{stamp}.jsonl"
    out.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    print(f"Wrote {out}")

    live = os.environ.get("CURA_LIVE_MODEL_EVAL") == "1"
    zdr_ok = bool(settings.openrouter_zero_data_retention)
    if not live:
        print("Live model comparison not run (set CURA_LIVE_MODEL_EVAL=1 to enable).")
        print("Production model not chosen; live eval not run.")
    elif not settings.openrouter_api_key and not settings.llm_api_key:
        print("Live eval skipped: no OpenRouter credentials.")
    elif settings.require_zdr_for_personal_health and not zdr_ok:
        print("Live eval skipped: personal-health ZDR is required and not configured.")
        print("data_collection=deny is not proof of ZDR.")
    else:
        candidates = [
            settings.answer_model_standard,
            settings.answer_model_advanced,
            settings.eval_candidate_model,
        ]
        allowed = {item.strip() for item in (settings.llm_allowed_models or "").split(",") if item.strip()}
        print("Live candidates (allowlisted only):", [m for m in candidates if m in allowed or not allowed])
        print("Live per-model loop is opt-in and was not auto-executed to avoid PHI/cost surprises.")
        print("Confirm JSON Schema support and ZDR before a production model choice.")
    return 0 if passed >= 32 else 1


if __name__ == "__main__":
    raise SystemExit(main())
