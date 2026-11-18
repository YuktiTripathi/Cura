"""Deterministic tests for the optional semantic reranker."""
from types import SimpleNamespace

from app.retrieval.semantic_candidate import SemanticMedicalCandidate, _cosine


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[0.0, 1.0], [1.0, 0.0]]

    def embed_query(self, text):
        return [1.0, 0.0]


class Baseline:
    def query(self, message, topic=None, limit=5):
        return [
            SimpleNamespace(name="first", title="", topics=("ldl",), keywords=(), excerpt="first"),
            SimpleNamespace(name="second", title="", topics=("ldl",), keywords=(), excerpt="second"),
        ]


def test_semantic_reranks_only_baseline_candidates():
    candidate = SemanticMedicalCandidate(FakeEmbeddings(), Baseline())
    result = candidate.query("What is LDL?", limit=2)
    assert [doc.name for doc in result] == ["second", "first"]


def test_cosine_handles_zero_and_mismatched_vectors():
    assert _cosine([0, 0], [1, 0]) == 0
    assert _cosine([1], [1, 0]) == 0
