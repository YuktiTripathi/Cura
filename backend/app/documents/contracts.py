from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    document_id: str
    filename: str
    content_type: str
    file_size: int
    source: str = "user_uploaded"
    upload_status: str
    extraction_status: str
    conversation_id: str | None = None
    created_at: str
    sha256: str | None = None
    extraction_error: str | None = None
    processing_status: str | None = None
    pageindex_status: str | None = None
    document_kind: str | None = None
    document_type: str | None = None
    structured_facts_ready: bool = False
    narrative_ready: bool = False


class DocumentPageOut(BaseModel):
    """One page of an uploaded document, as the text Cura extracted from it."""

    document_id: str
    filename: str
    page: int
    page_count: int
    text: str
    # True when the page has no text layer and the text comes from stored (OCR) chunks.
    approximate: bool = False


class DocumentListOut(BaseModel):
    documents: list[DocumentOut] = Field(default_factory=list)


class DocumentStore(Protocol):
    def save(self, user_id: str, document_id: str, data: bytes, suffix: str = ".pdf") -> str: ...

    def read(self, storage_key: str) -> bytes: ...

    def delete(self, storage_key: str) -> None: ...

    def exists(self, storage_key: str) -> bool: ...
