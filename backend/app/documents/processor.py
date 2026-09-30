from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundError
from app.contracts.uploaded_document import PageIndexStatus, ProcessingStatus
from app.db.models import Document, DocumentChunk
from app.documents.chunking import chunk_pages
from app.documents.extraction import ExtractedPage, extract_pdf_pages
from app.documents.facts import extract_facts_from_pages
from app.documents.metadata import update_meta
from app.documents.normalization import normalize_extracted_text
from app.documents.ocr import OCRProvider, get_ocr_provider
from app.documents.pageindex import build_pageindex
from app.documents.service import SOURCE_USER_UPLOADED
from app.documents.storage import get_document_store
from app.documents.structured import store_structured
from app.documents.type_detect import detect_document_kind, detect_document_subtype

logger = logging.getLogger("cura.documents")

SAFE_ERRORS = {
    "too_many_pages": "This document has too many pages to process.",
    "ocr_unavailable": "The document was uploaded, but its text could not be extracted because OCR is not configured.",
    "ocr_failed": "I couldn't read this document.",
    "no_text": "I couldn't read this document.",
    "too_much_text": "This document is too large to process.",
    "extract_failed": "I couldn't read this document.",
}


class DocumentProcessor:
    def __init__(self, db: Session, ocr: OCRProvider | None = None):
        self.db = db
        self.store = get_document_store()
        self.ocr = ocr or get_ocr_provider()

    def process(self, user_id: str, document_id: str) -> None:
        row = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Document not found.")
        row.extraction_status = "processing"
        row.extraction_error = None
        update_meta(
            row,
            processing_status=ProcessingStatus.parsing.value,
            pageindex_status=PageIndexStatus.not_started.value,
        )
        self.db.commit()
        try:
            data = self.store.read(row.storage_key)
            pages = extract_pdf_pages(data)
            if len(pages) > settings.document_max_pages:
                self._fail(row, "too_many_pages")
                return
            try:
                pages = self._maybe_ocr(data, pages)
            except _OCRUnavailable:
                self._fail(row, "ocr_unavailable")
                return
            for page in pages:
                page.text = normalize_extracted_text(page.text)
                page.character_count = len(page.text)
            total = sum(p.character_count for p in pages)
            if total > settings.document_max_extracted_chars:
                self._fail(row, "too_much_text")
                return
            if total == 0:
                self._fail(row, "no_text" if self.ocr.available() else "ocr_unavailable")
                return
            self.db.query(DocumentChunk).filter(DocumentChunk.document_id == row.id).delete()
            drafts = chunk_pages(pages, document_id=row.id, user_id=user_id)
            for draft in drafts:
                self.db.add(
                    DocumentChunk(
                        id=draft.chunk_id,
                        document_id=draft.document_id,
                        user_id=draft.user_id,
                        page_start=draft.page_start,
                        page_end=draft.page_end,
                        text=draft.text,
                        source=SOURCE_USER_UPLOADED,
                    )
                )
            kind = detect_document_kind(pages)
            subtype = detect_document_subtype(pages)
            extracted = extract_facts_from_pages(row.id, pages)
            extracted = extracted.model_copy(update={"document_type": subtype.value})
            store_structured(row, extracted)
            row.extraction_status = "completed"
            row.extraction_error = None
            row.page_count = len(pages)
            row.extracted_chars = total
            update_meta(
                row,
                document_kind=kind.value,
                document_subtype=subtype.value,
                structured_facts_ready=True,
                processing_status=ProcessingStatus.structured_facts_ready.value,
                pageindex_status=PageIndexStatus.building.value,
            )
            self.db.commit()
            logger.info(
                "document_structured_ready document_id=%s pages=%s facts=%s kind=%s subtype=%s",
                row.id,
                len(pages),
                len(extracted.biomarkers),
                kind.value,
                subtype.value,
            )
            try:
                tree = build_pageindex(row.id, pages)
                update_meta(
                    row,
                    pageindex=tree.model_dump(mode="json"),
                    pageindex_status=PageIndexStatus.ready.value,
                    processing_status=ProcessingStatus.ready.value,
                    narrative_ready=True,
                )
                self.db.commit()
                logger.info("document_pageindex_ready document_id=%s nodes=%s", row.id, len(tree.nodes))
            except Exception:
                logger.warning("document_pageindex_failed document_id=%s", document_id)
                update_meta(
                    row,
                    pageindex_status=PageIndexStatus.failed.value,
                    processing_status=ProcessingStatus.partial_failure.value,
                )
                self.db.commit()
            return
        except Exception:
            logger.warning("document_extract_failed document_id=%s", document_id)
            self.db.rollback()
            row = self.db.query(Document).filter(Document.id == document_id).one_or_none()
            if row:
                self._fail(row, "extract_failed")

    def _maybe_ocr(self, data: bytes, pages: list[ExtractedPage]) -> list[ExtractedPage]:
        if not pages:
            return pages
        total = sum(p.character_count for p in pages)
        sparse = [p for p in pages if p.character_count < settings.document_sparse_page_chars]
        most_sparse = len(sparse) > len(pages) / 2
        need = total < settings.document_min_text_chars or most_sparse
        if not need:
            return pages
        targets = sparse[: settings.document_max_ocr_pages]
        if not targets:
            return pages
        if not self.ocr.available():
            if total >= settings.document_min_text_chars and not most_sparse:
                return pages
            if total > 0 and not most_sparse:
                return pages
            raise _OCRUnavailable()
        for page in targets:
            try:
                text = self.ocr.ocr_page(data, page.page_number)
            except Exception:
                logger.warning("ocr_page_failed document_page=%s", page.page_number)
                continue
            page.text = text or ""
            page.character_count = len(page.text.strip())
            page.method = "ocr"
        return pages

    def _fail(self, row: Document, code: str) -> None:
        row.extraction_status = "failed"
        row.extraction_error = SAFE_ERRORS.get(code, SAFE_ERRORS["extract_failed"])
        update_meta(
            row,
            processing_status=ProcessingStatus.failed.value,
            pageindex_status=PageIndexStatus.failed.value,
            structured_facts_ready=False,
        )
        self.db.commit()


class _OCRUnavailable(Exception):
    pass


def process_document_job(document_id: str, user_id: str) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        DocumentProcessor(db).process(user_id, document_id)
    except _OCRUnavailable:
        row = db.query(Document).filter(Document.id == document_id).one_or_none()
        if row:
            row.extraction_status = "failed"
            row.extraction_error = SAFE_ERRORS["ocr_unavailable"]
            db.commit()
    except Exception:
        logger.warning("document_job_failed document_id=%s", document_id)
        try:
            row = db.query(Document).filter(Document.id == document_id).one_or_none()
            if row:
                row.extraction_status = "failed"
                row.extraction_error = SAFE_ERRORS["extract_failed"]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
