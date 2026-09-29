"""Ground medical claims against retrieved evidence. Not a second 'looks good' LLM."""

from __future__ import annotations

import re
from enum import Enum

from app.retrieval.medical import MedicalEvidenceDoc, MedicalEvidenceSource


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CONTEXT = re.compile(
    r"\b(can depend|depends|may|might|sometimes|individual|clinician|not everyone)\b",
    re.I,
)
_ABSOLUTE = re.compile(r"\b(always|never|must|cure[sd]?|prevents|guaranteed)\b", re.I)
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "was",
    "be",
    "this",
    "that",
    "with",
    "from",
    "it",
    "as",
    "by",
}


def extract_claims(answer: str) -> list[str]:
    text = (answer or "").strip()
    if not text:
        return []
    parts = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    return [part for part in parts if len(part) > 24]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if token not in _STOP and len(token) > 2
    }


def classify_claim(claim: str, evidence_text: str) -> ClaimVerdict:
    if _ABSOLUTE.search(claim) and evidence_text:
        if _CONTEXT.search(evidence_text) or "not a single universal" in evidence_text.lower():
            return ClaimVerdict.CONTRADICTED
    if _CONTEXT.search(claim):
        overlap = _tokens(claim) & _tokens(evidence_text)
        if overlap:
            return ClaimVerdict.CONTEXT_DEPENDENT
    if not evidence_text.strip():
        return ClaimVerdict.UNSUPPORTED
    claim_tokens = _tokens(claim)
    evidence_tokens = _tokens(evidence_text)
    if not claim_tokens:
        return ClaimVerdict.UNSUPPORTED
    overlap = claim_tokens & evidence_tokens
    ratio = len(overlap) / max(1, len(claim_tokens))
    if ratio >= 0.45:
        return ClaimVerdict.SUPPORTED
    if ratio >= 0.2:
        return ClaimVerdict.PARTIALLY_SUPPORTED
    return ClaimVerdict.UNSUPPORTED


def check_claims(
    answer: str,
    evidence: list[MedicalEvidenceDoc] | list[MedicalEvidenceSource],
) -> list[tuple[str, ClaimVerdict]]:
    corpus = " ".join(
        getattr(item, "evidence_text", None) or getattr(item, "excerpt", "") or ""
        for item in evidence
    )
    return [(claim, classify_claim(claim, corpus)) for claim in extract_claims(answer)]


def revise_unsupported_answer(
    answer: str,
    evidence: list[MedicalEvidenceDoc] | list[MedicalEvidenceSource],
) -> tuple[str, list[str]]:
    flags: list[str] = []
    kept: list[str] = []
    for claim, verdict in check_claims(answer, evidence):
        if verdict in {ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED}:
            flags.append(verdict.value.lower())
            continue
        kept.append(claim)
    if not flags:
        return answer, flags
    if kept:
        text = " ".join(kept)
        if evidence:
            text += (
                "\n\nThis is general health education based on the retrieved source pointers. "
                "It is not a guideline quotation or a personal diagnosis."
            )
        return text, flags
    if evidence:
        return (
            "I can point you to authoritative sources on this topic, but I do not have a retrieved "
            "guideline excerpt that supports a specific clinical claim here. Please use the listed "
            "sources and a clinician for personal advice.",
            flags,
        )
    return (
        "I don't have retrieved medical evidence for that question, so I won't present a "
        "guideline-verified answer.",
        flags,
    )
