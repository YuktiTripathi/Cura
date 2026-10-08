"""Semantic response contract: CURA decides what matters, the backend guarantees the
values, the frontend decides presentation.

    {summary, blocks[0..4], follow_ups[0..3], sources[]}

``summary`` is a standalone conversational answer (safe Markdown); it must make sense
with no blocks rendered. ``blocks`` are optional, generic, and composable; no block type
belongs to an intent. Blocks carry ``evidence`` keys, never copied numbers: the backend
resolves each key from the member's normalized health context into ``values``.

Evidence keys:  blood.<code>.latest   blood.<code>.trend   bioai.<code>
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockType = Literal[
    "text",          # a short separate idea in prose
    "metric",        # one value, resolved from evidence
    "metric_group",  # several values (a report section; may start collapsed)
    "priority_list",  # ranked items, each with optional evidence
    "risk",          # Bio-AI risk assessments, resolved from evidence
    "comparison",    # previous vs latest, resolved from evidence
    "insight",       # a connection between findings + the values behind it
    "reassurance",   # what looks fine
    "action_list",   # practical next steps
    "nutrition",     # increase / reduce / why it matters
    "warning",       # something that needs prompt attention (safety layer decides urgency)
]
BLOCK_TYPES: tuple[str, ...] = BlockType.__args__  # type: ignore[attr-defined]


class ResolvedValue(BaseModel):
    """A value the backend read from the member's record (never from model text)."""

    key: str
    label: str
    kind: Literal["blood", "bio_ai"]
    value: float | str | None = None
    unit: str | None = None
    status: str | None = None  # high | low | normal | critical | moderate | ...
    reference_low: float | None = None
    reference_high: float | None = None
    date: str | None = None
    previous: float | str | None = None
    previous_date: str | None = None
    direction: str | None = None  # increased | decreased | unchanged


class BlockItem(BaseModel):
    title: str | None = None
    text: str | None = None
    evidence: list[str] = Field(default_factory=list)
    values: list[ResolvedValue] = Field(default_factory=list)


class ResponseBlock(BaseModel):
    type: BlockType
    title: str | None = None
    text: str | None = None  # safe Markdown
    items: list[BlockItem] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    values: list[ResolvedValue] = Field(default_factory=list)
    increase: list[str] = Field(default_factory=list)  # nutrition
    reduce: list[str] = Field(default_factory=list)  # nutrition
    collapsed: bool = False  # metric_group: start folded (e.g. the full report)


class ResponseSource(BaseModel):
    type: Literal["blood_report", "bio_ai", "questionnaire", "uploaded_document", "medical_reference"]
    date: str | None = None
    label: str | None = None


class SemanticResponse(BaseModel):
    summary: str
    blocks: list[ResponseBlock] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    sources: list[ResponseSource] = Field(default_factory=list)
