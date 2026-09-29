from __future__ import annotations

from sqlalchemy import text

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.lifestyle import LifestyleContext
from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from app.core.errors import ProviderUnavailableError
from app.pipeline.lab_parameters import related_keys
from app.pipeline.ontology import retrieval_metric_keys
from integrations.supershyft.db import run_readonly
from integrations.supershyft.ihr import _Row, _user_id, fetch_ihr_rows
from integrations.supershyft.mapping import bio_ai_from_row, blood_report_from_row


class SuperShyftUserProvider:
    def get_profile(self, principal: AuthenticatedPrincipal) -> UserProfile:
        uid = _user_id(principal)
        row = run_readonly(
            text("SELECT user_id, first_name, last_name, age, gender FROM users WHERE user_id = :uid"),
            {"uid": uid},
            fetch="one",
        )
        if not row:
            return UserProfile(subject_id=str(uid), display_name="", first_name=None, last_name=None)
        first = (row.get("first_name") or "").strip() or None
        last = (row.get("last_name") or "").strip() or None
        age = row.get("age")
        band = None
        if isinstance(age, int):
            band = f"{(age // 10) * 10}s"
        return UserProfile(
            subject_id=str(uid),
            display_name=first or "",
            first_name=first,
            last_name=last,
            age_band=band,
            sex=row.get("gender"),
        )

    def available_topics(self, principal: AuthenticatedPrincipal) -> list[str]:
        reports = SuperShyftBloodProvider().query(
            principal,
            QueryPlan(intent=IntentType.latest_result, needs_blood=True, history=True),
        )
        keys: list[str] = []
        for report in reports:
            for marker in report.markers:
                if marker.key not in keys:
                    keys.append(marker.key)
        return keys[:12]


class SuperShyftBloodProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BloodReport]:
        _user_id(principal)
        rows = fetch_ihr_rows(principal)
        reports: list[BloodReport] = []
        for raw in rows:
            mapped = blood_report_from_row(_Row(raw))
            if mapped:
                reports.append(mapped)
        if plan.report_id:
            reports = [report for report in reports if report.report_id == plan.report_id]
        wanted_keys = retrieval_metric_keys(plan)
        if wanted_keys:
            wanted = set(wanted_keys)
            for key in wanted_keys:
                wanted |= related_keys(key)
            filtered = []
            for report in reports:
                markers = [m for m in report.markers if m.key in wanted]
                if markers:
                    if "fasting_blood_glucose" in {m.key for m in markers} and (
                        plan.topic in {"glucose", "fasting_blood_glucose"}
                        or "fasting_blood_glucose" in wanted_keys
                        or "glucose" in wanted_keys
                    ):
                        markers = sorted(
                            markers,
                            key=lambda m: 0 if m.key == "fasting_blood_glucose" else 1,
                        )
                    filtered.append(report.model_copy(update={"markers": markers}))
            reports = filtered
        if plan.time_operation == "latest_report" and reports:
            return reports[-1:]
        if plan.history or plan.time_operation in {"latest_marker", "trend", "previous", "compare"}:
            return reports
        if reports:
            return reports[-1:]
        return reports


class SuperShyftBioAIProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BioAIReport]:
        _user_id(principal)
        rows = fetch_ihr_rows(principal)
        reports: list[BioAIReport] = []
        for raw in rows:
            mapped = bio_ai_from_row(_Row(raw))
            if mapped:
                reports.append(mapped)
        if plan.report_id:
            reports = [
                report
                for report in reports
                if report.report_id == plan.report_id
                or report.report_id == f"bioai-{plan.report_id}"
            ]
        return reports


class SuperShyftLifestyleProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> LifestyleContext | None:
        uid = _user_id(principal)
        row = run_readonly(
            text("SELECT diet_preference, allergies FROM user_preferences WHERE user_id = :uid"),
            {"uid": uid},
            fetch="one",
        )
        if not row:
            return None
        notes = []
        diet = row.get("diet_preference")
        if diet:
            notes.append(f"Diet preference: {diet}")
        allergy_names: list[str] = []
        allergies = row.get("allergies")
        if isinstance(allergies, list):
            allergy_names = [str(item) for item in allergies if item]
            if allergy_names:
                notes.append("Allergies recorded in SuperShyft preferences")
        return LifestyleContext(
            subject_id=str(uid),
            notes=notes,
            dietary_preference=str(diet) if diet else None,
            allergies=allergy_names,
        )
