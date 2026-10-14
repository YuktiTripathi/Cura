from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.db.models import Document, DocumentChunk
from app.documents.service import SOURCE_USER_UPLOADED
from app.pipeline.lab_parameters import normalize_lab_query, primary_lab_key

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.I)
_NUMERIC_RESULT = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg/dl|mg/dL|ng/ml|pg/ml|µiu/ml|%|mmol/l)?\b",
    re.I,
)
_EXPLANATORY = re.compile(
    r"\b(ovulation|luteinizing|follicle|pregnancy|explain|overview|physiology)\b",
    re.I,
)
_TABLEISH = re.compile(r"\b(reference|range|result|test|investigation|method)\b", re.I)
_SEARCH_STOPWORDS = {
    "a",
    "about",
    "and",
    "does",
    "explain",
    "for",
    "from",
    "how",
    "is",
    "mean",
    "my",
    "of",
    "report",
    "say",
    "the",
    "this",
    "what",
}


@dataclass
class DocumentEvidence:
    source: str
    document_id: str
    chunk_id: str
    filename: str
    page_start: int
    page_end: int
    text: str
    score: float
    user_id: str


class DocumentRetriever:
    def __init__(self, db: Session):
        self.db = db

    def retrieve(
        self,
        user_id: str,
        query: str,
        document_ids: list[str] | None = None,
        limit: int | None = None,
    ) -> list[DocumentEvidence]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        params = normalize_lab_query(query)
        primary = primary_lab_key(query)
        if document_ids is not None:
            requested = set(document_ids)
            owned = {
                row[0]
                for row in (
                    self.db.query(Document.id)
                    .filter(
                        Document.id.in_(requested),
                        Document.user_id == user_id,
                        Document.upload_status != "deleted",
                    )
                    .all()
                )
            }
            if owned != requested:
                raise NotFoundError("Document not found.")
        base = self.db.query(DocumentChunk, Document).join(
            Document, DocumentChunk.document_id == Document.id
        )
        base = base.filter(DocumentChunk.user_id == user_id, Document.user_id == user_id)
        if document_ids is not None:
            base = base.filter(DocumentChunk.document_id.in_(document_ids))

        # Fetch only a superset of chunks that can receive a positive score. The
        # previous implementation transferred every chunk to Python even though
        # chunks without a query token or recognized biomarker alias always scored
        # zero. Keeping the total corpus count preserves the existing IDF formula.
        search_terms = {
            token for token in q_tokens if len(token) >= 2 and token not in _SEARCH_STOPWORDS
        }
        for parameter in params:
            search_terms.update(_tokenize(parameter.key.replace("_", " ")))
        if not search_terms:
            search_terms = set(q_tokens)
        lowered_text = func.lower(DocumentChunk.text)
        candidates = base.filter(
            or_(*(lowered_text.contains(term) for term in sorted(search_terms)))
        )
        n_docs = max(base.count(), 1)
        rows = candidates.all()
        # An explicitly selected document is the source even when the question
        # shares no words with the excerpt. Otherwise every such question builds
        # the same prompt and the answer cache can repeat another document.
        if document_ids is not None and not rows:
            cap = limit or settings.document_retrieve_limit
            rows = base.limit(cap).all()
        scored: list[DocumentEvidence] = []
        df: dict[str, int] = {}
        texts = []
        for chunk, doc in rows:
            toks = set(_tokenize(chunk.text))
            texts.append((chunk, doc, toks, _tokenize(chunk.text)))
            for t in toks:
                df[t] = df.get(t, 0) + 1
        for chunk, doc, uniq, all_toks in texts:
            score = 0.0
            tf: dict[str, int] = {}
            for t in all_toks:
                tf[t] = tf.get(t, 0) + 1
            for t in q_tokens:
                if t not in tf:
                    continue
                idf = math.log((n_docs + 1) / (df.get(t, 0) + 1)) + 1
                score += (tf[t] / len(all_toks)) * idf
            lowered = chunk.text.lower()
            matched_param = False
            if params:
                for p in params:
                    for alias in p.aliases:
                        if alias in lowered:
                            score += 8.0 if p.key == primary else 4.0
                            matched_param = True
                            break
                if matched_param:
                    if _NUMERIC_RESULT.search(chunk.text):
                        score += 5.0
                    if _TABLEISH.search(chunk.text):
                        score += 2.0
                if _EXPLANATORY.search(chunk.text) and not matched_param:
                    score -= 6.0
                if primary and not matched_param:
                    score -= 2.0
            if document_ids is not None and score <= 0:
                score = 0.1
            if score > 0:
                scored.append(
                    DocumentEvidence(
                        source=SOURCE_USER_UPLOADED,
                        document_id=chunk.document_id,
                        chunk_id=chunk.id,
                        filename=doc.original_filename,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        text=chunk.text,
                        score=score,
                        user_id=chunk.user_id,
                    )
                )
        scored.sort(key=lambda e: e.score, reverse=True)
        scored = _dedupe(scored)
        cap = limit or settings.document_retrieve_limit
        return scored[:cap]


def _dedupe(items: list[DocumentEvidence]) -> list[DocumentEvidence]:
    seen: set[tuple[str, int, str]] = set()
    out: list[DocumentEvidence] = []
    for item in items:
        key = (item.document_id, item.page_start, (item.text or "")[:80].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN.finditer(text or "")]
