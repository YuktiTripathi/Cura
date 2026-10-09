"""Immutable reading of what the user asked, used to stop later stages from changing the task.

Jev remains the router. This module only corrects plans when the user's words
unambiguously require a source or operation that the current plan dropped.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan

_OUTSIDE = re.compile(
    r"\b(?:outside|out of) (?:the )?(?:range|reference)|which (?:of my )?(?:values|results|markers).{0,24}(?:high or low|abnormal)\b",
    re.I,
)
_BLOOD_REPORT = re.compile(r"\b(?:blood|lab) (?:report|results?|tests?)\b", re.I)
_BIO_LIST = re.compile(
    r"\b(?:what are|show|list|give me)\b.{0,40}\b(?:my )?bio-?ai\b.{0,24}\b(?:risk )?scores?\b"
    r"|\bmy bio-?ai risk scores?\b",
    re.I,
)
_WHY_RISK = re.compile(r"\bwhy\b.{0,40}\b(?:my )?.{0,24}\brisk\b", re.I)
_DISCREPANCY = re.compile(
    r"\b(?:but|although|even though)\b.{0,80}\bbio-?ai\b|\bbio-?ai\b.{0,40}\b(?:but|although)\b",
    re.I,
)
_PRIORITIZE = re.compile(r"\b(?:focus on first|prioriti[sz]e|which health risk|what should i focus)\b", re.I)
_SYMPTOM = re.compile(r"\b(?:tired|fatigue|exhausted)\b.{0,40}\b(?:report|blood|explain|could)\b|\bcould my reports\b", re.I)
_PERSONAL_MARKER = re.compile(
    r"\bmy\b.{0,32}\b(hdl|ldl|hba1c|glucose|tsh|hemoglobin|haemoglobin|cholesterol|triglycerides|alt|ast|bilirubin)\b",
    re.I,
)


class ReasoningOperation(str, Enum):
    lookup = "LOOKUP"
    interpret = "INTERPRET"
    explain = "EXPLAIN"
    compare = "COMPARE"
    explain_discrepancy = "EXPLAIN_DISCREPANCY"
    prioritize = "PRIORITIZE"
    investigate_symptom = "INVESTIGATE_SYMPTOM"
    plan = "PLAN"
    summarize = "SUMMARIZE"
    general_education = "GENERAL_EDUCATION"


class TaskContract(BaseModel):
    version: str = "1"
    original_message: str
    operations: list[ReasoningOperation] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    response_type: str = "DIRECT_ANSWER"


def build_task_contract(message: str | None) -> TaskContract:
    text = message or ""
    ops: list[ReasoningOperation] = []
    sources: list[str] = []
    response = "DIRECT_ANSWER"
    if _BIO_LIST.search(text) and not _WHY_RISK.search(text):
        ops.append(ReasoningOperation.lookup)
        sources.append("bio_ai")
        response = "BIO_AI_SCORE_LIST"
    elif _DISCREPANCY.search(text):
        ops.append(ReasoningOperation.explain_discrepancy)
        sources.extend(["blood_report", "bio_ai"])
        response = "CROSS_SOURCE_EXPLANATION"
    elif _WHY_RISK.search(text):
        ops.append(ReasoningOperation.explain)
        sources.extend(["bio_ai", "blood_report"])
        response = "PERSONAL_RISK_EXPLANATION"
    elif _PRIORITIZE.search(text):
        ops.append(ReasoningOperation.prioritize)
        sources.extend(["blood_report", "bio_ai"])
        response = "PRIORITIZED_CONCERNS"
    elif _SYMPTOM.search(text):
        ops.append(ReasoningOperation.investigate_symptom)
        sources.append("blood_report")
        response = "SYMPTOM_CONTEXT"
    elif _OUTSIDE.search(text) or (_BLOOD_REPORT.search(text) and re.search(r"\b(?:outside|abnormal|high or low)\b", text, re.I)):
        ops.append(ReasoningOperation.lookup)
        sources.append("blood_report")
        response = "ABNORMAL_LIST"
    elif _PERSONAL_MARKER.search(text) and not re.search(r"\bhow does\b", text, re.I):
        ops.append(ReasoningOperation.interpret if re.search(r"\b(?:good|bad|mean|normal|high|low|worry)\b", text, re.I) else ReasoningOperation.lookup)
        sources.append("blood_report")
        response = "MARKER_LOOKUP"
    return TaskContract(original_message=text, operations=ops, required_sources=sources, response_type=response)


def reapply_stored_contract(plan: QueryPlan) -> QueryPlan:
    """Downstream source routing must not drop sources the task contract required."""
    raw = getattr(plan, "task_contract", None) or {}
    sources = list(raw.get("required_sources") or [])
    if not sources:
        return plan
    if "blood_report" in sources:
        plan.needs_blood = True
        plan.needs_supershyft = True
        plan.needs_user_uploaded = False
    if "bio_ai" in sources:
        plan.needs_bio_ai = True
        plan.needs_supershyft = True
    if raw.get("response_type") == "BIO_AI_SCORE_LIST":
        plan.needs_blood = False
        plan.intent = IntentType.bio_ai_score
    return plan


def apply_task_contract(plan: QueryPlan, message: str | None = None) -> QueryPlan:
    """Keep required sources when the wording is unambiguous. Does not replace Jev."""
    contract = build_task_contract(message or plan.raw_message)
    if not contract.required_sources:
        return plan
    update: dict = {
        "knowledge_scope": KnowledgeScope.personal,
        "needs_supershyft": True,
        "needs_general": False,
        "needs_user_uploaded": False,
    }
    if "blood_report" in contract.required_sources:
        update["needs_blood"] = True
    if "bio_ai" in contract.required_sources:
        update["needs_bio_ai"] = True
    if contract.response_type == "BIO_AI_SCORE_LIST":
        update.update(
            intent=IntentType.bio_ai_score,
            source=QuerySource.bio_ai,
            needs_blood=False,
            needs_bio_ai=True,
            topic=None,
            requested_metrics=[],
        )
    elif contract.response_type == "ABNORMAL_LIST":
        update.update(intent=IntentType.report_explanation, source=QuerySource.blood, needs_bio_ai=False)
        selectors = list(plan.selectors or [])
        if "ABNORMAL" not in {str(item).upper() for item in selectors}:
            selectors.append("ABNORMAL")
        update["selectors"] = selectors
    elif contract.response_type == "MARKER_LOOKUP":
        update.update(source=QuerySource.blood, needs_blood=True, needs_bio_ai=False)
    elif contract.response_type == "CROSS_SOURCE_EXPLANATION":
        update.update(source=QuerySource.mixed, needs_cross_source=True)
    plan.task_contract = contract.model_dump()
    return plan.model_copy(update=update)
