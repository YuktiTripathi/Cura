from __future__ import annotations

from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    character_count: int
    method: str = "text"


def extract_pdf_pages(data: bytes) -> list[ExtractedPage]:
    reader = PdfReader(stream_from(data))
    pages: list[ExtractedPage] = []
    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        pages.append(ExtractedPage(page_number=i, text=raw, character_count=len(raw.strip()), method="text"))
    return pages


def stream_from(data: bytes):
    from io import BytesIO

    return BytesIO(data)
