"""Build the one canonical user-facing experience for a CURA turn.

The orchestrator intentionally runs *after* medical reasoning and validation. It does
not decide medical facts. It decides how already-approved facts and interpretation
are delivered to the user and whether progressive delivery is safe for this turn.
"""

from __future__ import annotations

import re

from app.contracts.followup import FollowUpSuggestion
from app.contracts.presentation import PresentedFinding, StructuredResponse
from app.contracts.turn_experience import (
    ExperienceBlock,
    ExperienceBlockKind,
    StreamPolicy,
    TurnExperience,
)

_HIGH_RISK_SAFETY_MODES = {
    "EMERGENCY",
    "MEDICATION_BOUNDARY",
    "DIAGNOSIS_RESTRAINT",
}
_HIGH_RISK_ESCALATIONS = {
    "emergency",
    "urgent",
    "urgent_clinician_review",
    "clinician",
}


def _clean(text: str | None) -> str | None:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value or None


def _keep_layout(text: str | None) -> str | None:
    """Keep paragraph and list breaks. Collapse only spaces inside a line."""
    if not text or not text.strip():
        return None
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    value = "\n".join(lines).strip()
    return value or None


def _first_sentences(text: str | None, *, max_chars: int = 320) -> str | None:
    value = _clean(text)
    if not value:
        return None
    if len(value) <= max_chars:
        return value
    parts = re.split(r"(?<=[.!?])\s+", value)
    chosen: list[str] = []
    length = 0
    for part in parts:
        if chosen and length + len(part) + 1 > max_chars:
            break
        chosen.append(part)
        length += len(part) + 1
        if len(chosen) >= 2:
            break
    return " ".join(chosen).strip() or value[:max_chars].rstrip()


def _finding_text(findings: list[PresentedFinding]) -> str | None:
    rows: list[str] = []
    for item in findings[:4]:
        value = (item.value or "").strip()
        unit = (item.unit or "").strip()
        if not value:
            continue
        status = (item.status or "").replace("_", " ").strip()
        suffix = f" ({status})" if status and status.lower() != "unknown" else ""
        rows.append(f"{item.label}: {value}{(' ' + unit) if unit else ''}{suffix}")
    return "; ".join(rows) if rows else None


def _stream_policy(safety_mode: str | None, escalation: str | None) -> StreamPolicy:
    if (safety_mode or "").upper() in _HIGH_RISK_SAFETY_MODES:
        return StreamPolicy.complete_only
    if (escalation or "").lower() in _HIGH_RISK_ESCALATIONS:
        return StreamPolicy.complete_only
    return StreamPolicy.semantic_blocks


class ExperienceOrchestrator:
    """Compose validated response fields into a stable delivery contract."""

    def build(
        self,
        *,
        answer: str,
        presentation: StructuredResponse | None,
        follow_ups: list[FollowUpSuggestion] | None = None,
        safety_mode: str | None = None,
        escalation: str | None = None,
    ) -> TurnExperience:
        p = presentation
        findings = list(p.findings or []) if p else []
        if p and p.related_findings:
            seen = {(x.canonical_key, x.label, x.value) for x in findings}
            for item in p.related_findings:
                key = (item.canonical_key, item.label, item.value)
                if key not in seen:
                    findings.append(item)
                    seen.add(key)

        direct = _keep_layout((p.summary if p else None) or (p.overall_summary if p else None))
        if not direct:
            direct = _finding_text(findings) or _first_sentences(answer)
        interpretation = _keep_layout(p.interpretation if p else None)
        if interpretation and direct and interpretation.lower() == direct.lower():
            interpretation = None

        personal = _clean(p.personal_relevance if p else None)
        uncertainties = [_clean(x) for x in (p.uncertainties if p else [])]
        uncertainties = [x for x in uncertainties if x]
        next_steps = [_clean(x) for x in (p.next_steps if p else [])]
        next_steps = [x for x in next_steps if x]
        continuation = _clean((p.follow_up if p else None))
        if not continuation and follow_ups:
            continuation = _clean(follow_ups[0].text)

        blocks: list[ExperienceBlock] = []

        def add(kind: ExperienceBlockKind, text: str | None = None, facts: list[PresentedFinding] | None = None):
            clean_text = _clean(text)
            fact_rows = list(facts or [])
            if not clean_text and not fact_rows:
                return
            # Do not stream the same sentence twice under different labels.
            if clean_text and any((block.text or "").lower() == clean_text.lower() for block in blocks):
                return
            blocks.append(
                ExperienceBlock(
                    sequence=len(blocks),
                    kind=kind,
                    text=clean_text,
                    findings=fact_rows,
                )
            )

        add(ExperienceBlockKind.direct_answer, direct)
        # Findings remain structured so the frontend can evolve beyond plain text.
        # For a single lookup, the direct answer usually already contains the value;
        # do not repeat it as a second streamed sentence.
        facts_text = _finding_text(findings) if findings else None
        direct_lower = (direct or "").lower()
        single_fact_already_stated = bool(
            len(findings) == 1
            and findings[0].value
            and str(findings[0].value).lower() in direct_lower
        )
        if findings and not single_fact_already_stated:
            add(ExperienceBlockKind.key_facts, facts_text, findings[:4])
        add(ExperienceBlockKind.interpretation, interpretation)
        add(ExperienceBlockKind.personal_relevance, personal)
        if uncertainties:
            add(ExperienceBlockKind.uncertainty, uncertainties[0])
        add(ExperienceBlockKind.continuation, continuation)

        return TurnExperience(
            response_mode=p.mode.value if p else None,
            stream_policy=_stream_policy(safety_mode, escalation),
            direct_answer=direct,
            key_facts=findings,
            interpretation=interpretation,
            personal_relevance=personal,
            uncertainties=uncertainties,
            next_steps=[],
            continuation=continuation,
            blocks=blocks,
        )
