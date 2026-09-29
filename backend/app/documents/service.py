from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import DocumentUploadError, DocumentValidationError, NotFoundError
from app.db.models import Document
from app.documents.contracts import DocumentOut
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
        row = self.get_owned(user_id, document_id)
        key = row.storage_key
        self.db.delete(row)
        self.db.commit()
        try:
            self.store.delete(key)
        except Exception:
            logger.warning("document_file_delete_failed document_id=%s", document_id)
