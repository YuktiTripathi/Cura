from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope, MarkerFlag
from app.contracts.query import QueryPlan
from app.contracts.snapshot import PersonalHealthSnapshot, SnapshotReport
from app.core.errors import ProviderUnavailableError
from app.db.goal_store import GoalStore
from app.documents.service import DocumentService
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.health_timeline import build_health_timeline
from app.pipeline.insight_candidates import build_insight_candidates
from app.pipeline.personal_profile import build_personal_profile
from app.pipeline.trend_engine import comparison
from app.providers.registry import ProviderRegistry


def build_personal_health_snapshot(
    principal: AuthenticatedPrincipal,
    registry: ProviderRegistry,
    *,
    db: Session | None = None,
) -> PersonalHealthSnapshot:
    snap = PersonalHealthSnapshot(subject_id=principal.subject_id, available=True)
    blood_plan = QueryPlan(
        intent=IntentType.latest_result,
        needs_blood=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    bio_plan = QueryPlan(
        intent=IntentType.bio_ai_score,
        needs_bio_ai=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    life_plan = QueryPlan(
        intent=IntentType.personal_profile,
        needs_lifestyle=True,
        needs_profile=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    try:
        reports = registry.blood.query(principal, blood_plan) or []
    except ProviderUnavailableError:
        reports = []
        snap.available = False
        snap.missing.append("blood_reports")
    except Exception:
        reports = []
        snap.missing.append("blood_reports")
    try:
        bio = registry.bio_ai.query(principal, bio_plan) or []
    except ProviderUnavailableError:
        bio = []
        if not reports:
            snap.available = False
        snap.missing.append("bio_ai_reports")
    except Exception:
        bio = []
    try:
        life = registry.lifestyle.query(principal, life_plan)
    except Exception:
        life = None
    try:
        user = registry.users.get_profile(principal)
    except Exception:
        from app.contracts.user import UserProfile

        user = UserProfile(subject_id=principal.subject_id, display_name="")

    ordered = sorted(reports, key=lambda r: (r.report_date, r.report_id))
    if ordered:
        latest = ordered[-1]
        snap.latest_biomarkers = [m for m in latest.markers if m.value is not None]
        snap.recent_reports.append(
            SnapshotReport(
                report_id=latest.report_id,
                report_date=str(latest.report_date),
                source="SuperShyft",
                title="Latest blood report",
            )
        )
        if len(ordered) >= 2:
            previous = ordered[-2]
            keys = {m.key for m in latest.markers} & {m.key for m in previous.markers}
            for key in sorted(keys):
                prev_m = next((m for m in previous.markers if m.key == key), None)
                curr_m = next((m for m in latest.markers if m.key == key), None)
                if prev_m is None or curr_m is None:
                    continue
                if prev_m.value is None or curr_m.value is None:
                    continue
                row = comparison(
                    key,
                    prev_m.value,
                    curr_m.value,
                    previous.report_id,
                    latest.report_id,
                    previous.report_date,
                    latest.report_date,
                )
                snap.recent_changes.append(row)
                if curr_m.flag in {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical} or row.direction in {
                    "increased",
                    "decreased",
                }:
                    snap.notable_trends.append(row)
    if bio:
        latest_bio = sorted(bio, key=lambda r: (r.report_date, r.report_id))[-1]
        snap.bio_ai_scores = list(latest_bio.risks or [])
        snap.recent_reports.append(
            SnapshotReport(
                report_id=latest_bio.report_id,
                report_date=str(latest_bio.report_date),
                source="SuperShyft",
                title="Latest Bio-AI report",
            )
        )

    goals = []
    user_facts = []
    documents = []
    if db is not None:
        store = GoalStore(db)
        goals = store.list_for_subject(principal.subject_id)
        user_facts = store.provided_facts(principal.subject_id)
        try:
            documents = DocumentService(db).list_for_user(principal.subject_id)
        except Exception:
            documents = []
    snap.health_goals = goals
    snap.goal_progress = compute_goal_progress(goals, ordered)
    snap.profile = build_personal_profile(
        user=user,
        lifestyle=life,
        bio_risks=snap.bio_ai_scores,
        goals=goals,
        user_facts=user_facts,
    )
    snap.timeline = build_health_timeline(
        subject_id=principal.subject_id,
        blood_reports=ordered,
        bio_reports=bio,
        documents=documents,
    )
    snap.insight_candidates = build_insight_candidates(
        changes=snap.recent_changes,
        missing=snap.profile.missing,
    )
    if not ordered and not bio:
        snap.missing.append("personal_records")
    return snap
