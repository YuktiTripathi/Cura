"""Compare a fresh PDF extraction with stored facts. Never writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Document
from app.documents.extraction import extract_pdf_pages
from app.documents.facts import extract_facts_from_pages, facts_from_extracted
from app.documents.normalization import normalize_extracted_text
from app.documents.service import DocumentService
from app.documents.storage import get_document_store
from app.documents.structured import load_structured


def _sig(fact) -> tuple:
    return (
        fact.canonical_code,
        getattr(fact, "measurement_kind", "measured"),
        fact.value,
        fact.unit,
        fact.page_number,
    )


def preview_reprocess(db: Session, user_id: str, document_id: str) -> dict:
    """Re-read the original file and report fact changes. Leaves the row untouched."""
    row = DocumentService(db).get_owned(user_id, document_id)
    stored = load_structured(row)
    stored_facts = facts_from_extracted(stored) if stored else []
    pages = extract_pdf_pages(get_document_store().read(row.storage_key))
    for page in pages:
        page.text = normalize_extracted_text(page.text)
    fresh = facts_from_extracted(extract_facts_from_pages(row.id, pages))
    old = {_sig(item) for item in stored_facts}
    new = {_sig(item) for item in fresh}
    return {
        "document_id": row.id,
        "stored": len(stored_facts),
        "fresh": len(fresh),
        "removed": len(old - new),
        "added": len(new - old),
        "applied": False,
    }
