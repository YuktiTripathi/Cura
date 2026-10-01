"""Read-only SuperShyft blood reports from participant_blood_bookings. Always scoped to user_id."""

from __future__ import annotations

import time
from datetime import date

from sqlalchemy import text

from app.auth.models import AuthenticatedPrincipal
from app.contracts.blood import BloodReport
from app.core.config import settings
from app.core.errors import ProviderUnavailableError
from integrations.supershyft.db import DB_QUERY_FAILED, run_readonly
from integrations.supershyft.mapping import blood_report_from_booking_row

_BLOOD_SELECT = text(
    """
    SELECT
        pbb.id,
        pbb.engagement_participant_id,
        pbb.collection_date,
        pbb.collected_at,
        pbb.status,
        pbb.diagnostic_report_url,
        pbb.blood_parameters,
        pbb.blood_report_raw,
        pbb.created_at,
        ep.engagement_id,
        ep.user_id
    FROM participant_blood_bookings pbb
    JOIN engagement_participants ep
      ON ep.engagement_participant_id = pbb.engagement_participant_id
    WHERE ep.user_id = :uid
    ORDER BY pbb.collection_date ASC NULLS LAST, pbb.id ASC
    """
)

_cache: dict[int, tuple[float, list[dict]]] = {}


def _user_id(principal: AuthenticatedPrincipal) -> int:
    try:
        return int(str(principal.subject_id).strip())
    except (TypeError, ValueError) as exc:
        raise ProviderUnavailableError(
            "SuperShyft health reads require the authenticated token subject to be the numeric SuperShyft user_id",
            reason=DB_QUERY_FAILED,
        ) from exc


class _Row:
    def __init__(self, mapping: dict):
        self.__dict__.update(mapping)


def fetch_blood_booking_rows(principal: AuthenticatedPrincipal) -> list[dict]:
    if not (settings.supershyft_database_url or "").strip():
        return []
    uid = _user_id(principal)
    now = time.monotonic()
    hit = _cache.get(uid)
    if hit and now - hit[0] < 2.0:
        return hit[1]
    rows = run_readonly(_BLOOD_SELECT, {"uid": uid}) or []
    _cache[uid] = (now, rows)
    return rows


def reset_blood_cache() -> None:
    _cache.clear()


def mapped_booking_reports(principal: AuthenticatedPrincipal) -> list[BloodReport]:
    uid = _user_id(principal)
    reports: list[BloodReport] = []
    for raw in fetch_blood_booking_rows(principal):
        raw_uid = raw.get("user_id")
        if raw_uid is None or int(raw_uid) != uid:
            continue
        mapped = blood_report_from_booking_row(_Row(raw))
        if mapped:
            reports.append(mapped)
    reports.sort(key=lambda report: (report.report_date or date.min, report.report_id))
    return reports
