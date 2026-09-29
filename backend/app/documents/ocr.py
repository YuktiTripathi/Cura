from __future__ import annotations

import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger("cura.documents")


class OCRProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def ocr_page(self, pdf_bytes: bytes, page_number: int) -> str: ...


class NoneOCRProvider:
    name = "none"

    def available(self) -> bool:
        return False

    def ocr_page(self, pdf_bytes: bytes, page_number: int) -> str:
        raise RuntimeError("ocr_unavailable")


class LocalOCRProvider:
    """Optional pytesseract + pypdfium2/pdf2image. Missing deps → unavailable."""

    name = "local"

    def available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
        except Exception:
            return False
        return True

    def ocr_page(self, pdf_bytes: bytes, page_number: int) -> str:
        raise RuntimeError("ocr_unavailable")


def get_ocr_provider() -> OCRProvider:
    raw = (settings.document_ocr_provider or "none").strip().lower()
    if raw in {"local", "tesseract"}:
        provider = LocalOCRProvider()
        if provider.available():
            return provider
        logger.info("ocr_provider_unavailable requested=%s", raw)
        return NoneOCRProvider()
    return NoneOCRProvider()
