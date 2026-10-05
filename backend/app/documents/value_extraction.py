from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

from app.pipeline.intent import MARKER_ALIASES, NAMES
from app.pipeline.lab_parameters import PARAMETERS, aliases_for, display_name_for

_SKIP = re.compile(
    r"\b(recommended|target|goal|below|above|less than|greater than|previous|prior|last time)\b",
    re.I,
)
# Longer units first so "mg/dl" wins over "mg/d…" and "miu/ml" over "miu/l".
_UNITS = (
    "mg/dl", "mg/l", "g/dl", "g/l", "ng/ml", "ng/dl", "pg/ml", "µg/dl", "ug/dl", "µiu/ml", "uiu/ml",
    "miu/ml", "miu/l", "iu/ml", "iu/l", "u/l", "mmol/mol", "mmol/l", "µmol/l", "umol/l", "nmol/l",
    "pmol/l", "meq/l", "%",
)
_UNIT_CANON = {
    "mg/dl": "mg/dL", "mg/l": "mg/L", "g/dl": "g/dL", "g/l": "g/L", "ng/ml": "ng/mL", "ng/dl": "ng/dL",
    "pg/ml": "pg/mL", "µg/dl": "µg/dL", "ug/dl": "µg/dL", "µiu/ml": "µIU/mL", "uiu/ml": "µIU/mL",
    "miu/ml": "mIU/mL", "miu/l": "mIU/L", "iu/ml": "IU/mL", "iu/l": "IU/L", "u/l": "U/L",
    "mmol/mol": "mmol/mol", "mmol/l": "mmol/L", "µmol/l": "µmol/L", "umol/l": "µmol/L",
    "nmol/l": "nmol/L", "pmol/l": "pmol/L", "meq/l": "mEq/L", "%": "%",
}
_NUM = r"[0-9]+(?:\.[0-9]+)?"
# A standalone number: not the "1" in "HbA1c" or the "25" in a date like 2026-09-25.
_NUMBER = re.compile(
    rf"(?<![\w.\-/])({_NUM})(?![\w.])\s*(" + "|".join(re.escape(u) for u in _UNITS) + r")?(?![\w/])",
    re.I,
)
_DATE = re.compile(
    r"\b(?:collection date|test date|report date|date)[:\s]+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.I,
)
_TO = r"\s*(?:-|–|—|to)\s*"
_RANGE_LABELLED = re.compile(
    rf"\b(?:reference(?:\s+(?:range|interval))?|ref(?:\.|erence)?(?:\s+range)?|normal(?:\s+range)?|range)"
    rf"\s*[:=]?\s*\(?\s*({_NUM}){_TO}({_NUM})",
    re.I,
)
_RANGE_BARE = re.compile(rf"(?<![\w.])({_NUM}){_TO}({_NUM})(?![\w.])", re.I)
# One-sided reference bounds such as "< 100", "<=5.6", "up to 1.0", "> 40".
_BOUND = re.compile(
    rf"(?:(<=|≤|<|up to|less than|below)|(>=|≥|>|more than|greater than|above))\s*({_NUM})(?![\w.])",
    re.I,
)


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
    reference_text: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class _Mention:
    start: int
    end: int
    key: str


@lru_cache(maxsize=1)
def _name_index() -> tuple[re.Pattern[str], dict[str, str]]:
    """Every known biomarker name -> canonical key, as one longest-first alternation."""
    owners: dict[str, str] = {}
    for param in PARAMETERS:
        names = [*aliases_for(param.key), param.key.replace("_", " "), display_name_for(param.key)]
        for name in names:
            owners.setdefault(name.strip().lower(), param.key)
    for alias, code in MARKER_ALIASES.items():
        owners.setdefault(alias.strip().lower(), code)
    names = sorted((name for name in owners if name), key=len, reverse=True)
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(name) for name in names) + r")(?!\w)", re.I)
    return pattern, owners


def _mentions(text: str) -> list[_Mention]:
    """Biomarker names in reading order. Leftmost-longest matching means the generic
    "cholesterol" inside "LDL Cholesterol" is part of the LDL name, not a mention of its own."""
    pattern, owners = _name_index()
    return [_Mention(m.start(), m.end(), owners[m.group(1).lower()]) for m in pattern.finditer(text)]


def _row_end(text: str, mention: _Mention, mentions: list[_Mention]) -> int:
    """A result row runs from its name to the next *different* biomarker name.

    Same-line layouts stop at the newline once a value is present, so LDL cannot
    take HbA1c's range from the next printed row. Columnar table exports often put
    the name, value, unit and range on separate lines; if this line has no number,
    the row continues across those following lines until the next marker.
    """
    newline = text.find("\n", mention.end)
    line_end = len(text) if newline < 0 else newline
    next_marker = len(text)
    for other in mentions:
        if other.start >= mention.end and other.key != mention.key:
            next_marker = other.start
            break
    same_line = text[mention.end : min(line_end, next_marker)]
    if _NUMBER.search(same_line):
        return min(line_end, next_marker)
    return next_marker


def _has_value(text: str, mention: _Mention, mentions: list[_Mention]) -> bool:
    return bool(_NUMBER.search(text[mention.end:_row_end(text, mention, mentions)]))


def _row_start(text: str, mention: _Mention, mentions: list[_Mention], line_start: int) -> int:
    """Quote the whole line unless an earlier result with its own value shares it."""
    for other in mentions:
        if line_start <= other.start < mention.start and other.key != mention.key and _has_value(text, other, mentions):
            return mention.start
    return line_start


def _reference(row_after_value: str) -> tuple[float | None, float | None, str | None]:
    labelled = _RANGE_LABELLED.search(row_after_value)
    if labelled:
        return float(labelled.group(1)), float(labelled.group(2)), f"{labelled.group(1)}-{labelled.group(2)}"
    bare = _RANGE_BARE.search(row_after_value)
    if bare:
        return float(bare.group(1)), float(bare.group(2)), bare.group(0).strip()
    bound = _BOUND.search(row_after_value)
    if bound:
        limit = float(bound.group(3))
        if bound.group(1):
            return None, limit, bound.group(0).strip()
        return limit, None, bound.group(0).strip()
    return None, None, None


def extract_marker_from_text(text: str, marker_key: str, page: int | None = None) -> ExtractedValue | None:
    """Value, unit and reference range for one biomarker, taken from that biomarker's own row.

    A number belongs to the nearest biomarker name before it on the same line. If another
    biomarker's name sits between a name and the next number (e.g. "Glycated Haemoglobin
    (HbA1c): 6.1"), the earlier name has no value in that row.
    """
    if not text or not marker_key:
        return None
    mentions = _mentions(text)
    own = [m for m in mentions if m.key == marker_key]
    if not own:
        return None
    report_date = _find_date(text)
    date_kind = "collection_or_report" if _DATE.search(text) else None
    name = display_name_for(marker_key) if marker_key else NAMES.get(marker_key, marker_key)
    first_row: str | None = None
    first_line: int | None = None
    for mention in own:
        line_start = text.rfind("\n", 0, mention.start) + 1
        row_end = _row_end(text, mention, mentions)
        row_text = text[_row_start(text, mention, mentions, line_start):row_end].strip()
        line = text.count("\n", 0, mention.start) + 1
        if first_row is None:
            first_row, first_line = row_text, line
        context = text[max(line_start, mention.start - 20):row_end]
        if _SKIP.search(context):
            continue
        after = text[mention.end:row_end]
        match = _NUMBER.search(after)
        if not match:
            continue
        unit_raw = (match.group(2) or "").lower()
        unit = _UNIT_CANON.get(unit_raw) if unit_raw else None
        low, high, ref_text = _reference(after[match.end():])
        return ExtractedValue(
            parameter=marker_key,
            name=name,
            value=float(match.group(1)),
            unit=unit,
            source_text=row_text[:200],
            page=page,
            date=report_date,
            date_kind=date_kind,
            reference_low=low,
            reference_high=high,
            confidence="high",
            reference_text=ref_text,
            line=line,
        )
    return ExtractedValue(
        parameter=marker_key,
        name=NAMES.get(marker_key, marker_key),
        value=None,
        unit=None,
        source_text=(first_row or "")[:200],
        page=page,
        date=report_date,
        date_kind=date_kind,
        confidence="low",
        line=first_line,
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
