"""User-facing answer assembly. Lookups stay short; reasoning keeps evidence and follow-ups."""

from __future__ import annotations

import re

from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.contracts.diagnostics import TestingOption
from app.contracts.presentation import ResponseMode, StructuredResponse
from app.contracts.query import QueryPlan
from app.llm.models import LLMStructuredOutput
from app.pipeline.presentation import (
    build_structured_response,
    flatten_structured_response,
    is_list_only,
    sanitize_internal_ids,
    strip_lookup_disclaimers,
    attach_presentation_personalization,
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
    ) -> tuple[str, list[FollowUpSuggestion], StructuredResponse]:
        suggestions = [item for item in (follow_ups or []) if item.handling_path]
        extras: list[FollowUpSuggestion] = []
        existing = {item.text.strip().lower() for item in suggestions}
        for question in (llm_follow_ups or [])[:2]:
            value = (question or "").strip()
            if not value or value.lower() in existing or not _HANDLED_LLM.search(value):
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
            existing.add(value.lower())
        combined = (extras + suggestions)[:2]
        if is_list_only(plan.raw_message):
            combined = combined[:1]
        if plan.conversation_turn == "ANSWER_TO_ASSISTANT":
            combined = []
        follow_text = combined[0].text if combined else None
        cleaned = sanitize_internal_ids(answer or "")
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
        if presentation.mode in {ResponseMode.single_value, ResponseMode.result_list}:
            combined = combined[:1]
        text = flatten_structured_response(presentation, raw_answer=cleaned)
        if not text:
            text = strip_lookup_disclaimers(cleaned, presentation.mode) or cleaned
        if testing_option:
            presentation.testing_option = testing_option
        presentation = attach_presentation_personalization(presentation, context, plan)
        if presentation.mode.value == "CLINICIAN_HANDOFF" and presentation.summary:
            text = presentation.summary
        if presentation.quiet_mode and presentation.mode.value == "QUIET_UPDATE":
            if not re.search(r"nothing new stands out|would not suggest changing", text, re.I):
                text = (
                    "Nothing new stands out in these results. The available measurements look stable, "
                    "so I would not suggest changing anything based on this report alone."
                )
                presentation.summary = text
        return text, combined, presentation
