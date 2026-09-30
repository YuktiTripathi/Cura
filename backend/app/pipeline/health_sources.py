"""Canonical health source types. QueryPlan.needs_* flags remain the retrieval switches."""

from __future__ import annotations

import re

from app.contracts.common import HealthSourceType, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.questionnaire_intent import explicit_questionnaire_request

_DATA_SOURCE_NAMES = {
    HealthSourceType.supershyft_blood: "blood_reports",
    HealthSourceType.supershyft_bio_ai: "bio_ai_report",
    HealthSourceType.supershyft_questionnaire: "questionnaire",
    HealthSourceType.supershyft_lifestyle: "lifestyle",
    HealthSourceType.uploaded_document: "uploaded_documents",
}

_BIO_CUE = re.compile(r"\b(bio-?ai|metabolic age|metabolic score|dyslipidemia|metsights)\b", re.I)
_LIFESTYLE_CUE = re.compile(
    r"\b(lifestyle|how active(?: am i)?|activity level|sleep habits|dietary habits)\b",
    re.I,
)


def mixed_bio_cue(message: str) -> bool:
    return bool(_BIO_CUE.search(message or ""))


def mixed_questionnaire_cue(message: str) -> bool:
    return explicit_questionnaire_request(message or "")


def mixed_lifestyle_cue(message: str) -> bool:
    return bool(_LIFESTYLE_CUE.search(message or ""))


def mixed_personal_cues(message: str) -> dict[str, bool]:
    return {
        "bio_ai": mixed_bio_cue(message),
        "questionnaire": mixed_questionnaire_cue(message),
        "lifestyle": mixed_lifestyle_cue(message),
    }


def sources_from_flags(plan: QueryPlan) -> list[HealthSourceType]:
    sources: list[HealthSourceType] = []
    if plan.needs_blood:
        sources.append(HealthSourceType.supershyft_blood)
    if plan.needs_bio_ai:
        sources.append(HealthSourceType.supershyft_bio_ai)
    if plan.needs_questionnaire:
        sources.append(HealthSourceType.supershyft_questionnaire)
    if plan.needs_lifestyle or plan.needs_profile:
        sources.append(HealthSourceType.supershyft_lifestyle)
    if plan.needs_user_uploaded:
        sources.append(HealthSourceType.uploaded_document)
    if plan.needs_general or plan.medical_evidence_required:
        sources.append(HealthSourceType.medical_knowledge)
    return list(dict.fromkeys(sources))


def data_source_names(sources: list[HealthSourceType]) -> list[str]:
    names: list[str] = []
    for item in sources:
        name = _DATA_SOURCE_NAMES.get(item)
        if name and name not in names:
            names.append(name)
    return names


def sync_plan_sources(plan: QueryPlan) -> QueryPlan:
    plan.sources = sources_from_flags(plan)
    plan.data_sources = data_source_names(plan.sources)
    if len(plan.sources) > 1 and plan.source not in {QuerySource.mixed, QuerySource.general}:
        if HealthSourceType.uploaded_document in plan.sources and any(
            item.value.startswith("supershyft_") for item in plan.sources
        ):
            plan.source = QuerySource.mixed
    return plan


def has_supershyft_sources(plan: QueryPlan) -> bool:
    return bool(
        plan.needs_blood
        or plan.needs_bio_ai
        or plan.needs_questionnaire
        or plan.needs_lifestyle
        or plan.needs_profile
        or plan.needs_supershyft
    )


def is_lab_source_compare(plan: QueryPlan) -> bool:
    """PDF vs SuperShyft blood marker comparison. Other mixed queries use ContextMerger."""
    if not plan.needs_cross_source:
        return False
    if not plan.needs_user_uploaded:
        return False
    if not (plan.needs_blood or plan.needs_supershyft):
        return False
    message = plan.raw_message or ""
    if mixed_bio_cue(message) or mixed_questionnaire_cue(message) or mixed_lifestyle_cue(message):
        return False
    return True
