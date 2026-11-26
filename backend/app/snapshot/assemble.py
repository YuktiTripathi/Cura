"""Build one MemberSnapshot from provider DTOs. No model calls."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.auth.models import AuthenticatedPrincipal
from app.biomarkers.health_categories import REGISTRY_VERSION
from app.biomarkers.overview import build_body_system_overview
from app.biomarkers.risk_overview import build_risk_overview
from app.biomarkers.unified_overview import build_category_detail, build_unified_overview, gather
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.member_snapshot import HealthView, MemberSnapshot, ReportRef, SourceAvailability
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.core.errors import ProviderUnavailableError
from app.providers.registry import ProviderRegistry
from app.biomarkers.medical_registry import related_ids

logger = logging.getLogger("cura.snapshot")

exploration_llm_calls = 0


def _plan(intent: IntentType, **flags) -> QueryPlan:
    return QueryPlan(intent=intent, knowledge_scope=KnowledgeScope.personal, history=True, **flags)


def _call(name: str, fn, counts: dict[str, int]):
    counts[name] = counts.get(name, 0) + 1
    try:
        return fn(), None
    except ProviderUnavailableError:
        logger.warning("snapshot_provider status=unavailable source=%s", name)
        return None, "unavailable"
    except Exception:
        logger.warning("snapshot_provider status=failed source=%s", name, exc_info=True)
        return None, "unavailable"


def _order_reports(reports: list) -> list:
    """Keep every report identity. Same-day reports are not merged."""
    return sorted(reports, key=lambda report: (report.report_date, str(report.report_id)))


def _ref(report) -> ReportRef | None:
    if report is None:
        return None
    day = getattr(report, "report_date", None)
    return ReportRef(report_id=str(report.report_id), report_date=day.isoformat() if day else None)


def _availability(value, error: str | None) -> str:
    if error:
        return "unavailable"
    if value is None or value == [] or value is False:
        return "empty"
    return "ready"


def assemble_snapshot(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> MemberSnapshot:
    if exploration_llm_calls != 0:
        logger.warning("snapshot_llm_count=%s", exploration_llm_calls)
    counts: dict[str, int] = {}
    blood_plan = _plan(IntentType.latest_result, needs_blood=True)
    bio_plan = _plan(IntentType.bio_ai_score, needs_bio_ai=True)
    life_plan = _plan(IntentType.latest_result, needs_lifestyle=True)
    q_plan = _plan(IntentType.latest_result, needs_questionnaire=True)

    jobs = {
        "blood": lambda: registry.blood.query(principal, blood_plan) or [],
        "bio_ai": lambda: registry.bio_ai.query(principal, bio_plan) or [],
        "lifestyle": lambda: registry.lifestyle.query(principal, life_plan),
        "questionnaire": lambda: registry.questionnaires.query(principal, q_plan) or [],
        "profile": lambda: registry.users.get_profile(principal),
    }
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {name: pool.submit(_call, name, fn, counts) for name, fn in jobs.items()}
        results = {name: future.result() for name, future in futures.items()}

    blood_rows, blood_err = results["blood"]
    bio_rows, bio_err = results["bio_ai"]
    lifestyle, life_err = results["lifestyle"]
    questionnaires, q_err = results["questionnaire"]
    profile, profile_err = results["profile"]

    blood_rows = list(blood_rows or [])
    bio_rows = list(bio_rows or [])
    ordered_blood = _order_reports(blood_rows)
    ordered_bio = _order_reports(bio_rows)
    latest_blood = ordered_blood[-1] if ordered_blood else None
    previous_blood = ordered_blood[-2] if len(ordered_blood) > 1 else None
    latest_bio = ordered_bio[-1] if ordered_bio else None
    previous_bio = ordered_bio[-2] if len(ordered_bio) > 1 else None

    blood_view = build_body_system_overview(blood_rows) if blood_rows else None
    bio_view = build_risk_overview(bio_rows) if bio_rows else None
    overview = build_unified_overview(blood_view, bio_view, None)
    categories = {}
    findings = {}
    for card in overview.categories or []:
        detail = build_category_detail(card.id, blood_view, bio_view)
        if detail is None:
            continue
        detail.story = None
        categories[card.id] = detail
        for finding in detail.findings or []:
            if finding.source_type == "measured":
                from app.biomarkers.education import education_for

                key = finding.id.split(":", 1)[-1]
                note = education_for(key, finding.medical_name, finding.name)
                if note is not None:
                    finding.education = note
            elif finding.source_type == "predicted_risk":
                from app.biomarkers.education_notes import risk_note

                note = risk_note(finding.id.split(":", 1)[-1])
                if note is not None:
                    finding.education = note
            findings[finding.id] = finding

    marker_keys = [marker.key for report in blood_rows for marker in report.markers or [] if marker.key]
    related: dict[str, list[str]] = {}
    present = set(marker_keys)
    for finding in findings.values():
        if finding.source_type != "measured":
            continue
        key = finding.id.split(":", 1)[-1]
        extras = [item for item in related_ids(key, present) if item != key]
        if extras:
            related[finding.id] = extras[:8]

    availability = SourceAvailability(
        blood=_availability(blood_rows, blood_err),
        bio_ai=_availability(bio_rows, bio_err),
        lifestyle=_availability(lifestyle, life_err),
        questionnaire=_availability(questionnaires, q_err),
        profile=_availability(profile, profile_err),
    )
    failed = [name for name, (_, err) in results.items() if err]
    succeeded = [name for name, (value, err) in results.items() if not err]
    if not succeeded:
        state = "unavailable"
    elif failed:
        state = "partial"
    else:
        state = "ready"

    source_ids = [report.report_id for report in ordered_blood + ordered_bio]
    fingerprint = hashlib.sha256("|".join(source_ids).encode()).hexdigest()[:16]
    version = f"{settings.member_snapshot_schema_version}.{REGISTRY_VERSION}.{fingerprint}"
    metabolic = None
    if isinstance(latest_bio, BioAIReport):
        metabolic = latest_bio.metabolic_age
    display = None
    if profile is not None and not profile_err:
        display = getattr(profile, "display_name", None) or None

    logger.info(
        "snapshot_assembled state=%s provider_calls=%s sources=%s",
        state,
        sum(counts.values()),
        len(source_ids),
    )
    return MemberSnapshot(
        schema_version=settings.member_snapshot_schema_version,
        registry_version=REGISTRY_VERSION,
        snapshot_version=version,
        built_at=datetime.now(timezone.utc),
        state=state,
        availability=availability,
        profile_display_name=display,
        latest_blood=_ref(latest_blood) if isinstance(latest_blood, BloodReport) else None,
        previous_blood=_ref(previous_blood) if isinstance(previous_blood, BloodReport) else None,
        latest_bio_ai=_ref(latest_bio) if isinstance(latest_bio, BioAIReport) else None,
        previous_bio_ai=_ref(previous_bio) if isinstance(previous_bio, BioAIReport) else None,
        metabolic_age=metabolic,
        metabolic_age_insight=_metabolic_insight(profile, profile_err, latest_bio, metabolic),
        source_ids=source_ids,
        overview=overview,
        categories=categories,
        findings=findings,
        related_keys=related,
        questionnaire_count=len(questionnaires or []),
        lifestyle_present=lifestyle is not None and not life_err,
    )


def _metabolic_insight(profile, profile_err, latest_bio, metabolic):
    from app.biomarkers.metabolic_age_insight import build_metabolic_age_insight

    if profile is None or profile_err or not isinstance(latest_bio, BioAIReport):
        return None
    return build_metabolic_age_insight(
        actual_age=getattr(profile, "age", None),
        metabolic_age=metabolic,
        assessed_on=latest_bio.report_date,
    )


def to_health_view(snapshot: MemberSnapshot) -> HealthView:
    from app.biomarkers.medical_registry import related_ids

    measured = sum(1 for finding in snapshot.findings.values() if finding.source_type == "measured")
    risks = sum(1 for finding in snapshot.findings.values() if finding.source_type == "predicted_risk")
    questions = {key: list(detail.follow_ups or []) for key, detail in snapshot.categories.items()}
    present = set(snapshot.findings)
    related = {key: list(values) for key, values in snapshot.related_keys.items()}
    for key in present:
        extra = [item for item in related_ids(key, present) if item not in related.get(key, [])]
        if extra:
            related[key] = [*related.get(key, []), *extra]
    return HealthView(
        state=snapshot.state,
        snapshot_version=snapshot.snapshot_version,
        schema_version=snapshot.schema_version,
        registry_version=snapshot.registry_version,
        built_at=snapshot.built_at,
        availability=snapshot.availability,
        display_name=snapshot.profile_display_name,
        latest_blood_date=snapshot.latest_blood.report_date if snapshot.latest_blood else None,
        previous_blood_date=snapshot.previous_blood.report_date if snapshot.previous_blood else None,
        latest_bio_ai_date=snapshot.latest_bio_ai.report_date if snapshot.latest_bio_ai else None,
        previous_bio_ai_date=snapshot.previous_bio_ai.report_date if snapshot.previous_bio_ai else None,
        metabolic_age=snapshot.metabolic_age,
        metabolic_age_insight=snapshot.metabolic_age_insight,
        measured_count=measured,
        risk_count=risks,
        overview=snapshot.overview,
        categories=snapshot.categories,
        findings=snapshot.findings,
        related_keys=related,
        suggested_questions=questions,
    )


def slice_category(snapshot: MemberSnapshot, category_id: str):
    return snapshot.categories.get(category_id)


def slice_finding(snapshot: MemberSnapshot, finding_id: str):
    return snapshot.findings.get(finding_id)
