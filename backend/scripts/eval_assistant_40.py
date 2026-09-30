#!/usr/bin/env python3
"""Offline 40-question assistant evaluation. Does not send real patient data.

Uses mock health data and header identity so synthetic eval users are isolated
from SuperShyft. Live model comparison (gpt-5-mini vs gemini-3.8-flash vs
claude-sonnet-4.6) is opt-in: CURA_LIVE_MODEL_EVAL=1 with OPENROUTER_API_KEY
and an eligible ZDR endpoint. data_collection=deny is not proof of ZDR.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT))


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
    settings.enable_llm = False
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

    def _complete(self, messages, json_mode=False):
        user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        return (
            "This is general medical education, not a personal lab result. "
            "HbA1c LDL HDL TSH Vitamin D B12 CRP insulin resistance metabolic age. "
            + user[:240]
        )

    OpenAICompatibleLLMClient.complete = _complete
    OpenAICompatibleLLMClient._real_complete = OpenAICompatibleLLMClient.complete


_configure_offline()

from fastapi.testclient import TestClient

from app.main import app

FIXTURE = ROOT / "tests" / "fixtures" / "cura_assistant_eval_40.jsonl"


def main() -> int:
    client = TestClient(app)
    cases = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    conversations: dict[str, str] = {}
    by_cap: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})
    failed: list[str] = []
    for case in cases:
        headers = {"X-Cura-User-Id": case["user"]}
        payload = {"message": case["message"]}
        parent = case.get("follow_up_of")
        if parent and parent in conversations:
            payload["conversation_id"] = conversations[parent]
        response = client.post("/api/v1/chat", headers=headers, json=payload)
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        conversations[case["id"]] = body.get("conversation_id") or ""
        ok = _ok(case, body, response.status_code)
        by_cap[case["capability"]]["pass" if ok else "fail"] += 1
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed.append(case["id"])
        print(f"{mark} {case['id']} [{case['capability']}] {(body.get('answer') or '')[:140]}")
    print("\nBy capability:")
    passed = 0
    total = 0
    for cap, counts in sorted(by_cap.items()):
        bucket = counts["pass"] + counts["fail"]
        passed += counts["pass"]
        total += bucket
        print(f"  {cap}: {counts['pass']}/{bucket}")
    print(f"\nOverall: {passed}/{total}")
    if failed:
        print("Failed ids: " + ", ".join(failed))
    if os.environ.get("CURA_LIVE_MODEL_EVAL") == "1":
        print(
            "Live model comparison not executed here. Confirm model IDs, endpoint "
            "JSON Schema support, ZDR eligibility, and budget before sending "
            "de-identified eval cases. data_collection=deny is not proof of ZDR."
        )
    else:
        print("Live model comparison not run (set CURA_LIVE_MODEL_EVAL=1 to enable).")
    return 0 if passed >= 32 else 1


def _ok(case, body, status_code: int) -> bool:
    if status_code >= 400:
        return False
    answer = body.get("answer") or ""
    low = answer.lower()
    if case.get("expected_status") and (body.get("meta") or {}).get("status") != case["expected_status"]:
        return False
    if case.get("expected_personal") is False:
        if (body.get("meta") or {}).get("supershyft_called") is True and case["capability"] == "explain":
            return False
    for phrase in case.get("must_include") or []:
        if phrase.lower() not in low and phrase not in answer:
            return False
    if case.get("must_include_any") and not any(p.lower() in low or p in answer for p in case["must_include_any"]):
        return False
    for phrase in case.get("forbidden") or []:
        if phrase.lower() in low:
            return False
    if "I had trouble formatting that answer" in answer:
        return False
    meta = body.get("meta") or {}
    if case.get("expected_llm_called") is False and meta.get("llm_called") is True:
        return False
    if case.get("expect_sources") and meta.get("supershyft_called") is False:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
