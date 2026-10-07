"""Hybrid medical knowledge retrieval (readiness plan 4.5).

Implements ``MedicalKnowledgeProvider``, so the pipeline does not change:

1. Normalize the question to English (Indic spellings of biomarkers, abbreviations).
2. Ontology: map biomarkers and conditions in the question to corpus topics.
3. Rank passages with BM25 over title, keywords and text, boosted by ontology matches,
   plus an optional embedding score when an ``EmbeddingScorer`` is configured.
4. Keep only passages above a score threshold, so weak matches trigger the
   "no evidence" policy instead of loosely related text.
5. Serve only reviewed, in-date passages outside development (``active_corpus``).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from app.pipeline.indic_terms import english_names_for_localized_terms, latinize_spelled_abbreviations
from app.pipeline.lab_parameters import match_lab_keys
from app.retrieval.medical import MedicalEvidenceDoc, active_corpus

# Condition and lay-term ontology -> corpus topics. Biomarkers come from match_lab_keys.
ONTOLOGY: dict[str, tuple[str, ...]] = {
    "glucose": ("type_2_diabetes", "hba1c"),
    "hba1c": ("hba1c", "type_2_diabetes"),
    "ldl": ("ldl", "cholesterol"),
    "hdl": ("hdl", "cholesterol"),
    "total_cholesterol": ("cholesterol",),
    "triglycerides": ("cholesterol",),
    "tsh": ("tsh", "thyroid"),
    "t3": ("thyroid",),
    "t4": ("thyroid",),
    "creatinine": ("creatinine", "kidney_function"),
    "egfr": ("egfr", "kidney_function"),
    "vitamin_d": ("vitamin_d",),
}
_LAY_TERMS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = tuple(
    (re.compile(pattern, re.I), topics)
    for pattern, topics in (
        (r"\b(diabet\w*|sugar|prediabet\w*|insulin resistance)\b", ("type_2_diabetes", "hba1c")),
        (r"\b(blood pressure|bp|hypertension|high bp)\b", ("hypertension",)),
        (r"\b(cholesterol|lipid\w*)\b", ("cholesterol", "ldl")),
        (r"\b(thyroid|hypothyroid\w*|hyperthyroid\w*)\b", ("thyroid", "tsh")),
        (r"\b(kidney|renal)\b", ("kidney_function",)),
        (r"\b(sunlight|vitamin d|vit d)\b", ("vitamin_d",)),
    )
)
_TOKEN = re.compile(r"[a-z0-9]+")
# Question words are stopwords too: "who won..." must not match the WHO passages.
_STOP = frozenset(
    "a an the is are was were of to in on at for and or my me i you your what does do did how why can "
    "could should would with it this that be who whom whose when where which there their them about "
    "yesterday today tomorrow".split()
)

MIN_SCORE = 2.0
DEFAULT_LIMIT = 3
MAX_LIMIT = 5


class EmbeddingScorer(Protocol):
    """Optional semantic scorer, e.g. backed by an embedding index. Returns 0..1 per doc."""

    def scores(self, query: str, docs: list[MedicalEvidenceDoc]) -> list[float]: ...


def normalize_query(message: str) -> str:
    text = latinize_spelled_abbreviations(message or "")
    return english_names_for_localized_terms(text).lower()


def ontology_topics(normalized: str, topic: str | None = None) -> set[str]:
    topics: set[str] = set()
    if topic:
        topics.add(topic.lower().replace(" ", "_"))
    for key in match_lab_keys(normalized):
        topics.update(ONTOLOGY.get(key, (key,)))
    for pattern, mapped in _LAY_TERMS:
        if pattern.search(normalized):
            topics.update(mapped)
    return topics


def _tokens(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall((text or "").lower()) if tok not in _STOP]


def _doc_tokens(doc: MedicalEvidenceDoc) -> list[str]:
    # Title and keywords count double: they describe what the passage is about.
    head = " ".join([doc.title or "", " ".join(doc.keywords), " ".join(doc.topics).replace("_", " ")])
    return _tokens(head) * 2 + _tokens(doc.excerpt)


def bm25_scores(query_tokens: list[str], docs: list[MedicalEvidenceDoc], k1: float = 1.4, b: float = 0.75) -> list[float]:
    corpus = [_doc_tokens(doc) for doc in docs]
    if not corpus:
        return []
    avg_len = sum(len(d) for d in corpus) / len(corpus) or 1.0
    df = Counter(tok for d in corpus for tok in set(d))
    n = len(corpus)
    scores = []
    for tokens in corpus:
        tf = Counter(tokens)
        score = 0.0
        for q in set(query_tokens):
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            score += idf * (tf[q] * (k1 + 1)) / (tf[q] + k1 * (1 - b + b * len(tokens) / avg_len))
        scores.append(score)
    return scores


class HybridMedicalKnowledgeProvider:
    """Ontology + BM25 (+ optional embeddings) over reviewed passages."""

    def __init__(self, embedder: EmbeddingScorer | None = None, min_score: float = MIN_SCORE):
        self.embedder = embedder
        self.min_score = min_score

    def query(self, message: str, topic: str | None = None, limit: int = DEFAULT_LIMIT) -> list[MedicalEvidenceDoc]:
        docs = list(active_corpus())
        if not docs:
            return []
        normalized = normalize_query(message)
        topics = ontology_topics(normalized, topic)
        lexical = bm25_scores(_tokens(normalized), docs)
        semantic = self.embedder.scores(normalized, docs) if self.embedder else [0.0] * len(docs)
        ranked: list[tuple[float, int, int, MedicalEvidenceDoc]] = []
        for index, doc in enumerate(docs):
            ontology = 3.0 * len(topics & set(doc.topics))
            score = lexical[index] + ontology + 4.0 * semantic[index]
            if score >= self.min_score:
                ranked.append((score, -doc.tier, -index, doc))
        ranked.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
        picked: list[MedicalEvidenceDoc] = []
        seen: set[tuple[str, str]] = set()
        for _, _, _, doc in ranked:
            key = (doc.name, doc.url)
            if key in seen:
                continue
            seen.add(key)
            picked.append(doc)
            if len(picked) >= max(1, min(limit, MAX_LIMIT)):
                break
        return picked
