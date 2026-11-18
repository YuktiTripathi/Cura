"""Benchmark output and negative-control regression checks."""
from types import SimpleNamespace

from scripts.benchmark_medical_retrieval import evaluate, load_cases


class FakeProvider:
    def query(self, message, limit=3):
        if "football" in message:
            return []
        return [SimpleNamespace(name="mock", url="", topics=("hba1c",))]


def test_benchmark_cases_include_negative_control():
    cases = load_cases()
    assert len(cases) >= 10
    assert any(not case["expected_topics"] for case in cases)


def test_benchmark_reports_candidate_and_latency():
    result = evaluate(candidate=FakeProvider(), cases=[
        {"query": "What does HbA1c measure?", "expected_topics": ["hba1c"]},
        {"query": "Who won the football game yesterday?", "expected_topics": []},
    ])
    assert result["candidate"]["count"] == 2
    assert result["candidate"]["topic_hit_at_k"] == 1
    assert result["candidate"]["negative_false_positives"] == 0
    assert result["candidate"]["median_latency_ms"] >= 0
