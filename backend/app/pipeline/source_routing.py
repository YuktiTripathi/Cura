from __future__ import annotations

import logging
import re

from app.contracts.common import KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.pipeline.intent import (
    is_educational_utterance,
    is_medical_advice_request,
    is_personal_utterance,
    requires_personal_record,
)

logger = logging.getLogger("cura.pipeline")

_UPLOAD = re.compile(r"\b(upload(?:ed)?|pdf|this document|the document|this report)\b", re.I)
_SS = re.compile(r"\bsupershyft\b", re.I)
_COMPARE = re.compile(
    r"\b(compare|comparison|difference|differ(?:ent)?|between (?:these|the|my)|"
    r"changed between|two reports|which (?:one|report) is newer|has my .{0,40} changed)\b",
    re.I,
)
_WHAT_ABOUT = re.compile(r"^\s*what about\b", re.I)


def apply_source_routing(
    plan: QueryPlan,
    *,
    document_ids: list[str] | None = None,
    uploaded_document_count: int = 0,
    prior_source_mode: str | None = None,
) -> QueryPlan:
    ids = document_ids or []
    text = plan.raw_message or ""
    upload_cue = bool(_UPLOAD.search(text))
    ss_cue = bool(_SS.search(text))
    compare_cue = bool(_COMPARE.search(text))
    educational = is_educational_utterance(text) and not requires_personal_record(text) and not compare_cue and not upload_cue

    needs_general = plan.knowledge_scope == KnowledgeScope.general
    needs_supershyft = bool(plan.needs_personal_data)
    needs_user_uploaded = False
    needs_cross = False

    if educational and not compare_cue and not upload_cue and not plan.explicit_source_ref:
        plan.needs_general = True
        plan.needs_supershyft = False
        plan.needs_user_uploaded = False
        plan.needs_cross_source = False
        return annotate_plan(plan)

    if compare_cue and (upload_cue or ids or prior_source_mode == "cross"):
        needs_cross = True
        needs_user_uploaded = True
        needs_supershyft = True
        needs_general = False
        plan.needs_blood = True
        plan.knowledge_scope = KnowledgeScope.personal
        plan.compare = True
        plan.source = QuerySource.mixed

    if compare_cue and re.search(r"\b(two reports|my reports)\b", text, re.I) and uploaded_document_count > 0:
        needs_cross = True
        needs_user_uploaded = True
        needs_supershyft = True
        plan.needs_blood = True
        plan.knowledge_scope = KnowledgeScope.personal
        plan.source = QuerySource.mixed

    if ids and not compare_cue and not ss_cue:
        needs_user_uploaded = True
        if not needs_cross:
            needs_supershyft = False
            plan.needs_blood = False
            plan.needs_bio_ai = False
            plan.source = QuerySource.user_uploaded

    if upload_cue and not ss_cue and not compare_cue:
        needs_user_uploaded = True
        needs_supershyft = False
        plan.needs_blood = False
        plan.source = QuerySource.user_uploaded

    if ss_cue and not upload_cue and not compare_cue:
        needs_supershyft = True
        needs_user_uploaded = False
        needs_cross = False
        plan.source = QuerySource.supershyft

    if prior_source_mode == "cross" and not educational:
        if compare_cue or _WHAT_ABOUT.search(text) or requires_personal_record(text) or "different" in text.lower() or "newer" in text.lower():
            needs_cross = True
            needs_user_uploaded = True
            needs_supershyft = True
            plan.needs_blood = True
            plan.knowledge_scope = KnowledgeScope.personal
            plan.source = QuerySource.mixed

    if compare_cue and ss_cue and prior_source_mode == "user_uploaded":
        needs_cross = True
        needs_user_uploaded = True
        needs_supershyft = True
        plan.needs_blood = True
        plan.knowledge_scope = KnowledgeScope.personal
        plan.source = QuerySource.mixed

    if prior_source_mode == "user_uploaded" and not ss_cue and not educational:
        if ids or upload_cue or _WHAT_ABOUT.search(text):
            needs_user_uploaded = True
            if not needs_cross:
                needs_supershyft = False

    plan.needs_general = needs_general and not needs_cross
    plan.needs_supershyft = needs_supershyft
    plan.needs_user_uploaded = needs_user_uploaded
    plan.needs_cross_source = needs_cross
    if needs_cross:
        plan.compare = True
    logger.debug(
        "source_routing knowledge_scope=%s needs_supershyft=%s needs_user_uploaded=%s "
        "needs_general=%s needs_cross_source=%s needs_personal_data=%s",
        plan.knowledge_scope.value,
        plan.needs_supershyft,
        plan.needs_user_uploaded,
        plan.needs_general,
        plan.needs_cross_source,
        plan.needs_personal_data,
    )
    return annotate_plan(plan)


def annotate_plan(plan: QueryPlan) -> QueryPlan:
    message = plan.raw_message or ""
    plan.personal_reference = is_personal_utterance(message)
    sources: list[str] = []
    if plan.needs_user_uploaded:
        sources.append("uploaded_documents")
    if plan.needs_blood:
        sources.append("blood_reports")
    if plan.needs_bio_ai:
        sources.append("bio_ai_report")
    if plan.needs_lifestyle or plan.needs_profile:
        sources.append("lifestyle")
    plan.data_sources = list(dict.fromkeys(sources))
    guidance = bool(getattr(plan, "needs_guidance", False) or is_medical_advice_request(message))
    if guidance and plan.needs_personal_data:
        plan.needs_guidance = True
        plan.needs_general = True
    plan.medical_evidence_required = bool(
        (plan.needs_general and plan.intent.value != "casual_conversation")
        or (plan.needs_personal_data and guidance)
    )
    return plan
