"""Offline retrieval benchmark; no patient data, network calls or model API required.

Run from backend/: python -m scripts.benchmark_medical_retrieval
Optional semantic candidate: pass an embeddings implementation in Python and
call evaluate(candidate=SemanticMedicalCandidate(...)).
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from app.retrieval.hybrid import HybridMedicalKnowledgeProvider


def load_cases():
    path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "medical_retrieval_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(candidate=None, cases=None, limit=3):
    baseline = HybridMedicalKnowledgeProvider()
    cases = cases if cases is not None else load_cases()
    providers = {"baseline": baseline}
    if candidate is not None:
        providers["candidate"] = candidate
    results = {}
    for label, provider in providers.items():
        rows = []
        for case in cases:
            start = time.perf_counter()
            docs = provider.query(case["query"], limit=limit)
            elapsed_ms = (time.perf_counter() - start) * 1000
            expected = set(case["expected_topics"])
            topics = set().union(*(set(doc.topics) for doc in docs)) if docs else set()
            # A relevant topic among the retrieved passages is a weak proxy,
            # NOT a clinically validated relevance judgment.
            hit = bool(topics & expected) if expected else not docs
            rows.append({
                "query": case["query"],
                "expected_topics": sorted(expected),
                "returned": len(docs),
                "hit_at_k": hit,
                "false_positive_on_negative": not expected and bool(docs),
                "latency_ms": round(elapsed_ms, 3),
                "evidence": [{"name": d.name, "url": d.url, "topics": list(d.topics)} for d in docs],
            })
        results[label] = {
            "count": len(rows),
            "topic_hit_at_k": round(sum(r["hit_at_k"] for r in rows) / max(len(rows), 1), 4),
            "negative_false_positives": sum(r["false_positive_on_negative"] for r in rows),
            "median_latency_ms": round(statistics.median(r["latency_ms"] for r in rows), 3) if rows else None,
            "rows": rows,
        }
    return results


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=False))
