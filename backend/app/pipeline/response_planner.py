"""Conversation-first response planning for CURA.

This module repairs a small but important class of routing mistakes: report-level
requests must never fall into a missing-biomarker path merely because no marker
was named. It also provides a deterministic report-overview plan so the response
can be composed around the user's goal before optional insights are attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope, QuerySource
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.pipeline.presentation import format_user_date

_REPORT_LEVEL = re.compile(
    r"\b(?:"
    r"show|open|view|see|display|give me|pull up|review|check|summar(?:ize|ise)"
    r")\b.{0,48}\b(?:my )?(?:latest|current|most recent|last)?\s*(?:blood|lab)\s+(?:report|results?|tests?)\b"
    r"|\b(?:my )?(?:latest|current|most recent|last)\s+(?:blood|lab)\s+(?:report|results?|tests?)\b"
    r"|\b(?:which|what)\b.{0,40}\b(?:values?|results?|markers?)\b.{0,24}\b(?:outside|out of|abnormal|high or low)\b",
    re.I,
)

_FULL_REPORT = re.compile(r"\b(full|entire|all results|all values|every marker|complete report)\b", re.I)


@dataclass
class ResponsePlan:
    kind: str = "default"
    user_goal: str | None = None
    direct_answer: str | None = None
    summary: str | None = None
    highlight_keys: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    suppress_proactive_cards: bool = False


def is_report_level_request(message: str | None) -> bool:
    text = message or ""
    # Do not collapse an explicit cross-source review into a blood-only report view.
    if re.search(r"\b(?:bio-?ai|questionnaire|all sources|multiple sources)\b", text, re.I):
        return False
    return bool(_REPORT_LEVEL.search(text))


def repair_report_level_plan(plan: QueryPlan, message: str | None = None) -> QueryPlan:
    """Force explicit blood-report requests into report-level retrieval.

    JEV can correctly identify the blood source yet still classify a request such
    as "Show me my latest blood report" as a lab-result lookup. With no requested
    biomarker, that can cascade into a missing-marker answer. This repair is
    intentionally narrow and only fires for explicit report-level wording.
    """
    text = message or plan.raw_message or ""
    if not is_report_level_request(text):
        return plan
    update = {
        "intent": IntentType.report_explanation,
        "source": QuerySource.blood,
        "knowledge_scope": KnowledgeScope.personal,
        "topic": None,
        "topic_name": "latest blood report",
        "answer_depth": AnswerDepth.broad,
        "needs_blood": True,
        "needs_bio_ai": False,
        "needs_lifestyle": False,
        "needs_profile": False,
        "needs_goals": False,
        "needs_questionnaire": False,
        "needs_supershyft": True,
        "needs_general": False,
        "needs_cross_source": False,
        "history": False,
        "compare": False,
        "requested_metrics": [],
        "display_entities": [],
        "optional_entities": [],
        "reasoning_context": [],
        "time_operation": "latest_report",
        "time_scope": "latest",
        "operation": "SUMMARIZE",
        "operations": ["SUMMARIZE"],
        "reasoning_required": False,
        "medical_evidence_required": False,
        "raw_message": text,
    }
    return plan.model_copy(update=update)


def build_response_plan(message: str, plan: QueryPlan, context: HealthContext) -> ResponsePlan:
    if not is_report_level_request(message):
        return ResponsePlan()

    markers = [m for m in (context.markers or []) if m.value is not None]
    dates = [getattr(m, "measured_at", None) for m in markers if getattr(m, "measured_at", None)]
    if context.evidence:
        dates.extend([row.report_date for row in context.evidence if row.report_date])
    report_date = max(dates) if dates else None
    date_text = format_user_date(report_date)

    abnormal = [m for m in markers if getattr(m.flag, "value", str(m.flag)) in {"low", "high", "critical"}]
    normal = [m for m in markers if getattr(m.flag, "value", str(m.flag)) == "normal"]

    direct = "I found your latest blood report" if markers else "I looked for your blood report"
    if date_text and markers:
        direct += f" from {date_text}"
    direct += "."

    if markers:
        pieces = [f"It contains {len(markers)} reported results"]
        if abnormal:
            pieces.append(f"{len(abnormal)} {'is' if len(abnormal) == 1 else 'are'} outside the reported reference range")
        if normal:
            pieces.append(f"{len(normal)} {'is' if len(normal) == 1 else 'are'} within range")
        summary = "; ".join(pieces) + "."
    else:
        summary = "I don't have blood measurements from the records I can access for this question."

    actions = [
        "Show all results",
        "Explain the abnormal results",
        "Compare my latest blood report with my previous blood report",
    ]
    if _FULL_REPORT.search(message or ""):
        actions = ["Explain the abnormal results", "Compare my latest blood report with my previous blood report"]

    return ResponsePlan(
        kind="report_overview",
        user_goal="view_latest_blood_report",
        direct_answer=direct,
        summary=summary,
        highlight_keys=[m.key for m in abnormal[:3] if m.key],
        next_actions=actions,
        suppress_proactive_cards=True,
    )
