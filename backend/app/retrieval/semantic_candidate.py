"""Experimental semantic reranker for CURA's *approved* medical evidence.

Offline/opt-in only: never bypass active_corpus(), provenance gating, or the
existing lexical/ontology retrieval. Embeddings must be supplied by the caller;
this module does not create a network client or send patient data anywhere.
"""
from __future__ import annotations

import math
from typing import Protocol

from app.retrieval.hybrid import HybridMedicalKnowledgeProvider
from app.retrieval.medical import MedicalEvidenceDoc


class TextEmbeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    denom = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
    if not denom:
        return 0.0
    return max(0.0, min(1.0, sum(x*y for x, y in zip(a, b)) / denom))


class SemanticMedicalCandidate:
    """Rerank approved baseline candidates, never introduce unapproved evidence.

    This intentionally limits semantic recall until a larger, governed corpus
    and medical relevance evaluation justify expanding candidate generation.
    """

    def __init__(self, embeddings: TextEmbeddings, baseline: HybridMedicalKnowledgeProvider | None = None):
        self.embeddings = embeddings
        self.baseline = baseline or HybridMedicalKnowledgeProvider()

    def query(self, message: str, topic: str | None = None, limit: int = 3) -> list[MedicalEvidenceDoc]:
        # Baseline applies active corpus, Bio-AI provenance, topic and relevance gates.
        candidates = self.baseline.query(message, topic=topic, limit=5)
        if len(candidates) < 2:
            return candidates[:limit]
        texts = [
            " ".join((doc.title, " ".join(doc.topics), " ".join(doc.keywords), doc.excerpt))
            for doc in candidates
        ]
        vectors = self.embeddings.embed_documents(texts)
        query_vector = self.embeddings.embed_query(message)
        if len(vectors) != len(candidates):
            return candidates[:limit]
        scored = sorted(
            enumerate(candidates),
            key=lambda item: (-_cosine(query_vector, vectors[item[0]]), item[0]),
        )
        return [doc for _, doc in scored[:limit]]
