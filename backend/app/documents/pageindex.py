"""Tree-based PageIndex for narrative/section retrieval. No embeddings, no vector DB."""

from __future__ import annotations

import re
from uuid import uuid4

from pydantic import BaseModel, Field

from app.contracts.uploaded_document import DocumentNarrativeFact, PageIndexHit
from app.documents.extraction import ExtractedPage

_HEADING = re.compile(
    r"^(?:"
    r"[A-Z][A-Z0-9 /,&:-]{3,72}|"
    r"\d+(?:\.\d+)*\s+[A-Z][A-Za-z0-9 /,&:-]{2,72}|"
    r"(?:Impression|Findings|Recommendation|Recommendations|Conclusion|Clinical notes|"
    r"Microscopy|Diagnosis|Summary|History|Technique|Comparison|Opinion|"
    r"Gross description|Clinical information|Report comments)s?"
    r")\s*$",
    re.I,
)
_TOKEN = re.compile(r"[a-z0-9]+", re.I)
_SYNONYMS = {
    "radiologist": ("impression", "findings", "radiology"),
    "radiology": ("impression", "findings"),
    "impression": ("impression", "findings"),
    "doctor": ("impression", "conclusion", "opinion", "recommendation"),
    "pathology": ("pathology", "microscopy", "diagnosis"),
    "pathologist": ("pathology", "microscopy", "diagnosis"),
    "recommend": ("recommendation", "recommendations"),
    "recommendation": ("recommendation", "recommendations"),
    "conclude": ("conclusion", "impression", "opinion"),
    "findings": ("findings", "impression"),
}


class PageIndexNode(BaseModel):
    node_id: str
    title: str
    page_start: int
    page_end: int
    text: str
    children: list["PageIndexNode"] = Field(default_factory=list)


class PageIndexTree(BaseModel):
    document_id: str
    nodes: list[PageIndexNode] = Field(default_factory=list)


def build_pageindex(document_id: str, pages: list[ExtractedPage]) -> PageIndexTree:
    nodes: list[PageIndexNode] = []
    current: PageIndexNode | None = None
    buffer: list[str] = []
    for page in pages:
        lines = [line.strip() for line in (page.text or "").splitlines()]
        if not any(lines) and current is None:
            continue
        if not any(lines):
            continue
        for line in lines:
            if _is_heading(line):
                if current is not None:
                    current.text = _join(buffer)
                    current.page_end = max(current.page_end, page.page_number)
                    nodes.append(current)
                current = PageIndexNode(
                    node_id=str(uuid4()),
                    title=line[:120],
                    page_start=page.page_number,
                    page_end=page.page_number,
                    text="",
                )
                buffer = []
                continue
            if current is None:
                current = PageIndexNode(
                    node_id=str(uuid4()),
                    title=f"Page {page.page_number}",
                    page_start=page.page_number,
                    page_end=page.page_number,
                    text="",
                )
                buffer = []
            buffer.append(line)
            current.page_end = page.page_number
        if current is not None and len(buffer) > 40:
            current.text = _join(buffer)
            nodes.append(current)
            current = None
            buffer = []
    if current is not None:
        current.text = _join(buffer)
        nodes.append(current)
    if not nodes:
        for page in pages:
            text = (page.text or "").strip()
            if not text:
                continue
            nodes.append(
                PageIndexNode(
                    node_id=str(uuid4()),
                    title=f"Page {page.page_number}",
                    page_start=page.page_number,
                    page_end=page.page_number,
                    text=text[:4000],
                )
            )
    return PageIndexTree(document_id=document_id, nodes=nodes)


def retrieve_pageindex(tree: PageIndexTree | None, query: str, *, limit: int = 3) -> list[PageIndexHit]:
    if tree is None or not tree.nodes:
        return []
    q_tokens = set(_tokenize(query))
    for token in list(q_tokens):
        q_tokens.update(_SYNONYMS.get(token, ()))
    if not q_tokens:
        return []
    scored: list[PageIndexHit] = []
    for node in _flatten(tree.nodes):
        title_tokens = set(_tokenize(node.title))
        body_tokens = set(_tokenize(node.text[:2000]))
        title_hits = len(q_tokens & title_tokens)
        body_hits = len(q_tokens & body_tokens)
        score = (4.0 * title_hits) + body_hits
        if score <= 0:
            continue
        scored.append(
            PageIndexHit(
                heading=node.title,
                page_start=node.page_start,
                page_end=node.page_end,
                text=node.text[:1200],
                score=score,
                node_id=node.node_id,
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def narrative_facts_from_tree(tree: PageIndexTree) -> list[DocumentNarrativeFact]:
    out: list[DocumentNarrativeFact] = []
    for node in _flatten(tree.nodes):
        text = (node.text or "").strip()
        if len(text) < 40:
            continue
        out.append(
            DocumentNarrativeFact(
                category=_category(node.title),
                heading=node.title,
                text=text[:2000],
                page_start=node.page_start,
                page_end=node.page_end,
                source_document_id=tree.document_id,
            )
        )
    return out[:24]


def _is_heading(line: str) -> bool:
    value = (line or "").strip()
    if not value or len(value) > 80:
        return False
    if value.endswith((".", ",", ";", ":")) and len(value) > 40:
        return False
    return bool(_HEADING.match(value))


def _join(parts: list[str]) -> str:
    return " ".join(part for part in parts if part).strip()[:4000]


def _tokenize(text: str) -> list[str]:
    return [item.group(0).lower() for item in _TOKEN.finditer(text or "")]


def _flatten(nodes: list[PageIndexNode]) -> list[PageIndexNode]:
    out: list[PageIndexNode] = []
    for node in nodes:
        out.append(node)
        if node.children:
            out.extend(_flatten(node.children))
    return out


def _category(title: str) -> str:
    lowered = (title or "").lower()
    for token in ("impression", "findings", "recommendation", "conclusion", "diagnosis", "summary"):
        if token in lowered:
            return token
    return "section"
