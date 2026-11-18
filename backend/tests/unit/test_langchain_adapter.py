"""Phase 3: retrieval adapter remains opt-in and preserves the baseline."""
from types import SimpleNamespace

from app.retrieval.langchain_adapter import compare_retrieval


class Baseline:
    def query(self, query, limit=3):
        return [SimpleNamespace(name="LDL"), SimpleNamespace(name="Cholesterol")]


class Candidate:
    def invoke(self, query):
        return [
            SimpleNamespace(metadata={"name": "LDL"}),
            SimpleNamespace(metadata={"name": "Other"}),
        ]


def test_retrieval_comparison_reports_overlap():
    result = compare_retrieval("What is LDL?", Candidate(), baseline=Baseline())
    assert result.baseline_names == ("LDL", "Cholesterol")
    assert result.candidate_names == ("LDL", "Other")
    assert result.overlap_at_k == 0.5


def test_comparison_does_not_call_patient_providers():
    result = compare_retrieval("Explain thyroid", Candidate(), baseline=Baseline())
    assert len(result.candidate_names) == 2
