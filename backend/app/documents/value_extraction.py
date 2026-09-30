from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from app.pipeline.intent import MARKER_ALIASES, NAMES
from app.pipeline.lab_parameters import aliases_for, display_name_for

_SKIP = re.compile(
    r"\b(recommended|target|goal|below|above|less than|greater than|previous|prior|last time)\b",
    re.I,
)
_NUMBER = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(%|mg/dl|mg/dL|g/dl|g/dL|u/l|U/L|miu/l|mIU/L|ng/ml|pg/ml|µiu/ml|uiu/ml|mmol/l)?",
    re.I,
)
_DATE = re.compile(
    r"\b(?:collection date|test date|report date|date)[:\s]+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)
_RANGE = re.compile(
    r"(?:reference(?:\s*range)?|range)[:\s]*([0-9]+(?:\.[0-9]+)?)\s*[-–to]+\s*([0-9]+(?:\.[0-9]+)?)",
    re.I,
)
_RANGE_BARE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*[-–]\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dl|mg/dL)?")


@dataclass
class ExtractedValue:
    parameter: str
    name: str
    value: float | None
    unit: str | None
    source_text: str
    page: int | None
    date: date | None
    date_kind: str | None
    reference_low: float | None = None
    reference_high: float | None = None
    confidence: str = "low"


def extract_marker_from_text(text: str, marker_key: str, page: int | None = None) -> ExtractedValue | None:
    if not text or not marker_key:
        return None
    aliases = [a for a, code in MARKER_ALIASES.items() if code == marker_key]
    aliases.extend(aliases_for(marker_key))
    aliases.append(marker_key.replace("_", " "))
    aliases.append(display_name_for(marker_key).lower())
    aliases = sorted({a.lower() for a in aliases if a}, key=len, reverse=True)
    lowered = text.lower()
    hit_alias = next((a for a in sorted(aliases, key=len, reverse=True) if a in lowered), None)
    if not hit_alias:
        return None
    idx = lowered.find(hit_alias)
    after = text[idx + len(hit_alias) :]
    window = text[max(0, idx - 20) : idx + len(hit_alias) + 80]
    if _SKIP.search(window):
        return ExtractedValue(
            parameter=marker_key,
            name=NAMES.get(marker_key, marker_key),
            value=None,
            unit=None,
            source_text=window.strip()[:200],
            page=page,
            date=_find_date(text),
            date_kind="collection_or_report" if _DATE.search(text) else None,
            confidence="low",
        )
    match = _NUMBER.search(after[:80])
    if not match:
        return ExtractedValue(
            parameter=marker_key,
            name=NAMES.get(marker_key, marker_key),
            value=None,
            unit=None,
            source_text=window.strip()[:200],
            page=page,
            date=_find_date(text),
            date_kind="collection_or_report" if _DATE.search(text) else None,
            confidence="low",
        )
    unit = (match.group(2) or "").strip() or None
    if not unit and re.search(r"mg/dl", after[:40], re.I):
        unit = "mg/dL"
    elif unit:
        unit = unit.replace("mg/dl", "mg/dL").replace("MG/DL", "mg/dL")
    rng = _RANGE.search(text) or _RANGE.search(after[:120]) or _RANGE_BARE.search(after[:80])
    return ExtractedValue(
        parameter=marker_key,
        name=display_name_for(marker_key) if marker_key else NAMES.get(marker_key, marker_key),
        value=float(match.group(1)),
        unit=unit.replace("mg/dl", "mg/dL") if unit else None,
        source_text=window.strip()[:200],
        page=page,
        date=_find_date(text),
        date_kind="collection_or_report" if _DATE.search(text) else None,
        reference_low=float(rng.group(1)) if rng else None,
        reference_high=float(rng.group(2)) if rng else None,
        confidence="high",
    )


def extract_keys_present(text: str) -> set[str]:
    lowered = text.lower()
    return {code for alias, code in MARKER_ALIASES.items() if alias in lowered}


def find_report_date(text: str) -> date | None:
    return _find_date(text)


def _find_date(text: str) -> date | None:
    m = _DATE.search(text)
    if not m:
        return None
    raw = m.group(1)
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
