"""Canonical user-experience contract for a completed CURA turn.

This contract sits after retrieval/reasoning/validation and before transport/rendering.
It contains no chain-of-thought. It only describes user-visible, already-validated
response blocks and the continuation state for the conversation.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.presentation import PresentedFinding


class ExperienceBlockKind(str, Enum):
    direct_answer = "direct_answer"
    key_facts = "key_facts"
    interpretation = "interpretation"
    personal_relevance = "personal_relevance"
    uncertainty = "uncertainty"
    next_step = "next_step"
    continuation = "continuation"


class StreamPolicy(str, Enum):
    semantic_blocks = "SEMANTIC_BLOCKS"
    complete_only = "COMPLETE_ONLY"


class ExperienceBlock(BaseModel):
    sequence: int
    kind: ExperienceBlockKind
    text: str | None = None
    findings: list[PresentedFinding] = Field(default_factory=list)


class TurnExperience(BaseModel):
    """Single response contract consumed by streaming and final presentation."""

    response_mode: str | None = None
    stream_policy: StreamPolicy = StreamPolicy.semantic_blocks
    direct_answer: str | None = None
    key_facts: list[PresentedFinding] = Field(default_factory=list)
    interpretation: str | None = None
    personal_relevance: str | None = None
    uncertainties: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    continuation: str | None = None
    blocks: list[ExperienceBlock] = Field(default_factory=list)
