from __future__ import annotations

from app.db.models import DocumentChunk
from app.documents.value_extraction import find_report_date


def latest_uploaded_by_test_date(db, user_id: str, docs) -> str | None:
    """Return document_id of the newest report if every doc has an extractable test/report date."""
    dated: list[tuple] = []
    for doc in docs:
        did = getattr(doc, "document_id", None) or getattr(doc, "id", None)
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == did, DocumentChunk.user_id == user_id)
            .all()
        )
        dates = [find_report_date(c.text) for c in chunks]
        dates = [d for d in dates if d is not None]
        if not dates:
            return None
        dated.append((max(dates), did))
    if len(dated) != len(list(docs)):
        return None
    return max(dated, key=lambda item: item[0])[1]
