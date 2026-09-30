from __future__ import annotations

from sqlalchemy import text

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIReport
from app.contracts.blood import BloodReport
from app.contracts.lifestyle import LifestyleContext
from app.contracts.common import IntentType
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from integrations.supershyft.db import run_readonly
from integrations.supershyft.ihr import IhrRepository, _user_id


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
        blood_plan = plan if plan.needs_blood else plan.model_copy(update={"needs_blood": True})
        return IhrRepository().get_ihr_data_for_query(principal, blood_plan).blood_reports


class SuperShyftBioAIProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> list[BioAIReport]:
        bio_plan = plan if plan.needs_bio_ai else plan.model_copy(update={"needs_bio_ai": True})
        return IhrRepository().get_ihr_data_for_query(principal, bio_plan).bio_ai_reports


class SuperShyftLifestyleProvider:
    def query(self, principal: AuthenticatedPrincipal, plan: QueryPlan) -> LifestyleContext | None:
        uid = _user_id(principal)
        row = run_readonly(
            text("SELECT diet_preference, allergies FROM user_preferences WHERE user_id = :uid"),
            {"uid": uid},
            fetch="one",
        )
        prefs = self._from_preferences(uid, row)
        if prefs and (prefs.dietary_preference or prefs.allergies or prefs.notes):
            return prefs
        return self._from_questionnaire(principal, uid) or prefs

    def _from_preferences(self, uid: int, row: dict | None) -> LifestyleContext | None:
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
        if not notes and not allergy_names:
            return None
        return LifestyleContext(
            subject_id=str(uid),
            notes=notes,
            dietary_preference=str(diet) if diet else None,
            allergies=allergy_names,
        )

    def _from_questionnaire(self, principal: AuthenticatedPrincipal, uid: int) -> LifestyleContext | None:
        from integrations.supershyft.questionnaire import fetch_questionnaire_instances

        instances = fetch_questionnaire_instances(
            principal,
            QueryPlan(
                intent=IntentType.questionnaire_lookup,
                needs_questionnaire=True,
                topic="lifestyle",
            ),
        )
        by_key: dict[str, str | float] = {}
        for instance in instances:
            for answer in instance.answers:
                if answer.question_key in by_key:
                    continue
                if answer.value in (None, ""):
                    continue
                by_key[answer.question_key] = answer.value
        if not by_key:
            return None
        diet = by_key.get("diet_preference")
        activity = by_key.get("physical_activity_frequency") or by_key.get("exercise_level")
        sleep = by_key.get("sleeping_hours")
        notes = []
        if diet:
            notes.append(f"Diet preference: {diet}")
        if activity:
            notes.append(f"Activity: {activity}")
        if sleep:
            notes.append(f"Sleep: {sleep}")
        return LifestyleContext(
            subject_id=str(uid),
            activity_level=str(activity) if activity is not None else None,
            sleep_quality=str(sleep) if sleep is not None else None,
            notes=notes,
            dietary_preference=str(diet) if diet is not None else None,
        )
