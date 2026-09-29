from __future__ import annotations

import math
import re
from dataclasses import dataclass

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
        if document_ids is not None:
            for did in document_ids:
                row = (
                    self.db.query(Document)
                    .filter(Document.id == did, Document.user_id == user_id, Document.upload_status != "deleted")
                    .one_or_none()
                )
                if row is None:
                    raise NotFoundError("Document not found.")
        q = self.db.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        q = q.filter(DocumentChunk.user_id == user_id, Document.user_id == user_id)
        if document_ids is not None:
            q = q.filter(DocumentChunk.document_id.in_(document_ids))
        rows = q.all()
        scored: list[DocumentEvidence] = []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        params = normalize_lab_query(query)
        primary = primary_lab_key(query)
        df: dict[str, int] = {}
        texts = []
        for chunk, doc in rows:
            toks = set(_tokenize(chunk.text))
            texts.append((chunk, doc, toks, _tokenize(chunk.text)))
            for t in toks:
                df[t] = df.get(t, 0) + 1
        n_docs = max(len(texts), 1)
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
