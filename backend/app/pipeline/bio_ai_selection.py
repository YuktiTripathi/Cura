"""Select a single authorized Bio-AI report. Never merge two reports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.contracts.bio_ai import BioAIReport
from app.contracts.query import QueryPlan

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_ISO_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_NAMED_DATE = re.compile(
    r"\b("
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(20\d{2}))?\b",
    re.I,
)
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r")(?:,?\s*(20\d{2}))?\b",
    re.I,
)


@dataclass
class BioAIReportChoice:
    report: BioAIReport | None = None
    ambiguous: list[BioAIReport] = field(default_factory=list)
    reason: str = "none"


def report_stamp(report: BioAIReport) -> datetime:
    value = getattr(report, "completed_at", None) or report.report_date
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.min


def requested_dates(message: str) -> list[date]:
    found: list[date] = []
    for match in _ISO_DATE.finditer(message or ""):
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if day not in found:
            found.append(day)
    return found


def requested_blood_dates(message: str) -> list[date]:
    """Dates that name a blood report. A Bio-AI date in the same sentence is left out."""
    text = message or ""
    dates = requested_dates(text)
    if re.search(r"bio-?\s*ai", text, re.I) and re.search(r"\bblood\b", text, re.I):
        bio_day = requested_report_date(text)
        kept = [day for day in dates if day != bio_day]
        return kept or dates
    return dates


def requested_report_date(message: str) -> date | None:
    text = message or ""
    bio = re.search(r"bio-?\s*ai", text, re.I)
    if bio:
        after = _ISO_DATE.search(text[bio.end() :])
        before = list(_ISO_DATE.finditer(text[: bio.start()]))
        token = after.group(1) if after else (before[-1].group(1) if before else None)
        if token:
            try:
                return date.fromisoformat(token)
            except ValueError:
                pass
    iso = _ISO_DATE.search(text)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            pass
    named = _NAMED_DATE.search(text)
    if named:
        month = _MONTHS.get(named.group(1).lower())
        day = int(named.group(2))
        year = int(named.group(3)) if named.group(3) else None
        if month:
            return _safe_date(year, month, day)
    day_month = _DAY_MONTH.search(text)
    if day_month:
        day = int(day_month.group(1))
        month = _MONTHS.get(day_month.group(2).lower())
        year = int(day_month.group(3)) if day_month.group(3) else None
        if month:
            return _safe_date(year, month, day)
    return None


def _safe_date(year: int | None, month: int, day: int) -> date | None:
    try:
        return date(year or 1900, month, day)
    except ValueError:
        return None


def _match_requested_date(reports: list[BioAIReport], wanted: date) -> list[BioAIReport]:
    if wanted.year == 1900:
        return [item for item in reports if item.report_date.month == wanted.month and item.report_date.day == wanted.day]
    return [item for item in reports if item.report_date == wanted]


def select_bio_ai_report(
    reports: list[BioAIReport],
    plan: QueryPlan,
    *,
    message: str = "",
    conversation_report_id: str | None = None,
) -> BioAIReportChoice:
    owned = [item for item in reports if item]
    if not owned:
        return BioAIReportChoice(reason="no_reports")
    if len(owned) == 1:
        return BioAIReportChoice(report=owned[0], reason="single")

    text = (message or plan.raw_message or "").lower()
    explicit_ids = [
        item
        for item in owned
        if item.report_id and item.report_id.lower() in text
    ]
    if len(explicit_ids) == 1:
        return BioAIReportChoice(report=explicit_ids[0], reason="explicit_report_id")

    if plan.report_id:
        matched = [
            item
            for item in owned
            if item.report_id == plan.report_id or item.report_id == f"bioai-{plan.report_id}"
        ]
        if len(matched) == 1:
            return BioAIReportChoice(report=matched[0], reason="plan_report_id")

    wanted_date = requested_report_date(message or plan.raw_message or "")
    if wanted_date:
        dated = _match_requested_date(owned, wanted_date)
        if len(dated) == 1:
            return BioAIReportChoice(report=dated[0], reason="explicit_date")
        if len(dated) > 1:
            return _latest_or_ambiguous(dated, reason_prefix="explicit_date")

    if conversation_report_id:
        matched = [
            item
            for item in owned
            if item.report_id == conversation_report_id
            or item.report_id == f"bioai-{conversation_report_id}"
        ]
        if len(matched) == 1:
            return BioAIReportChoice(report=matched[0], reason="conversation_report")

    if "advanced" in text:
        advanced = [item for item in owned if item.source_line == "advanced_bio_ai"]
        if len(advanced) == 1:
            return BioAIReportChoice(report=advanced[0], reason="explicit_source_line")
        if len(advanced) > 1:
            return _latest_or_ambiguous(advanced, reason_prefix="explicit_source_line")

    return _latest_or_ambiguous(owned, reason_prefix="latest")


def _latest_or_ambiguous(reports: list[BioAIReport], *, reason_prefix: str) -> BioAIReportChoice:
    ordered = sorted(reports, key=lambda item: (report_stamp(item), item.report_id))
    latest = ordered[-1]
    latest_stamp = report_stamp(latest)
    tied = [item for item in ordered if report_stamp(item) == latest_stamp]
    if len(tied) == 1:
        return BioAIReportChoice(report=tied[0], reason=f"{reason_prefix}_unique")
    return BioAIReportChoice(ambiguous=tied, reason=f"{reason_prefix}_ambiguous")
