from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import DocumentUploadError, DocumentValidationError, NotFoundError
from app.db.models import Document, DocumentChunk
from app.documents.contracts import DocumentFactOut, DocumentFactsOut, DocumentOut, DocumentPageOut
from app.documents.extraction import extract_pdf_pages
from app.documents.normalization import normalize_extracted_text
from app.documents.storage import LocalDocumentStore, get_document_store
from app.documents.validation import validate_pdf_upload

logger = logging.getLogger("cura.documents")

SOURCE_USER_UPLOADED = "user_uploaded"


def _iso(value: datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


def to_out(row: Document) -> DocumentOut:
    from app.documents.metadata import load_meta

    meta = load_meta(row)
    pageindex = meta.get("pageindex_status")
    processing = meta.get("processing_status")
    structured_ready = bool(meta.get("structured_facts_ready")) or (
        row.extraction_status == "completed" and bool((meta.get("structured_health") or {}).get("biomarkers"))
    )
    return DocumentOut(
        document_id=row.id,
        filename=row.original_filename,
        content_type=row.content_type,
        file_size=row.file_size,
        source=row.source,
        upload_status=row.upload_status,
        extraction_status=row.extraction_status,
        conversation_id=row.conversation_id,
        created_at=_iso(row.created_at),
        sha256=row.sha256,
        extraction_error=row.extraction_error,
        processing_status=processing,
        pageindex_status=pageindex,
        document_kind=meta.get("document_kind"),
        document_type=meta.get("document_subtype"),
        structured_facts_ready=structured_ready or row.extraction_status == "completed",
        narrative_ready=pageindex == "READY",
    )


class DocumentService:
    def __init__(self, db: Session, store: LocalDocumentStore | None = None):
        self.db = db
        self.store = store or get_document_store()

    def upload(
        self,
        *,
        user_id: str,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        conversation_id: str | None = None,
    ) -> DocumentOut:
        shown, mime = validate_pdf_upload(filename=filename, content_type=content_type, data=data)
        document_id = str(uuid.uuid4())
        digest = hashlib.sha256(data).hexdigest()
        storage_key = None
        try:
            storage_key = self.store.save(user_id, document_id, data, suffix=".pdf")
            row = Document(
                id=document_id,
                user_id=user_id,
                conversation_id=conversation_id or None,
                original_filename=shown,
                content_type=mime,
                file_size=len(data),
                storage_key=storage_key,
                upload_status="uploaded",
                extraction_status="processing",
                source=SOURCE_USER_UPLOADED,
                sha256=digest,
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        except DocumentValidationError:
            raise
        except Exception:
            logger.warning("document_upload_failed document_id=%s", document_id)
            if storage_key:
                try:
                    self.store.delete(storage_key)
                except Exception:
                    pass
            self.db.rollback()
            raise DocumentUploadError()
        logger.info(
            "document_uploaded document_id=%s bytes=%s source=%s",
            document_id,
            len(data),
            SOURCE_USER_UPLOADED,
        )
        return to_out(row)

    def get_owned(self, user_id: str, document_id: str) -> Document:
        row = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id, Document.upload_status != "deleted")
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Document not found.")
        return row

    def get(self, user_id: str, document_id: str) -> DocumentOut:
        return to_out(self.get_owned(user_id, document_id))

    def facts(self, user_id: str, document_id: str) -> DocumentFactsOut:
        """Measurements extracted from an owned document, in report order."""
        from app.documents.facts import infer_status
        from app.documents.structured import load_structured
        from app.pipeline.lab_parameters import display_name_for

        row = self.get_owned(user_id, document_id)
        extracted = load_structured(row)
        facts: list[DocumentFactOut] = []
        for item in (extracted.biomarkers if extracted else []):
            value = item.value if isinstance(item.value, (int, float)) and not isinstance(item.value, bool) else None
            facts.append(
                DocumentFactOut(
                    key=item.normalized_name,
                    label=display_name_for(item.normalized_name) or item.name,
                    value=value,
                    unit=item.unit,
                    reference_low=item.reference_low,
                    reference_high=item.reference_high,
                    reference_text=item.reference_range,
                    status=item.flag or infer_status(value, item.reference_low, item.reference_high, None),
                    page=item.source_page,
                    line=item.source_line,
                    excerpt=item.excerpt,
                )
            )
        facts.sort(key=lambda f: (f.page or 0, f.line or 0, f.label))
        return DocumentFactsOut(document_id=row.id, filename=row.original_filename, ready=extracted is not None, facts=facts)

    def page(self, user_id: str, document_id: str, page: int) -> DocumentPageOut:
        """Page text normalized exactly as at extraction time, so excerpts and line numbers match."""
        row = self.get_owned(user_id, document_id)
        pages = extract_pdf_pages(self.store.read(row.storage_key))
        if page < 1 or page > len(pages):
            raise NotFoundError("Page not found.")
        text = normalize_extracted_text(pages[page - 1].text)
        approximate = False
        if not text:
            chunk = (
                self.db.query(DocumentChunk)
                .filter(
                    DocumentChunk.document_id == row.id,
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.page_start <= page,
                    DocumentChunk.page_end >= page,
                )
                .order_by(DocumentChunk.page_start)
                .first()
            )
            text = chunk.text if chunk else ""
            approximate = bool(chunk)
        return DocumentPageOut(
            document_id=row.id,
            filename=row.original_filename,
            page=page,
            page_count=len(pages),
            text=text,
            approximate=approximate,
        )

    def list_for_user(self, user_id: str) -> list[DocumentOut]:
        rows = (
            self.db.query(Document)
            .filter(Document.user_id == user_id, Document.upload_status != "deleted")
            .order_by(Document.created_at.desc())
            .all()
        )
        return [to_out(r) for r in rows]

    def assert_owned(self, user_id: str, document_ids: list[str]) -> list[Document]:
        docs = []
        for did in document_ids:
            docs.append(self.get_owned(user_id, did))
        return docs

    def delete(self, user_id: str, document_id: str) -> None:
        from app.core.retention import delete_document_derived

        row = self.get_owned(user_id, document_id)
        key = row.storage_key
        delete_document_derived(self.db, document_id, user_id)
        self.db.delete(row)
        self.db.commit()
        try:
            self.store.delete(key)
        except Exception:
            logger.warning("document_file_delete_failed document_id=%s", document_id)
