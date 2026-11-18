"""Optional LangChain-compatible adapter for CURA medical evidence.

This adapter is deliberately outside the live pipeline. The existing reviewed
corpus, ontology and minimum-score rules remain authoritative. No user reports
or personal identifiers are sent to an embedding service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.retrieval.hybrid import HybridMedicalKnowledgeProvider


@dataclass(frozen=True)
class RetrievalComparison:
    baseline_names: tuple[str, ...]
    candidate_names: tuple[str, ...]
    overlap_at_k: float


def as_langchain_documents(evidence: list[Any]) -> list[Any]:
    """Convert already-approved medical evidence to LangChain Documents.

    Import lazily so the existing production runtime does not require LangChain.
    Never pass unreviewed documents through this adapter.
    """
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError(
            "Install langchain-core in an evaluation environment to use this adapter"
        ) from exc

    return [
        Document(
            page_content=doc.excerpt,
            metadata={
                "name": doc.name,
                "title": doc.title,
                "url": doc.url,
                "topics": list(doc.topics),
                "provenance": doc.provenance,
            },
        )
        for doc in evidence
    ]


class MedicalKnowledgeLangChainAdapter:
    """Read-only, non-LLM bridge to the existing safety-filtered provider."""

    def __init__(self, provider: HybridMedicalKnowledgeProvider | None = None):
        self.provider = provider or HybridMedicalKnowledgeProvider()

    def invoke(self, query: str, *, topic: str | None = None, limit: int = 3) -> list[Any]:
        evidence = self.provider.query(query, topic=topic, limit=limit)
        return as_langchain_documents(evidence)


def compare_retrieval(
    query: str,
    candidate: Any,
    *,
    baseline: HybridMedicalKnowledgeProvider | None = None,
    limit: int = 3,
) -> RetrievalComparison:
    """Compare names, not medical content or patient data."""
    provider = baseline or HybridMedicalKnowledgeProvider()
    expected = tuple(doc.name for doc in provider.query(query, limit=limit))
    actual_docs = candidate.invoke(query)
    actual = tuple(str(doc.metadata.get("name", "")) for doc in actual_docs[:limit])
    overlap = len(set(expected) & set(actual)) / max(len(expected), 1)
    return RetrievalComparison(expected, actual, overlap)
