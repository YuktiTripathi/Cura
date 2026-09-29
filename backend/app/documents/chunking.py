from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import settings
from app.documents.extraction import ExtractedPage

SOURCE = "user_uploaded"


@dataclass
class ChunkDraft:
    chunk_id: str
    document_id: str
    user_id: str
    page_start: int
    page_end: int
    text: str
    source: str = SOURCE


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    document_id: str,
    user_id: str,
    size: int | None = None,
    overlap: int | None = None,
) -> list[ChunkDraft]:
    limit = size or settings.document_chunk_size
    ov = overlap if overlap is not None else settings.document_chunk_overlap
    drafts: list[ChunkDraft] = []
    for page in pages:
        text = (page.text or "").strip()
        if not text:
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        buf = ""
        for para in paragraphs:
            candidate = f"{buf}\n\n{para}".strip() if buf else para
            if len(candidate) <= limit:
                buf = candidate
                continue
            if buf:
                drafts.append(_draft(document_id, user_id, page.page_number, buf))
                tail = buf[-ov:] if ov and len(buf) > ov else ""
                buf = f"{tail}\n\n{para}".strip() if tail else para
            else:
                for piece in _hard_split(para, limit, ov):
                    drafts.append(_draft(document_id, user_id, page.page_number, piece))
                buf = ""
            if len(buf) > limit:
                for piece in _hard_split(buf, limit, ov):
                    drafts.append(_draft(document_id, user_id, page.page_number, piece))
                buf = ""
        if buf:
            drafts.append(_draft(document_id, user_id, page.page_number, buf))
    return drafts


def _draft(document_id: str, user_id: str, page: int, text: str) -> ChunkDraft:
    return ChunkDraft(
        chunk_id=str(uuid.uuid4()),
        document_id=document_id,
        user_id=user_id,
        page_start=page,
        page_end=page,
        text=text,
        source=SOURCE,
    )


def _hard_split(text: str, limit: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + limit)
        parts.append(text[start:end])
        if end >= n:
            break
        start = max(0, end - overlap)
    return parts
