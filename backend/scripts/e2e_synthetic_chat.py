"""Run synthetic-member questions through the CURA chat endpoint. Prints scores only."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

settings.health_provider = "mock"
settings.enable_llm = True
settings.jev_enabled = False

client = TestClient(app)
H = {"X-Cura-User-Id": "demo-user-001"}

TURNS = [
    "What is HDL?",
    "What is my HDL level?",
    "What does my result mean?",
    "How is it connected to LDL?",
    "What can influence HDL?",
    "What is ferritin?",
    "What does my ferritin result mean?",
    "How is ferritin connected to haemoglobin?",
    "Explain that more simply.",
    "Can my iron stores be low even if haemoglobin is normal?",
    "What is Bio-AI?",
    "What does my cardiac health risk mean?",
    "Does this prediction mean I have heart disease?",
    "What does my cholesterol report tell me?",
    "What about my vitamin D?",
    "What is diabetes?",
    "Has my HbA1c changed?",
    "What should I eat based on my blood report?",
]


def main() -> None:
    import json
    from pathlib import Path

    print("provider", settings.health_provider, "llm", settings.enable_llm, "max_out", settings.llm_max_output_tokens)
    transcript = []
    conversation_id = None
    for index, message in enumerate(TURNS, 1):
        started = time.perf_counter()
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = client.post("/api/v1/chat", headers=H, json=payload)
        elapsed = round(time.perf_counter() - started, 2)
        if response.status_code != 200:
            print(index, "http", response.status_code, elapsed)
            continue
        body = response.json()
        conversation_id = body.get("conversation_id") or conversation_id
        answer = body.get("answer") or ""
        follow = body.get("follow_ups") or body.get("follow_up_questions") or []
        texts = []
        for item in follow:
            texts.append(item.get("text") if isinstance(item, dict) else str(item))
        meta = body.get("meta") or {}
        timing = (meta.get("timing") or {}) if isinstance(meta.get("timing"), dict) else {}
        stages = timing.get("stages") or {}
        print(
            index,
            "sec", elapsed,
            "words", len(answer.split()),
            "json_leak", answer.strip().startswith("{"),
            "follow", len(texts),
            "model", meta.get("model") or meta.get("answer_model"),
            "intent", stages.get("intent"),
            "llm", meta.get("llm_called"),
            "sources", meta.get("sources_used"),
            "stages",
            {k: stages.get(k) for k in ("safety_ms", "jev_ms", "planning_ms", "retrieval_ms", "generation", "first_token_ms", "total_ms") if k in stages or k in timing},
        )
        print("  q", message)
        print("  a", " ".join(answer.split())[:220])
        print("  f", " | ".join(texts[:4]))
        transcript.append({
            "n": index,
            "q": message,
            "a": " ".join(answer.split()),
            "follow": texts,
            "model": meta.get("answer_model"),
            "llm": meta.get("llm_called"),
            "intent": stages.get("intent"),
            "sources": meta.get("sources_used"),
            "sec": elapsed,
            "tokens_in": meta.get("input_tokens"),
            "tokens_out": meta.get("output_tokens"),
            "cached": (meta.get("usage") or {}).get("cached_tokens") if isinstance(meta.get("usage"), dict) else meta.get("cached_tokens"),
            "cost": meta.get("estimated_cost_usd"),
            "stages": {k: stages.get(k) for k in ("safety_ms", "jev_ms", "retrieval_ms", "total_ms")},
        })
    Path("/tmp/cura_phase44_18.json").write_text(json.dumps(transcript, indent=2))


if __name__ == "__main__":
    main()
