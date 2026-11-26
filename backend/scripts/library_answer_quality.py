"""Answer quality with the upgraded Medical Knowledge Library, through the real CURA chat pipeline.

Each question is sent as a real /api/v1/chat request from a synthetic member. The report records the
member's own values the request carried, the curated knowledge block (and its size), the final answer and
the follow-ups. It asserts nothing about quality: read it.

    cd backend
    # capture: the model call is replaced at the network edge, so the request is exact and the answer is
    # CURA's own fallback. Works offline.
    PYTHONPATH=..:. python scripts/library_answer_quality.py --mode capture --out /tmp/library_quality.md
    # live: the configured model answers. Needs network access and your own credential.
    ENABLE_LLM=true OPENROUTER_API_KEY=... PYTHONPATH=..:. python scripts/library_answer_quality.py --mode live --out /tmp/library_quality_live.md
"""

from __future__ import annotations

import argparse
import pathlib
import re

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import LLMUnavailableError
from app.llm.openai_compatible import OpenAICompatibleLLMClient
from app.main import app

# (capability, member, question). Members are synthetic: demo-user-001 low vitamin D, low B12, high LDL;
# demo-user-002 normal vitamin D; eval-user-metabolic HbA1c 6.1 with high triglycerides and low HDL;
# eval-user-iron low haemoglobin, small red cells, low ferritin; eval-user-alp high ALP with normal haemoglobin.
CASES = [
    ("how the body works", "demo-user-002", "How does the liver work?"),
    ("what a biomarker measures", "demo-user-002", "What does HbA1c measure?"),
    ("personal result, encouraging", "demo-user-002", "What does my vitamin D result mean?"),
    ("personal result, abnormal", "demo-user-001", "What does my vitamin D result mean?"),
    ("personal result, abnormal", "demo-user-001", "Why is my vitamin B12 low?"),
    ("related findings", "eval-user-iron", "How are my ferritin and haemoglobin related?"),
    ("related findings", "eval-user-metabolic", "Explain my results: HbA1c, triglycerides and HDL"),
    ("maintaining good health", "demo-user-002", "How can I keep my vitamin D healthy?"),
    ("improving health", "demo-user-001", "How can I improve my LDL?"),
    ("modifiable risk", "eval-user-metabolic", "What can I do to lower my diabetes risk?"),
    ("food", "eval-user-iron", "What should I eat for my haemoglobin?"),
    ("bone or liver", "eval-user-alp", "Why is my ALP high?"),
]


def run(mode: str) -> str:
    client = TestClient(app)
    seen: list = []
    original = OpenAICompatibleLLMClient.complete_structured

    def capture(self, messages, *args, **kwargs):
        seen.append(messages)
        if mode == "capture":
            raise LLMUnavailableError("captured for evaluation")
        return original(self, messages, *args, **kwargs)

    settings.enable_llm = True if mode == "capture" else settings.enable_llm
    OpenAICompatibleLLMClient.complete_structured = capture
    OpenAICompatibleLLMClient.complete = capture
    out = [f"# Library answer quality ({mode})", ""]
    try:
        for capability, user, question in CASES:
            seen.clear()
            body = client.post("/api/v1/chat", headers={"X-Cura-User-Id": user}, json={"message": question}).json()
            request = "\n".join(m.get("content", "") for m in (seen[0] if seen else []) if isinstance(m, dict))
            knowledge = ""
            if "CURATED KNOWLEDGE (V2.3)" in request:
                knowledge = request.split("CURATED KNOWLEDGE (V2.3)", 1)[1]
                knowledge = knowledge.split("\n\n", 1)[0]
            lines = [x for x in knowledge.splitlines()[1:] if x.strip()]
            values = sorted(set(re.findall(r'"value":\s*([\d.]+)', request)))[:12]
            out += [
                f"## {capability}: {question} ({user})",
                "",
                f"- Model request assembled: {'yes' if request else 'no'}",
                f"- Member values in the request: {', '.join(values) or 'none'}",
                f"- Curated knowledge: {len(lines)} passages, about {sum(len(x) for x in lines) // 4} tokens",
                "",
                "Knowledge passages:",
                "",
                *[f"> {x[:400]}" for x in lines],
                "",
                "Final answer:",
                "",
                *[f"> {x}" for x in (body.get("answer") or "").splitlines()],
                "",
                "Follow-ups: " + "; ".join(f.get("text", "") for f in body.get("follow_ups") or []),
                "",
            ]
    finally:
        OpenAICompatibleLLMClient.complete_structured = original
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["capture", "live"], default="capture")
    parser.add_argument("--out", default="/tmp/library_quality.md")
    args = parser.parse_args()
    pathlib.Path(args.out).write_text(run(args.mode), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
