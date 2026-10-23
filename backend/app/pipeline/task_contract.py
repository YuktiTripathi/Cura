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
_QUOTED_PERSONAL_CONTEXT = re.compile(
    r"\bmy\s+(?:doctor|clinician|nurse|pharmacist|friend|family|partner)\b",
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
    intent: str = ""
    focus: str | None = None
    personal_context: str = "none"
    goal: str = "explain"
    broad_summary: bool = False
    recommendations_requested: bool = False
    card_keys: list[str] = Field(default_factory=list)
    length_band: str = "100-150"


_ADVISE = re.compile(
    r"\b(?:what should i do|what can i do|how can i|how do i|how to|improve|prevent|focus on first)\b",
    re.I,
)
_BROAD = re.compile(
    r"\b(?:overall health|how am i doing|complete blood|full report|entire report|summarize my health)\b",
    re.I,
)


def stamp_answer_spec(plan: QueryPlan, message: str | None = None) -> QueryPlan:
    """Record the resolved task. Does not add sources or replace the router."""
    text = message or plan.raw_message or ""
    intent = plan.intent.value if plan.intent else ""
    if plan.knowledge_scope == KnowledgeScope.personal:
        personal = "required"
    elif plan.general_personalization:
        personal = "optional"
    else:
        personal = "none"
    understand_report = bool(
        re.search(r"\bhelp me understand my (?:latest |last |current )?(?:blood |lab )?report\b", text, re.I)
    )
    named_focus = bool(plan.topic) and not _BROAD.search(text)
    broad = intent in {"broad_health_summary", "health_scenario", "report_explanation"} or bool(_BROAD.search(text))
    if named_focus or understand_report or (_ADVISE.search(text) and not _BROAD.search(text)):
        broad = False
    if _ADVISE.search(text) or intent == "nutrition_guidance":
        goal = "advise"
    elif plan.compare or intent in {"trend", "bio_ai_comparison"}:
        goal = "compare"
    elif intent == "bio_ai_score" and re.search(r"\b(?:explain|interpret|understand|what does|what do|mean)\b", text, re.I):
        goal = "interpret"
    elif intent in {"latest_result", "previous_result", "bio_ai_score"}:
        goal = "lookup"
    elif understand_report or intent in {"blood_marker_explanation", "bio_ai_explanation"} or (named_focus and personal == "required"):
        goal = "interpret"
    elif broad:
        goal = "synthesize"
    else:
        goal = "explain"
    if personal == "none" and goal in {"lookup", "interpret", "synthesize"}:
        goal = "explain"
        broad = False
    keys = [key for key in (plan.requested_metrics or []) if key]
    card_keys = [] if broad else keys[:6]
    if goal == "explain" and personal == "none":
        length = "85-100"
    elif intent == "blood_marker_explanation":
        length = "100-120"
    elif goal == "compare" or understand_report or broad or (
        goal == "interpret" and intent in {"bio_ai_score", "bio_ai_explanation"}
    ):
        length = "100-150"
    else:
        length = "100-150"
    primary = _primary_source(text, plan)
    existing = dict(plan.task_contract or {})
    existing.update(
        {
            "intent": intent,
            "focus": plan.topic,
            "personal_context": personal,
            "goal": goal,
            "broad_summary": broad,
            "recommendations_requested": goal == "advise",
            "card_keys": card_keys,
            "length_band": length,
            "primary_source": primary,
        }
    )
    update: dict = {"task_contract": existing}
    # A report explanation keeps the source the user named. Later routing must not swap it.
    if primary == "blood_report":
        update.update(needs_blood=True, needs_bio_ai=False, needs_questionnaire=False, source=QuerySource.blood)
    elif primary == "bio_ai":
        update.update(needs_blood=False, needs_bio_ai=True, needs_questionnaire=False, source=QuerySource.bio_ai)
    return plan.model_copy(update=update)


def _primary_source(text: str, plan: QueryPlan) -> str:
    """Which record the answer must explain. Mixed only when the user asked across sources."""
    blood = bool(re.search(r"\b(?:blood|lab) report\b", text or "", re.I))
    bio = bool(re.search(r"\bbio-?ai\b", text or "", re.I))
    marker = bool(re.search(r"\b(?:ldl|hdl|hba1c|cholesterol|triglycerides|hemoglobin|ferritin)\b", text or "", re.I))
    if blood and bio or (bio and marker):
        return "mixed"
    if blood:
        return "blood_report"
    if bio and re.search(r"\breport\b", text or "", re.I):
        return "bio_ai"
    if plan.explicit_source_ref and plan.needs_blood and not plan.needs_bio_ai:
        return "blood_report"
    if plan.explicit_source_ref and plan.needs_bio_ai and not plan.needs_blood:
        return "bio_ai"
    if plan.intent in {IntentType.broad_health_summary, IntentType.health_scenario}:
        return "mixed"
    return "unspecified"


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
    elif (
        _PERSONAL_MARKER.search(text)
        and not _QUOTED_PERSONAL_CONTEXT.search(text)
        and not re.search(r"\bhow does\b", text, re.I)
    ):
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
    if plan.needs_user_uploaded and not plan.needs_cross_source:
        return plan
    message = plan.raw_message or ""
    from app.pipeline.intent import is_educational_utterance, is_personal_utterance, requires_personal_record

    if (
        is_educational_utterance(message)
        and not is_personal_utterance(message)
        and not requires_personal_record(message, prior_personal=plan.knowledge_scope == KnowledgeScope.personal, follow_up_topic=plan.topic)
    ):
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
    if plan.document_ids or plan.needs_user_uploaded:
        # "Blood report" may refer to the explicitly attached/uploaded report. The
        # source router has already resolved that reference, so a text-only contract
        # must not silently replace it with the SuperShyft blood source.
        return plan.model_copy(update={"task_contract": contract.model_dump()})
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
