from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

from app.pipeline.intent import MARKER_ALIASES, NAMES
from app.pipeline.lab_parameters import PARAMETERS, aliases_for, display_name_for

_SKIP = re.compile(
    r"\b(recommended|target|goal|less than|greater than)\b",
    re.I,
)
_HISTORICAL = re.compile(r"\b(previous|prior|last time|historical)\b", re.I)
# Lines that name equipment, identity, or a diagnostic band. Their digits are not results.
_NON_RESULT_LINE = re.compile(
    r"\b(method|machine|instrument|analyzer|analyser|equipment|specimen|sample\s*id|"
    r"patient\s*id|lab\s*id|barcode|accession|mrn)\b|"
    r"\b(impaired|pre-?diabetes|diabetes mellitus|diagnostic|ada)\b|"
    r"\b(age/?sex|https?|www)\b|\d+\s*y\s*\d+\s*m",
    re.I,
)
_CALCULATED_GLUCOSE = re.compile(
    r"\b((?:average\s+)?estimated\s+average\s+glucose|average\s+estimated\s+glucose|calculated\s+glucose|eag)\b",
    re.I,
)
_FASTING_LINE = re.compile(r"\bfasting\b", re.I)
# Longer units first so "mg/dl" wins over "mg/d…" and "miu/ml" over "miu/l".
_UNITS = (
    "mg/dl", "mg/l", "g/dl", "g/l", "ng/ml", "ng/dl", "pg/ml", "µg/dl", "ug/dl", "µiu/ml", "uiu/ml",
    "miu/ml", "miu/l", "iu/ml", "iu/l", "u/l", "mmol/mol", "mmol/l", "µmol/l", "umol/l", "nmol/l",
    "pmol/l", "meq/l", "kua/l", "%",
)
_UNIT_CANON = {
    "mg/dl": "mg/dL", "mg/l": "mg/L", "g/dl": "g/dL", "g/l": "g/L", "ng/ml": "ng/mL", "ng/dl": "ng/dL",
    "pg/ml": "pg/mL", "µg/dl": "µg/dL", "ug/dl": "µg/dL", "µiu/ml": "µIU/mL", "uiu/ml": "µIU/mL",
    "miu/ml": "mIU/mL", "miu/l": "mIU/L", "iu/ml": "IU/mL", "iu/l": "IU/L", "u/l": "U/L",
    "mmol/mol": "mmol/mol", "mmol/l": "mmol/L", "µmol/l": "µmol/L", "umol/l": "µmol/L",
    "nmol/l": "nmol/L", "pmol/l": "pmol/L", "meq/l": "mEq/L", "kua/l": "kUA/L", "%": "%",
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
_RANGE_LINE = re.compile(rf"^\s*(?:reference(?:\s+range)?|ref\.?|range)?\s*:?\s*{_NUM}{_TO}{_NUM}(?:\s*[a-zA-Z/%µμ]+)?\s*$", re.I)
_LABELLED_RESULT = re.compile(rf"\b(?:result|value)\b\s*[:=]?\s*({_NUM})\b", re.I)
_LABELLED_UNIT = re.compile(r"\bunit\b\s*[:=]?\s*([a-zA-Z/%µμ0-9.]+)", re.I)
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
# Printed bands such as "High : >/=240" and "Borderline: 200-239" are not patient results.
_INTERPRETATION_LINE = re.compile(
    r"^\s*(?:desirable|borderline|very\s+high|high|optimal|near\b|low\s+risk|"
    r"mildly|moderately|severely|normal or high|stage\b)",
    re.I,
)
_INTERPRETATION_NUMBER = re.compile(
    r"\b(?:desirable|borderline|optimal|very\s+high|high|risk|stage)\b[^0-9]{0,16}$",
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
    measurement_kind: str = "measured"
    surface_name: str | None = None
    raw_value: str | None = None
    resolution_status: str = "verified"
    resolution_reason: str | None = None
    section: str | None = None
    specimen: str | None = None
    method: str | None = None
    temporal_scope: str = "current"


@dataclass(frozen=True)
class _Mention:
    start: int
    end: int
    key: str
    surface: str = ""
    measurement_kind: str = "measured"


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
    mentions = [
        _Mention(m.start(), m.end(), owners[m.group(1).lower()], surface=m.group(1))
        for m in pattern.finditer(text)
    ]
    return [_classify_mention(text, item) for item in mentions]


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
        if other.start > mention.start and other.start >= mention.end:
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


def _classify_mention(text: str, mention: _Mention) -> _Mention:
    """Keep fasting glucose and estimated glucose from collapsing into one measured glucose."""
    line_end = text.find("\n", mention.end)
    line = text[text.rfind("\n", 0, mention.start) + 1 : len(text) if line_end < 0 else line_end]
    window = text[max(0, mention.start - 48) : mention.end + 32]
    if mention.key in {"glucose", "fasting_blood_glucose"} and _CALCULATED_GLUCOSE.search(window):
        return _Mention(mention.start, mention.end, "glucose", mention.surface, "calculated")
    if mention.key == "glucose" and _FASTING_LINE.search(line):
        return _Mention(mention.start, mention.end, "fasting_blood_glucose", mention.surface, "measured")
    if mention.key == "creatinine" and re.search(r"\b(e-?gfr|gfr)\b", line, re.I):
        return _Mention(mention.start, mention.end, "", mention.surface, "rejected")
    if mention.key == "egfr" and re.search(r"\bcystatin\b", line, re.I):
        return _Mention(mention.start, mention.end, "egfr_cystatin", mention.surface, "calculated")
    if mention.key == "hdl" and re.search(r"non[-\s]*$", text[max(0, mention.start - 8) : mention.start], re.I):
        return _Mention(mention.start, mention.end, "", mention.surface, "rejected")
    return mention


def _usable_mention(text: str, mention: _Mention) -> bool:
    """Method lines and prose are not result rows, and must not end the previous row."""
    line = _line_containing(text, mention.start)
    if re.search(r"\b(method|machine|instrument|equation)\b", line, re.I):
        return False
    if len(line.split()) > 16 and not re.search(
        rf"{_NUM}\s*(?:mg/dl|g/dl|iu/ml|ng/ml|mmol/l|%)",
        line,
        re.I,
    ):
        return False
    return True


def _line_containing(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start : len(text) if end < 0 else end]


def _opens_range(text: str, match: re.Match[str]) -> bool:
    return bool(re.match(rf"\s*(?:-|–|—|to)\s*{_NUM}", text[match.end() :], re.I))


def _result_number(after: str) -> re.Match[str] | None:
    """First number that is a result, not a range edge, instrument id, or diagnostic band."""
    for match in _NUMBER.finditer(after):
        line = _line_containing(after, match.start())
        if _NON_RESULT_LINE.search(line) or _RANGE_LINE.match(line.strip()) or _INTERPRETATION_LINE.match(line.strip()):
            continue
        if _INTERPRETATION_NUMBER.search(line[: match.start()]):
            continue
        if re.search(r"\bid\b|\bno\s*:", line, re.I) and len(match.group(1).replace(".", "")) >= 6:
            continue
        prefix = after[max(0, match.start() - 8) : match.start()]
        if "\n" not in prefix and re.search(r"(?:au|dxc|im)\s*$", prefix, re.I):
            continue
        if _opens_range(after, match) and not match.group(2):
            continue
        if re.search(rf"{_NUM}\s*(?:-|–|—|to)\s*$", after[: match.start()]) and not match.group(2):
            continue
        if len(match.group(1).split(".")[0]) >= 6 and not match.group(2):
            continue
        if not match.group(2) and len(re.findall(r"[A-Za-z]{3,}", line)) > 3:
            continue
        return match
    return None


def extract_marker_from_text(text: str, marker_key: str, page: int | None = None) -> ExtractedValue | None:
    rows = [item for item in extract_known_observations(text, page) if item.parameter == marker_key and item.value is not None]
    if rows:
        return rows[0]
    return _unresolved_marker(text, marker_key, page)


def extract_known_observations(text: str, page: int | None = None) -> list[ExtractedValue]:
    """Every ontology row on the page, including repeats with different provenance."""
    if not text:
        return []
    mentions = [item for item in _mentions(text) if item.key and _usable_mention(text, item)]
    if not mentions:
        return []
    found: list[ExtractedValue] = []
    report_date = _find_date(text)
    date_kind = "collection_or_report" if _DATE.search(text) else None
    seen: set[tuple] = set()
    for mention in mentions:
        marker_key = mention.key
        name = display_name_for(marker_key) if marker_key else mention.surface
        line_start = text.rfind("\n", 0, mention.start) + 1
        row_end = _row_end(text, mention, mentions)
        row_text = text[_row_start(text, mention, mentions, line_start):row_end].strip()
        line_no = text.count("\n", 0, mention.start) + 1
        mention_line = text[line_start : text.find("\n", mention.end) if text.find("\n", mention.end) >= 0 else len(text)]
        if _SKIP.search(mention_line) or re.search(r"\bratio\b", mention_line, re.I):
            continue
        if re.search(r"\b(method|machine|instrument|equation)\b", mention_line, re.I):
            continue
        if re.search(r"\b(impaired|pre-?diabetes|diabetes)\b", mention_line, re.I):
            continue
        after = text[mention.end:row_end]
        match = _result_number(after)
        labelled = None
        if match is None:
            labelled = _LABELLED_RESULT.search(mention_line[: max(0, mention.start - line_start)])
            if labelled is None:
                continue
        if labelled is not None:
            raw_number = labelled.group(1)
            if raw_number not in mention_line:
                continue
            number = float(raw_number)
            unit_match = _LABELLED_UNIT.search(mention_line)
            unit = _UNIT_CANON.get(unit_match.group(1).lower()) if unit_match else None
            low = high = None
            ref_text = None
        else:
            raw_number = match.group(1)
            unit_raw = (match.group(2) or "").lower()
            unit = _UNIT_CANON.get(unit_raw) if unit_raw else None
            line_end = after.find("\n", match.end())
            same_line = after[match.end() : len(after) if line_end < 0 else line_end]
            low, high, ref_text = _reference(same_line)
            number = float(raw_number)
            if _opens_range(after, match) and not unit:
                continue
            if raw_number not in row_text:
                continue
        signature = (marker_key, raw_number, line_no, mention.measurement_kind)
        if signature in seen:
            continue
        seen.add(signature)
        found.append(
            ExtractedValue(
                parameter=marker_key,
                name=mention.surface or name,
                value=number,
                unit=unit,
                source_text=row_text[:240],
                page=page,
                date=_date_before(text, mention.start) or report_date,
                date_kind=date_kind,
                reference_low=low,
                reference_high=high,
                confidence="high" if unit or mention.measurement_kind == "calculated" else "low",
                reference_text=ref_text,
                line=line_no,
                measurement_kind=mention.measurement_kind,
                surface_name=mention.surface or None,
                raw_value=raw_number,
                resolution_status="verified",
                resolution_reason="ontology_row",
                section=_section_for(text, line_start, mention_line),
                method=_labelled_before(text, line_start, "method"),
                specimen=_labelled_before(text, line_start, "specimen"),
                temporal_scope="historical" if _HISTORICAL.search(mention_line) else "current",
            )
        )
    return found


def _unresolved_marker(text: str, marker_key: str, page: int | None) -> ExtractedValue | None:
    return None


_CANDIDATE_LINE = re.compile(
    rf"^(?P<name>[A-Za-z][A-Za-z0-9][A-Za-z0-9 /()+.,\-]{{1,70}}?)\s+(?P<num>{_NUM})(?:\s*(?P<unit>[A-Za-zµμ/%][A-Za-z0-9µμ/%.-]*))?",
)
_NOT_A_NAME = re.compile(
    r"^(reference|ref|result|value|unit|test|page|date|collection|patient|sample|method|machine|normal|comment|note)s?$",
    re.I,
)


def extract_unknown_observations(text: str, page: int | None = None) -> list[ExtractedValue]:
    """Table-like rows whose printed name is not in the ontology. Not verified facts."""
    if not text:
        return []
    known_lines = {item.line for item in extract_known_observations(text, page)}
    found: list[ExtractedValue] = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        if index in known_lines:
            continue
        line = raw_line.strip()
        if not line or _NON_RESULT_LINE.search(line) or _RANGE_LINE.match(line) or _DATE.search(line):
            continue
        if len(re.findall(r"[A-Za-z]{2,}", line)) > 10:
            continue
        match = _CANDIDATE_LINE.match(line)
        if not match:
            continue
        name = match.group("name").strip(" .:-")
        if len(name) < 3 or _NOT_A_NAME.match(name) or _mentions(name):
            continue
        unit_raw = (match.group("unit") or "").lower()
        unit = _UNIT_CANON.get(unit_raw)
        if unit is None and unit_raw:
            continue
        if unit is None:
            continue
        number = match.group("num")
        if number not in line:
            continue
        low, high, ref_text = _reference(line[match.end("num"):])
        found.append(
            ExtractedValue(
                parameter="unresolved",
                name=name,
                value=float(number),
                unit=unit,
                source_text=line[:240],
                page=page,
                date=_date_before(text, text.find(line)),
                date_kind=None,
                reference_low=low,
                reference_high=high,
                confidence="low",
                reference_text=ref_text,
                line=index,
                measurement_kind="measured",
                surface_name=name,
                raw_value=number,
                resolution_status="unresolved",
                resolution_reason="name_not_in_ontology",
                section=_section_before(text, text.find(line)),
            )
        )
    return found


def _date_before(text: str, index: int) -> date | None:
    found = None
    for match in _DATE.finditer(text[: max(0, index)]):
        found = _parse_date(match.group(1))
    return found


_PANEL_HEADING = re.compile(
    r"\b(function|profile|panel|studies|count|gfr|cystatin|kft|lft|lipid|thyroid|allergy|iron)\b",
    re.I,
)


def _section_for(text: str, index: int, mention_line: str) -> str | None:
    """A panel name on the result's own line is the section. Otherwise use the heading above."""
    current = (mention_line or "").strip()
    letters = [ch for ch in current if ch.isalpha()]
    caps = bool(letters) and sum(ch.isupper() for ch in letters) >= 0.7 * len(letters)
    if current and len(current) <= 80 and not _NUMBER.search(current) and (caps or _PANEL_HEADING.search(current)):
        return current[:80]
    return _section_before(text, index)


def _section_before(text: str, index: int) -> str | None:
    """Last panel heading before this row, not the method or specimen line above it."""
    section = ""
    for line in text[: max(0, index)].splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 80 or _NUMBER.search(stripped):
            continue
        if re.match(r"^(method|specimen|sample|machine|instrument|unit|result|comment)\b", stripped, re.I):
            continue
        letters = [ch for ch in stripped if ch.isalpha()]
        caps = bool(letters) and sum(ch.isupper() for ch in letters) >= 0.7 * len(letters)
        if caps or _PANEL_HEADING.search(stripped):
            section = stripped
    return section[:80] or None


def _labelled_before(text: str, index: int, label: str) -> str | None:
    pattern = re.compile(rf"\b{label}\b\s*:\s*(.+)", re.I)
    found = None
    window = text[max(0, index - 400): index]
    for match in pattern.finditer(window):
        found = match.group(1).strip()[:80]
    return found


def _parse_date(raw: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_date(raw: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


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
