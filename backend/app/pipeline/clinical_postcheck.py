"""Deterministic post-generation clinical checks. Prompt text is not the only layer."""

from __future__ import annotations

import re

from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan

_CAUSAL = re.compile(
    r"\b(caused your|caused the|this proves that|directly caused|is the cause of)\b",
    re.I,
)
_BIOAI_DX = re.compile(
    r"\b(you have (?:type 2 )?diabetes|this confirms (?:type 2 )?diabetes|you are diabetic)\b",
    re.I,
)
_CURRENT_AS_NOW = re.compile(
    r"\byour (?:latest )?(vitamin d|ldl|hdl|hba1c|alt|ast|tsh|ferritin) is\b",
    re.I,
)
_HAS_DATE = re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})\b")
_INTERNAL_ID = re.compile(
    r"\b(blood-\d+|bioai-|assessment_instance|report_id|user_id=|subject_id=)\b",
    re.I,
)
_PII = re.compile(r"\b(eyJ[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{8,}|Bearer\s+\S+|\S+@\S+\.\S+)\b")
_FERRITIN_SUB = re.compile(r"\bferritin\b.{0,40}\b(serum iron|estimated)\b", re.I)


def review_clinical_output(answer: str, *, plan: QueryPlan, context: HealthContext) -> tuple[str, list[str]]:
    flags: list[str] = []
    out = answer or ""
    if _CAUSAL.search(out):
        flags.append("causal_overclaim")
        out = _CAUSAL.sub("can be associated with", out)
        if "does not establish" not in out.lower():
            out = out.rstrip() + " The available information does not establish this as the cause."
    if _BIOAI_DX.search(out) and context.bio_ai_risks:
        flags.append("bio_ai_treated_as_diagnosis")
        out = _BIOAI_DX.sub("your Bio-AI Type 2 Diabetes risk score", out)
        if "not a diagnosis" not in out.lower() and "risk" in out.lower():
            out = out.rstrip() + " A Bio-AI score is a risk assessment, not a diagnosis."
    if context.markers and _CURRENT_AS_NOW.search(out) and not _HAS_DATE.search(out):
        dated = [
            row.measured_at.date() if hasattr(row.measured_at, "date") else row.measured_at
            for row in context.markers
            if getattr(row, "measured_at", None)
        ]
        dated.extend(ev.report_date for ev in (context.evidence or []) if ev.report_date)
        latest = max(dated) if dated else None
        if latest:
            flags.append("stale_presented_as_current")
            label = latest.strftime("%d %b %Y") if hasattr(latest, "strftime") else str(latest)
            out = out.rstrip() + f" This is from your last available report on {label}."
    if _INTERNAL_ID.search(out):
        flags.append("internal_identifier_exposed")
        out = _INTERNAL_ID.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
    if _PII.search(out):
        flags.append("sensitive_payload_leak")
        out = _PII.sub("[removed]", out)
    if "ferritin" in (plan.topic or "").lower() or any(
        (item.key or "").lower() == "ferritin" for item in (context.missing or [])
    ):
        if _FERRITIN_SUB.search(out):
            flags.append("missing_value_substituted")
            out = re.sub(_FERRITIN_SUB, "ferritin is not available in the retrieved results", out)
    return out, flags
