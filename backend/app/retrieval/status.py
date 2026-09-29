"""Controlled retrieval outcomes. Distinct from user-facing copy."""

from __future__ import annotations

from integrations.supershyft.db import (
    DB_AUTH_FAILED,
    DB_CONNECTION_FAILED,
    DB_NO_RECORDS,
    DB_NOT_CONFIGURED,
    DB_PROVIDER_NOT_CALLED,
    DB_QUERY_FAILED,
)

SUCCESS = "success"
NO_DATA = "no_data"
PROVIDER_UNAVAILABLE = "provider_unavailable"
EXTRACTION_FAILED = "extraction_failed"
UNAUTHORIZED = "unauthorized"
ERROR = "error"
NOT_REQUIRED = "not_required"

_PROVIDER_REASONS = {
    DB_CONNECTION_FAILED,
    DB_NOT_CONFIGURED,
    DB_QUERY_FAILED,
    "provider_unavailable",
}

_NO_DATA_STATUSES = {
    "document_no_match",
    "document_missing",
    "cross_source_missing_document",
}

_EXTRACTION_STATUSES = {
    "document_failed",
    "document_ocr_unavailable",
}


def infer_retrieval_status(
    *,
    personal_required: bool,
    documents_required: bool,
    meta_status: str | None,
    db_status: str | None,
    evidence_count: int,
    has_missing: bool = False,
) -> str:
    status = (meta_status or "").strip()
    reason = (db_status or "").strip()
    if status == "provider_unavailable" or reason in _PROVIDER_REASONS:
        return PROVIDER_UNAVAILABLE
    if reason == DB_AUTH_FAILED:
        return UNAUTHORIZED
    if status in _EXTRACTION_STATUSES:
        return EXTRACTION_FAILED
    if status == "safety_block":
        return NOT_REQUIRED
    if not personal_required and not documents_required:
        return NOT_REQUIRED
    if status in _NO_DATA_STATUSES:
        return NO_DATA
    if evidence_count > 0:
        return SUCCESS
    if has_missing or reason == DB_NO_RECORDS:
        return NO_DATA
    if reason == DB_PROVIDER_NOT_CALLED and documents_required:
        if status in {"document_processing"}:
            return ERROR
        return NO_DATA
    if personal_required or documents_required:
        return NO_DATA
    return NOT_REQUIRED
