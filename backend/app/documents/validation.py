from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.errors import DocumentValidationError

ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
PDF_MAGIC = b"%PDF"


def display_filename(raw: str | None) -> str:
    name = Path(raw or "document.pdf").name
    name = name.replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        return "document.pdf"
    return name[:255]


def validate_pdf_upload(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    max_bytes: int | None = None,
) -> tuple[str, str]:
    limit = max_bytes if max_bytes is not None else settings.document_max_upload_bytes
    if data is None or len(data) == 0:
        raise DocumentValidationError("The file is empty.")
    if len(data) > limit:
        raise DocumentValidationError("This file is too large to upload.")

    shown = display_filename(filename)
    ext = Path(shown).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError("Only PDF documents are supported.")

    declared = (content_type or "").split(";")[0].strip().lower()
    if declared and declared not in ALLOWED_CONTENT_TYPES and declared not in {"application/octet-stream", ""}:
        raise DocumentValidationError("Only PDF documents are supported.")

    if data[:4] == b"MZ" or data[:2] == b"#!" or data[:4] == b"PK\x03\x04":
        raise DocumentValidationError("This file type is not supported.")
    if not data.startswith(PDF_MAGIC):
        raise DocumentValidationError("This file is not a valid PDF.")
    if b"%%EOF" not in data[-1024:] and b"%%EOF" not in data:
        raise DocumentValidationError("This file is not a valid PDF.")

    return shown, "application/pdf"
