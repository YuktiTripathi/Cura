"""User-facing answer assembly. Lookups stay short; reasoning keeps evidence and follow-ups."""

from __future__ import annotations

import re

from app.contracts.common import KnowledgeScope
from app.contracts.conversation_experience import ConversationExperiencePlan
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.contracts.diagnostics import TestingOption
from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse
from app.contracts.query import QueryPlan
from app.llm.models import LLMStructuredOutput
from app.pipeline.conversation_experience import (
    build_experience_plan,
    chip_prompts,
    discipline_follow_ups,
    experience_blocks_from_answer,
)
from app.pipeline.lab_parameters import display_name_for
from app.pipeline.narrative import finding_from_marker
from app.pipeline.response_planner import build_response_plan
from app.pipeline.testing_option import is_explicit_catalog_lookup
from app.pipeline.presentation import (
    build_structured_response,
    flatten_structured_response,
    is_list_only,
    sanitize_internal_ids,
    strip_lookup_disclaimers,
    attach_presentation_personalization,
    prefer_report_range,
)

_HANDLED_LLM = re.compile(
    r"\b(symptoms?|medication|supplement|previous report|changed over time|what does .{0,24} mean)\b",
    re.I,
)


def _llm_handling(text: str) -> tuple[str | None, str | None]:
    if re.search(r"\b(symptoms?|medication|supplement)\b", text, re.I):
        return "CLINICAL_CONTEXT", "CONTINUE_INTERPRETATION"
    if re.search(r"\bprevious|changed over time|trend\b", text, re.I):
        return "YES_NO", "TREND"
    if re.search(r"\bwhat does .{0,24} mean\b", text, re.I):
        return None, "CONTINUE_INTERPRETATION"
    return None, None


_AMBIGUOUS_DEICTIC = re.compile(
    r"\b(?:that|this) (?:marker|result|value|finding)\b|^\s*what is (?:that|this)\b|\bwhat does it mean\b",
    re.I,
)

def _has_unique_referent(plan: QueryPlan, context: HealthContext) -> bool:
    candidates = [
        *(plan.display_entities or []),
        *(plan.requested_metrics or []),
        *[m.key for m in (context.markers or []) if m.key],
    ]
    return len(set(item for item in candidates if item)) == 1

def _valid_follow_up(item: FollowUpSuggestion, plan: QueryPlan, context: HealthContext) -> bool:
    text = (item.text or "").strip()
    if not text:
        return False
    if _AMBIGUOUS_DEICTIC.search(text) and not _has_unique_referent(plan, context):
        return False
    return True


class ResponseComposer:
    def compose(
        self,
        answer: str,
        *,
        plan: QueryPlan,
        context: HealthContext,
        follow_ups: list[FollowUpSuggestion] | None = None,
        llm_follow_ups: list[str] | None = None,
        llm_result: LLMStructuredOutput | None = None,
        testing_option: TestingOption | None = None,
        experience: ConversationExperiencePlan | None = None,
        conversation_turn: str | None = None,
    ) -> tuple[str, list[FollowUpSuggestion], StructuredResponse]:
        experience = experience or build_experience_plan(plan.raw_message or "", plan, context)
        answer_turn = (conversation_turn or plan.conversation_turn) == "ANSWER_TO_ASSISTANT"
        extras: list[FollowUpSuggestion] = []
        for question in (llm_follow_ups or [])[:1]:
            value = (question or "").strip()
            if not value or not _HANDLED_LLM.search(value):
                continue
            expected, path = _llm_handling(value)
            if not path:
                continue
            extras.append(
                FollowUpSuggestion(
                    text=value,
                    category="suggested",
                    knowledge_scope=plan.knowledge_scope.value,
                    requires_personal_context=plan.needs_personal_data,
                    expected_reply_type=expected,
                    handling_path=path,
                )
            )
        seeded = extras + [item for item in (follow_ups or []) if item.handling_path]
        seeded = [item for item in seeded if _valid_follow_up(item, plan, context)]
        extra_chips = chip_prompts(experience.next_action, context, plan)
        question, chips = discipline_follow_ups(
            seeded,
            experience,
            answer_turn=answer_turn,
            extra_chips=extra_chips,
            allow_default_question=bool(context.markers) and context.knowledge_scope == KnowledgeScope.personal,
        )
        combined = [*question, *chips]
        if is_list_only(plan.raw_message) or experience.depth.value == "SHORT":
            combined = combined[:1]
        if answer_turn:
            # A reply to CURA should not trigger another generic clinical question.
            # When the user has supplied meaningful new context (captured in
            # reasoning_context), keep one action chip so the conversation can
            # naturally move forward instead of ending abruptly.
            question = []
            continuation = chip_prompts(experience.next_action, context, plan) if plan.reasoning_context else []
            combined = [
                FollowUpSuggestion(
                    text=continuation[0],
                    category="suggested",
                    handling_path="CONTINUE_INTERPRETATION",
                )
            ] if continuation else []
            chips = list(combined)
        response_plan = build_response_plan(plan.raw_message or "", plan, context)
        if response_plan.kind == "report_overview":
            question = []
            combined = [
                FollowUpSuggestion(
                    text=label,
                    category="report_action",
                    handling_path="CONTINUE_INTERPRETATION",
                )
                for label in response_plan.next_actions
            ]
            chips = list(combined)
        follow_text = question[0].text if question else None
        cleaned = sanitize_internal_ids(prefer_report_range(answer or "", context))
        if context.premise_verified is False and context.premise and context.premise.note:
            note = sanitize_internal_ids(context.premise.note)
            if note.lower() not in cleaned.lower():
                cleaned = f"{note} {cleaned}".strip()
        presentation = build_structured_response(
            cleaned,
            plan=plan,
            context=context,
            follow_up=follow_text,
            llm_themes=list(llm_result.themes) if llm_result and llm_result.themes else None,
            llm_overall=llm_result.overall_summary if llm_result else None,
        )
        if response_plan.kind == "report_overview":
            presentation.headline = "Your latest blood report"
            presentation.summary = response_plan.direct_answer
            presentation.interpretation = response_plan.summary
            presentation.uncertainties = []
            presentation.follow_up = None
        if presentation.mode in {ResponseMode.single_value, ResponseMode.result_list} and response_plan.kind != "report_overview":
            combined = combined[:1] if not answer_turn else []
        text = flatten_structured_response(presentation, raw_answer=cleaned)
        model_wrote = bool(llm_result and (llm_result.answer or "").strip()) and presentation.mode != ResponseMode.clinician_handoff
        if model_wrote and cleaned.strip():
            # The model's answer IS the chat answer. Cards, missing-data notes and stock next
            # steps stay in the structured presentation; they are not spliced into the prose.
            text = cleaned.strip()
        if response_plan.kind == "report_overview":
            abnormal = [
                m for m in (context.markers or [])
                if getattr(m.flag, "value", str(m.flag)) in {"low", "high", "critical"}
            ]
            highlight = ""
            if abnormal:
                names = ", ".join(m.name for m in abnormal[:3])
                highlight = f" The results worth reviewing first are {names}."
            text = f"{response_plan.direct_answer} {response_plan.summary}{highlight}".strip()
        if not text:
            text = strip_lookup_disclaimers(cleaned, presentation.mode) or cleaned
        change_line = None if model_wrote else _change_summary(context)
        if change_line and not any(name.lower() in text.lower() for name in change_line[1]):
            # A comparison question is answered with what moved, before any wider summary.
            text = f"{change_line[0]} {text}".strip()
        if testing_option:
            presentation.testing_option = testing_option
            if is_explicit_catalog_lookup(plan.raw_message or ""):
                lead = testing_option.headline or testing_option.display_name
                detail = testing_option.reason
                text = " ".join(part for part in (lead, detail) if part).strip() or text
                presentation.summary = text
                presentation.headline = lead or presentation.headline
        presentation = attach_presentation_personalization(presentation, context, plan)
        presentation.conversation_goal = experience.goal.value
        presentation.response_depth = experience.depth.value
        presentation.next_conversation_action = experience.next_action.value
        presentation.blocks = [item.model_dump(mode="json") for item in experience_blocks_from_answer(text, experience, context)]
        presentation.related_findings = _related_findings(context, experience)
        presentation.suggestion_chips = [item.text for item in chips]
        if experience.topic_summary and not is_explicit_catalog_lookup(plan.raw_message or ""):
            presentation.topic_summary = experience.topic_summary.model_dump(mode="json")
        if presentation.mode.value == "CLINICIAN_HANDOFF" and presentation.summary:
            text = presentation.summary
        if presentation.quiet_mode and presentation.mode.value == "QUIET_UPDATE":
            if not re.search(r"nothing new stands out|would not suggest changing", text, re.I):
                text = (
                    "Nothing new stands out in these results. The available measurements look stable, "
                    "so I would not suggest changing anything based on this report alone."
                )
                presentation.summary = text
        from app.pipeline.presentation_policy import apply_presentation_policy

        presentation, policy_trace = apply_presentation_policy(presentation, follow_up_count=len(combined))
        if context.answer_evidence_trace is not None:
            context.answer_evidence_trace.update(policy_trace)
        return text, combined, presentation


def _related_findings(context: HealthContext, experience: ConversationExperiencePlan) -> list[PresentedFinding]:
    wanted = set(experience.relevant.supporting_keys)
    rows: list[PresentedFinding] = []
    for marker in context.markers or []:
        if marker.key not in wanted:
            continue
        try:
            rows.append(finding_from_marker(marker))
        except Exception:
            rows.append(
                PresentedFinding(
                    label=display_name_for(marker.key) or marker.name,
                    value=None if marker.value is None else str(marker.value),
                    unit=marker.unit,
                    canonical_key=marker.key,
                )
            )
    return rows


def _change_summary(context) -> tuple[str, list[str]] | None:
    """'Since your previous report: LDL 145 -> 138 mg/dL (down).' Values exactly as stored."""
    semantic = getattr(context, "semantic_plan", None) or {}
    if semantic.get("primary_goal") != "COMPARE":
        return None
    names = {m.key: (m.name or m.key) for m in getattr(context, "markers", None) or []}
    moved = [
        b for b in getattr(context, "baselines", None) or []
        if b.previous is not None and b.latest is not None and b.latest != b.previous
    ]
    if not moved:
        return None
    moved.sort(key=lambda b: abs(b.percentage_change or 0), reverse=True)
    parts, labels = [], []
    for b in moved[:3]:
        label = names.get(b.entity, b.entity.replace("_", " "))
        unit = f" {b.unit}" if b.unit else ""
        direction = "up" if b.latest > b.previous else "down"
        parts.append(f"{label} {b.previous:g} -> {b.latest:g}{unit} ({direction})")
        labels.append(label)
    return "Since your previous report: " + "; ".join(parts) + ".", labels
