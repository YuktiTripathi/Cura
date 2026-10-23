"""Choose structured lookup vs PageIndex without question-specific handlers."""

from __future__ import annotations

import re

from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import match_lab_keys, primary_lab_key

_NARRATIVE = re.compile(
    r"\b("
    r"radiologist|impression|patholog(?:y|ist)|doctor (?:say|said|conclude)|"
    r"what did the (?:doctor|report|radiologist)|"
    r"explain the (?:impression|recommendation|findings)|"
    r"summar(?:y|ize|ise) (?:the )?(?:document|report|section|pathology|comments)|"
    r"tell me about (?:my )?.{0,48}(?:results|report|allergy)|"
    r"main findings in this document|report comments|"
    r"what does the (?:report|doctor|radiologist) say|"
    r"recommendation section|conclude"
    r")\b",
    re.I,
)
_STRUCTURED = re.compile(
    r"\b("
    r"what(?:'s| is| was) my|show (?:all )?(?:my )?(?:abnormal|high|low)|"
    r"which (?:values|markers|results) are (?:high|low|abnormal)|"
    r"which .{0,24}markers"
    r")\b",
    re.I,
)
_SUMMARY = re.compile(
    r"\b(explain this (?:whole |entire )?report|summar(?:y|ize|ise) this (?:whole |entire )?(?:report|document)|"
    r"what (?:does|did) this (?:report|pdf|document|discharge summary|prescription) (?:say|show)|"
    r"summar(?:y|ize|ise) this discharge summary|"
    r"summar\w*.{0,48}\b(?:findings|report|document|results)\b|"
    r"anything unusual|anything abnormal|"
    r"what does this medical document say about (?:my )?treatment)\b",
    re.I,
)
_ALL_EXTRACTED = re.compile(
    r"\b(view all extracted|all extracted (?:results|measurements|values)|"
    r"show (?:me )?(?:all )?(?:the )?extracted (?:measurements|results|values))\b",
    re.I,
)


def wants_document_summary(message: str) -> bool:
    return bool(_SUMMARY.search(message or ""))


def wants_all_extracted(message: str) -> bool:
    return bool(_ALL_EXTRACTED.search(message or ""))


def wants_document_narrative(message: str, plan: QueryPlan | None = None) -> bool:
    text = message or (plan.raw_message if plan else "") or ""
    if wants_document_summary(text):
        return True
    if _NARRATIVE.search(text):
        return True
    if re.search(r"\bwhat does my .{3,80}\b(?:say|show)\b", text, re.I) and not match_lab_keys(text):
        return True
    if re.search(r"\b(allergy|bio-?allergy)\b", text, re.I) and not match_lab_keys(text):
        return True
    ops = {str(item).upper() for item in ((plan.operations if plan else None) or [])}
    return bool(ops & {"DOCUMENT_NARRATIVE_RETRIEVAL", "DOCUMENT_SUMMARY"})


def wants_document_structured(message: str, plan: QueryPlan | None = None) -> bool:
    text = message or (plan.raw_message if plan else "") or ""
    if wants_all_extracted(text):
        return True
    if wants_document_narrative(text, plan) and not primary_lab_key(text) and not match_lab_keys(text):
        return False
    if _STRUCTURED.search(text) or primary_lab_key(text) or match_lab_keys(text):
        return True
    selectors = {str(item).upper() for item in ((plan.selectors if plan else None) or [])}
    if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"}:
        return True
    ops = {str(item).upper() for item in ((plan.operations if plan else None) or [])}
    return bool(ops & {"DOCUMENT_STRUCTURED_LOOKUP"})


def mixed_document_query(message: str, plan: QueryPlan | None = None) -> bool:
    return wants_document_structured(message, plan) and wants_document_narrative(message, plan)
