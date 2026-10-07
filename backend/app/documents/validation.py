from __future__ import annotations

import re
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

    if _ACTIVE_CONTENT.search(data):
        # Lab reports never need scripts, launch actions or attachments.
        raise DocumentValidationError("This PDF contains active content and can't be uploaded.")
    _check_structure(data)
    scan_for_malware(data)
    return shown, "application/pdf"


# PDF name objects may hex-escape letters (/J#61vaScript), so normalize before matching.
_ACTIVE_CONTENT = re.compile(
    rb"/(?:JavaScript|JS|Launch|EmbeddedFile|EmbeddedFiles|RichMedia|XFA|SubmitForm|ImportData|GoToR)\b"
)


def _check_structure(data: bytes) -> None:
    """Reject encrypted PDFs and PDFs over the page cap before anything is stored."""
    if _ACTIVE_CONTENT.search(_normalize_names(data)):
        raise DocumentValidationError("This PDF contains active content and can't be uploaded.")
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise DocumentValidationError("Password-protected PDFs can't be read. Please upload an unlocked copy.")
        pages = len(reader.pages)
    except DocumentValidationError:
        raise
    except Exception:
        # Damaged PDFs are accepted here and marked unreadable by extraction, as before.
        return
    if pages > int(settings.document_max_pages):
        raise DocumentValidationError(
            f"This PDF has {pages} pages. Please upload a report of {settings.document_max_pages} pages or fewer."
        )


def _normalize_names(data: bytes) -> bytes:
    return re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), data)


def scan_for_malware(data: bytes) -> None:
    """Optional ClamAV scan over clamd's INSTREAM protocol (DOCUMENT_CLAMAV_HOST).

    Fails closed: if a scanner is configured but cannot be reached, the upload is refused.
    """
    host = (settings.document_clamav_host or "").strip()
    if not host:
        return
    import socket
    import struct

    try:
        with socket.create_connection((host, int(settings.document_clamav_port)), timeout=15) as conn:
            conn.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), 65536):
                chunk = data[start:start + 65536]
                conn.sendall(struct.pack("!L", len(chunk)) + chunk)
            conn.sendall(struct.pack("!L", 0))
            reply = conn.recv(4096).decode("utf-8", "replace")
    except OSError as exc:
        raise DocumentValidationError("We couldn't check this file right now. Please try again shortly.") from exc
    if "FOUND" in reply:
        raise DocumentValidationError("This file failed a security check and can't be uploaded.")
    if "OK" not in reply:
        raise DocumentValidationError("We couldn't check this file right now. Please try again shortly.")
