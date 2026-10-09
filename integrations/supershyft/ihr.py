"""Controlled IHR reads. One parameterized SELECT per user; never LLM-generated SQL."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from datetime import date

from sqlalchemy import text

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.core.errors import ProviderUnavailableError
from app.pipeline.lab_parameters import related_keys, distinct_neighbours
from app.pipeline.ontology import retrieval_metric_keys
from app.pipeline.personal_selection import retain_blood_reports
from integrations.supershyft.db import DB_QUERY_FAILED, run_readonly
from integrations.supershyft.mapping import _as_date, bio_ai_from_row, blood_report_from_row

logger = logging.getLogger("cura.integrations.supershyft")


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

_IHR_SELECT = text(
    """
    SELECT report_id, user_id, assessment_instance_id, engagement_id, reports, created_at, report_url
    FROM individual_health_report
    WHERE user_id = :uid
    ORDER BY created_at ASC NULLS FIRST, report_id ASC
    """
)

_cache: dict[int, tuple[float, list[dict]]] = {}


def fetch_ihr_rows(principal: AuthenticatedPrincipal) -> list[dict]:
    uid = _user_id(principal)
    now = time.monotonic()
    hit = _cache.get(uid)
    if hit and now - hit[0] < 2.0:
        return hit[1]
    rows = run_readonly(_IHR_SELECT, {"uid": uid}) or []
    _cache[uid] = (now, rows)
    return rows


def reset_ihr_cache() -> None:
    _cache.clear()
    from integrations.supershyft.blood import reset_blood_cache

    reset_blood_cache()


@dataclass
class IhrBundle:
    user_id: int
    blood_reports: list[BloodReport] = field(default_factory=list)
    bio_ai_reports: list[BioAIReport] = field(default_factory=list)
    report_ids: list[str] = field(default_factory=list)


class IhrRepository:
    """Read-only IHR access scoped to the authenticated SuperShyft user_id."""

    def get_latest_ihr_report(self, principal: AuthenticatedPrincipal) -> IhrBundle:
        plan = QueryPlan(
            intent=IntentType.latest_result,
            needs_blood=True,
            needs_bio_ai=True,
            history=False,
        )
        return self.get_ihr_data_for_query(principal, plan)

    def get_ihr_report_history(self, principal: AuthenticatedPrincipal) -> IhrBundle:
        plan = QueryPlan(intent=IntentType.trend, history=True, needs_blood=True, needs_bio_ai=True)
        return self.get_ihr_data_for_query(principal, plan)

    def get_ihr_data_for_query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> IhrBundle:
        uid = _user_id(principal)
        rows = _sorted_ihr_rows(fetch_ihr_rows(principal))
        started = time.perf_counter()
        uid = _user_id(principal)
        rows = _sorted_ihr_rows(fetch_ihr_rows(principal))
        blood: list[BloodReport] = []
        bio: list[BioAIReport] = []
        ids: list[str] = []
        for raw in rows:
            raw_uid = raw.get("user_id")
            if raw_uid is None or int(raw_uid) != uid:
                continue
            rid = str(raw.get("report_id") or "")
            if rid:
                ids.append(rid)
            mapped_blood = blood_report_from_row(_Row(raw))
            if mapped_blood:
                blood.append(mapped_blood)
            mapped_bio = bio_ai_from_row(_Row(raw))
            if mapped_bio:
                bio.append(mapped_bio)
        from integrations.supershyft.blood import mapped_booking_reports

        booking_blood = mapped_booking_reports(principal) if plan.needs_blood else []
        blood = _merge_blood_reports(blood, booking_blood)
        ids.extend(report.report_id for report in booking_blood if report.report_id)
        if plan.report_id:
            blood = [r for r in blood if r.report_id == plan.report_id]
            bio = [
                r
                for r in bio
                if r.report_id == plan.report_id or r.report_id == f"bioai-{plan.report_id}"
            ]
        wanted_keys = retrieval_metric_keys(plan) if plan.needs_blood else []
        if wanted_keys:
            wanted = set(wanted_keys)
            for key in wanted_keys:
                wanted |= related_keys(key) | distinct_neighbours(key)
            if plan.topic in {"ldl", "hdl", "cholesterol", "triglycerides"} or any(
                key in {"ldl", "hdl", "cholesterol", "triglycerides"} for key in wanted_keys
            ):
                wanted |= {"ldl", "hdl", "cholesterol", "triglycerides"}
            blood = retain_blood_reports(blood, wanted)
        keep_blood_history = bool(
            plan.history
            or plan.time_operation in {"latest_marker", "trend", "previous", "compare"}
        )
        if plan.time_operation == "latest_report" and blood:
            blood = blood[-1:]
        elif not keep_blood_history and blood:
            blood = blood[-1:]
        if plan.time_operation == "latest_report" and bio:
            bio = bio[-1:]
        elif not plan.history and plan.intent.value != "bio_ai_comparison" and bio and plan.intent.value != "bio_ai_explanation":
            if plan.intent.value == "bio_ai_score":
                pass
            elif bio:
                bio = bio[-1:]
        _log_retrieval(uid, len(rows), blood, bio, started)
        return IhrBundle(user_id=uid, blood_reports=blood, bio_ai_reports=bio, report_ids=ids)


def _log_retrieval(uid: int, ihr_rows: int, blood: list[BloodReport], bio: list[BioAIReport], started: float) -> None:
    from app.core.config import settings

    if settings.app_env != "development":
        return
    import hashlib

    member_ref = hashlib.sha256(str(uid).encode()).hexdigest()[:10]
    database = ""
    url = settings.supershyft_database_url or ""
    if "/" in url:
        database = url.rsplit("/", 1)[-1].split("?", 1)[0]
    logger.info(
        "ihr_retrieval member_ref=%s database=%s ihr_rows=%s blood_reports=%s markers=%s bio_reports=%s risks=%s duration_ms=%s",
        member_ref,
        database,
        ihr_rows,
        len(blood),
        sum(len(report.markers) for report in blood),
        len(bio),
        sum(len(report.risks) for report in bio),
        int((time.perf_counter() - started) * 1000),
    )


def _merge_blood_reports(ihr_blood: list[BloodReport], booking_blood: list[BloodReport]) -> list[BloodReport]:
    by_id: dict[str, BloodReport] = {}
    for report in ihr_blood + booking_blood:
        if report.report_id not in by_id:
            by_id[report.report_id] = report
    return sorted(by_id.values(), key=lambda report: (report.report_date, report.report_id))


def _sorted_ihr_rows(rows: list[dict]) -> list[dict]:
    def sort_key(raw: dict):
        created = raw.get("created_at")
        if not created:
            reports = raw.get("reports")
            if isinstance(reports, dict):
                created = reports.get("created_at")
        try:
            when = _as_date(created) if created else date.min
        except Exception:
            when = date.min
        return (when, str(raw.get("report_id") or ""))

    return sorted(rows, key=sort_key)
