from __future__ import annotations

from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.health_context import Comparison
from app.contracts.lifestyle import LifestyleContext
from app.contracts.recommendation import ApprovedRecommendation
from app.contracts.user import UserProfile


def marker_fact(marker: BloodMarker, subject_id: str | None = None) -> ProvenancedFact:
    return ProvenancedFact(
        fact=marker.key or marker.name,
        value=marker.value,
        unit=marker.unit,
        source=marker.source or "SuperShyft",
        report_id=marker.report_id,
        measured_at=marker.measured_at,
        fact_type=FactKind.measured_data,
        subject_id=subject_id,
        status=marker.flag.value if marker.flag else None,
    )


def bio_risk_fact(risk: BioAIRisk, subject_id: str | None = None) -> ProvenancedFact:
    return ProvenancedFact(
        fact=risk.code or risk.name,
        value=risk.score,
        source=risk.source or "SuperShyft",
        report_id=risk.report_id,
        measured_at=risk.measured_at,
        fact_type=FactKind.measured_data,
        subject_id=subject_id,
        status=risk.status,
        notes=["Bio-AI assessment, not a diagnosis"],
    )


def comparison_facts(row: Comparison, subject_id: str | None = None) -> list[ProvenancedFact]:
    facts: list[ProvenancedFact] = []
    if row.previous_value is not None:
        facts.append(
            ProvenancedFact(
                fact=row.topic,
                value=row.previous_value,
                source="SuperShyft",
                report_id=row.previous_report_id,
                measured_at=row.previous_date,
                fact_type=FactKind.measured_data,
                subject_id=subject_id,
                notes=["previous"],
            )
        )
    if row.current_value is not None:
        facts.append(
            ProvenancedFact(
                fact=row.topic,
                value=row.current_value,
                source="SuperShyft",
                report_id=row.current_report_id,
                measured_at=row.current_date,
                fact_type=FactKind.measured_data,
                subject_id=subject_id,
                notes=["current"],
            )
        )
    return facts


def lifestyle_facts(life: LifestyleContext | None, subject_id: str) -> list[ProvenancedFact]:
    if life is None:
        return []
    out: list[ProvenancedFact] = []
    if life.dietary_preference:
        out.append(
            ProvenancedFact(
                fact="dietary_preference",
                value=life.dietary_preference,
                source="SuperShyft",
                fact_type=FactKind.user_preference,
                subject_id=subject_id,
            )
        )
    if life.activity_level:
        out.append(
            ProvenancedFact(
                fact="activity_level",
                value=life.activity_level,
                source="SuperShyft",
                fact_type=FactKind.user_preference,
                subject_id=subject_id,
            )
        )
    if life.sleep_quality:
        out.append(
            ProvenancedFact(
                fact="sleep_quality",
                value=life.sleep_quality,
                source="SuperShyft",
                fact_type=FactKind.user_preference,
                subject_id=subject_id,
            )
        )
    for allergy in life.allergies or []:
        out.append(
            ProvenancedFact(
                fact="allergy",
                value=allergy,
                source="SuperShyft",
                fact_type=FactKind.user_provided_data,
                subject_id=subject_id,
            )
        )
    for goal in life.goals or []:
        out.append(
            ProvenancedFact(
                fact="stated_goal",
                value=goal,
                source="SuperShyft",
                fact_type=FactKind.user_provided_data,
                subject_id=subject_id,
            )
        )
    return out


def profile_identity_facts(profile: UserProfile) -> list[ProvenancedFact]:
    facts: list[ProvenancedFact] = []
    if profile.age_band:
        facts.append(
            ProvenancedFact(
                fact="age_band",
                value=profile.age_band,
                source="SuperShyft",
                fact_type=FactKind.user_provided_data,
                subject_id=profile.subject_id,
            )
        )
    if profile.sex:
        facts.append(
            ProvenancedFact(
                fact="sex",
                value=profile.sex,
                source="SuperShyft",
                fact_type=FactKind.user_provided_data,
                subject_id=profile.subject_id,
            )
        )
    return facts


def recommendation_facts(rows: list[ApprovedRecommendation]) -> list[ProvenancedFact]:
    return [
        ProvenancedFact(
            fact=row.category,
            value=row.text,
            source="cura_policy",
            fact_type=FactKind.model_recommendation,
        )
        for row in rows
    ]
