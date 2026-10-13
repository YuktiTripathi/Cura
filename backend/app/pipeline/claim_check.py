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
_NEGATION = re.compile(r"\b(not|never|cannot|can't|do not|don't|no longer|must not|should not)\b", re.I)
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


def claim_polarity(claim: str) -> str:
    return "negated" if _NEGATION.search(claim or "") else "affirmed"


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
    if claim_polarity(claim) == "negated" and claim_polarity(evidence_text) == "affirmed" and ratio >= 0.3:
        return ClaimVerdict.CONTRADICTED
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
        return " ".join(kept), flags
    if evidence:
        return (
            "I couldn't verify a reliable answer to that question just now, so I don't want to "
            "give you a misleading explanation.",
            flags,
        )
    return (
        "I don't have retrieved medical evidence for that question, so I won't present a "
        "guideline-verified answer.",
        flags,
    )


_SUPPORTING = {ClaimVerdict.SUPPORTED, ClaimVerdict.PARTIALLY_SUPPORTED, ClaimVerdict.CONTEXT_DEPENDENT}


def map_claims_to_passages(
    answer: str,
    evidence: list[MedicalEvidenceDoc] | list[MedicalEvidenceSource],
) -> list[tuple[str, ClaimVerdict, int | None]]:
    """Each claim with its verdict and the index of the passage that best supports it (plan 4.7)."""
    texts = [getattr(item, "evidence_text", None) or getattr(item, "excerpt", "") or "" for item in evidence]
    rank = {
        ClaimVerdict.SUPPORTED: 3,
        ClaimVerdict.CONTEXT_DEPENDENT: 2,
        ClaimVerdict.PARTIALLY_SUPPORTED: 1,
        ClaimVerdict.UNSUPPORTED: 0,
        ClaimVerdict.CONTRADICTED: -1,
    }
    mapped: list[tuple[str, ClaimVerdict, int | None]] = []
    for claim in extract_claims(answer):
        best: tuple[int, ClaimVerdict, int | None] = (0, ClaimVerdict.UNSUPPORTED, None)
        for index, text in enumerate(texts):
            verdict = classify_claim(claim, text)
            if verdict == ClaimVerdict.CONTRADICTED:
                best = (-1, verdict, index)
                break
            if rank[verdict] > best[0]:
                best = (rank[verdict], verdict, index)
        mapped.append((claim, best[1], best[2] if best[1] in _SUPPORTING else None))
    return mapped


def supporting_passages(answer: str, evidence: list) -> list:
    """Passages that support at least one claim, in retrieval order."""
    used = {index for _, _, index in map_claims_to_passages(answer, evidence) if index is not None}
    return [doc for index, doc in enumerate(evidence) if index in used]


def unmapped_share(answer: str, evidence: list) -> float:
    mapped = map_claims_to_passages(answer, evidence)
    if not mapped:
        return 0.0
    return sum(1 for _, _, index in mapped if index is None) / len(mapped)
