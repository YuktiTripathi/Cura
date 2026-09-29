from __future__ import annotations

from app.contracts.bio_ai import BioAIRisk
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.goals import HealthGoal
from app.contracts.lifestyle import LifestyleContext
from app.contracts.profile import PersonalHealthProfile
from app.contracts.user import UserProfile
from app.pipeline.fact_envelope import lifestyle_facts, profile_identity_facts


def build_personal_profile(
    *,
    user: UserProfile,
    lifestyle: LifestyleContext | None = None,
    bio_risks: list[BioAIRisk] | None = None,
    goals: list[HealthGoal] | None = None,
    user_facts: list[ProvenancedFact] | None = None,
) -> PersonalHealthProfile:
    subject_id = user.subject_id
    profile = PersonalHealthProfile(
        subject_id=subject_id,
        display_name=user.display_name or user.first_name,
        preferences=profile_identity_facts(user),
        lifestyle=lifestyle_facts(lifestyle, subject_id),
    )
    if lifestyle and lifestyle.dietary_preference:
        profile.dietary_preferences = [
            fact for fact in profile.lifestyle if fact.fact == "dietary_preference"
        ]
    elif lifestyle:
        for note in lifestyle.notes or []:
            if "diet preference" in note.lower():
                profile.dietary_preferences.append(
                    ProvenancedFact(
                        fact="dietary_preference",
                        value=note.split(":", 1)[-1].strip(),
                        source="SuperShyft",
                        fact_type=FactKind.user_preference,
                        subject_id=subject_id,
                    )
                )
    profile.allergies = [fact for fact in profile.lifestyle if fact.fact == "allergy"]
    for fact in user_facts or []:
        category = (fact.notes or ["preference"])[0]
        if category == "medication":
            profile.medications.append(fact)
        elif category == "allergy":
            profile.allergies.append(fact)
        else:
            profile.preferences.append(fact)
    for risk in bio_risks or []:
        profile.relevant_conditions.append(
            ProvenancedFact(
                fact=risk.code or risk.name,
                value=risk.status or risk.score,
                source=risk.source or "SuperShyft",
                report_id=risk.report_id,
                measured_at=risk.measured_at,
                fact_type=FactKind.measured_data,
                subject_id=subject_id,
                notes=["Bio-AI assessment, not a diagnosis"],
            )
        )
    for goal in goals or []:
        profile.health_goals.append(
            ProvenancedFact(
                fact=goal.goal_code,
                value=goal.label,
                source="cura_user",
                fact_type=FactKind.user_provided_data,
                subject_id=subject_id,
                status=goal.status,
            )
        )
    if not profile.dietary_preferences:
        profile.missing.append("dietary_preferences")
    if not profile.allergies:
        profile.missing.append("allergies")
    if not profile.medications:
        profile.missing.append("medications")
    if not profile.questionnaire:
        profile.missing.append("questionnaire")
    if not profile.health_goals:
        profile.missing.append("health_goals")
    return profile
