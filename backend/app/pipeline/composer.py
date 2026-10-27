"""User-facing answer assembly. Lookups stay short; reasoning keeps evidence and follow-ups."""

from __future__ import annotations

import logging
import re

from app.contracts.common import IntentType, KnowledgeScope
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

logger = logging.getLogger("cura.composer")

_HANDLED_LLM = re.compile(
    r"\b(symptoms?|medication|supplement|previous report|changed over time|what does .{0,24} mean|what is a healthy)\b",
    re.I,
)


def _llm_handling(text: str) -> tuple[str | None, str | None]:
    if re.search(r"\b(symptoms?|medication|supplement)\b", text, re.I):
        return "CLINICAL_CONTEXT", "CONTINUE_INTERPRETATION"
    if re.search(r"\bprevious|changed over time|trend\b", text, re.I):
        return "YES_NO", "TREND"
    if re.search(r"\bwhat does .{0,24} mean\b|\bwhat is a healthy\b", text, re.I):
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


_OVERVIEW_INTENTS = {
    IntentType.report_explanation,
    IntentType.broad_health_summary,
    IntentType.health_scenario,
    IntentType.bio_ai_explanation,
    IntentType.bio_ai_score,
}


def _journey_follow_ups(
    plan: QueryPlan,
    context: HealthContext,
    *,
    llm_follow_ups: list[str] | None,
    history: list[str] | None,
    shown: list[str] | None,
    keep: list[FollowUpSuggestion] | None = None,
    member_findings: tuple[list, list] | None = None,
) -> list[FollowUpSuggestion] | None:
    """Grounded follow-ups for personal answers (followup_generator); None keeps the old chips."""
    if context.status == "ambiguous" or plan.knowledge_scope != KnowledgeScope.personal:
        return None
    markers, risks = list(context.markers or []), list(context.bio_ai_risks or [])
    if not (markers or risks) and member_findings:
        markers, risks = list(member_findings[0]), list(member_findings[1])
    from app.pipeline.followup_generator import (
        FollowUpBrief, build_brief, fallback_questions, select_followups, to_suggestions,
    )

    if not (markers or risks):
        # No blood or Bio-AI report on record: useful general questions, never personal claims.
        general = fallback_questions(
            FollowUpBrief(asked=list(history or []), shown=list(shown or [])), count=3, current=plan.raw_message,
        )
        return to_suggestions(general, personal=False) if general else None
    brief = build_brief(
        markers=markers,
        risks=risks,
        comparisons=list(context.comparisons or []),
        asked=list(history or []),
        focus_keys={k for k in [plan.topic, context.resolved_topic, *(plan.requested_metrics or [])] if k},
        shown=list(shown or []),
        has_lifestyle=bool(getattr(context, "lifestyle", None) or getattr(context, "questionnaire", None)),
    )
    overview = plan.intent in _OVERVIEW_INTENTS and len(context.markers or []) + len(context.bio_ai_risks or []) > 2
    # A clinical-context question (its reply continues the interpretation) and the
    # "Show all results" action are flows of their own; grounded questions fill the rest.
    kept = list(keep or [])
    questions = select_followups(
        brief,
        current_question=plan.raw_message,
        model_questions=list(llm_follow_ups or []),
        count=(4 if overview else 3) - len(kept),
    )
    if len(kept) + len(questions) < 2:
        return None
    # The member's own next questions first; Cura's clinical-context question last.
    return [*to_suggestions(questions), *kept]


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
        history: list[str] | None = None,
        shown_follow_ups: list[str] | None = None,
        member_findings: tuple[list, list] | None = None,
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
        spec = plan.task_contract or {}
        explain_only = spec.get("goal") in {"explain", "interpret"} and not spec.get("recommendations_requested")
        question, chips = discipline_follow_ups(
            seeded,
            experience,
            answer_turn=answer_turn,
            extra_chips=[] if explain_only else extra_chips,
            allow_default_question=bool(context.markers)
            and context.knowledge_scope == KnowledgeScope.personal
            and not explain_only,
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
        if explain_only and not answer_turn:
            question = []
            chips = []
            symptom = next(
                (item for item in seeded if "symptom" in (item.text or "").lower()),
                None,
            )
            if symptom and plan.knowledge_scope == KnowledgeScope.personal:
                combined = [symptom]
            else:
                combined = extras[:1]
            # No chip is better than a generic "what does this topic mean" chip.
        elif response_plan.kind == "report_overview":
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
        from app.pipeline.narrative import format_units_in_text

        cleaned = format_units_in_text(sanitize_internal_ids(prefer_report_range(answer or "", context))) or ""
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
        if response_plan.kind == "report_overview" and not (model_wrote and cleaned.strip()):
            from app.pipeline.report_explainer import explain_blood_report

            counts = context.in_range_summary
            explained = explain_blood_report(
                list(context.markers or []),
                in_range=counts.in_range if counts else None,
                out_of_range=counts.out_of_range if counts else None,
            ) if context.markers else response_plan.summary
            text = f"{response_plan.direct_answer} {explained}".strip()
        if not text:
            text = strip_lookup_disclaimers(cleaned, presentation.mode) or cleaned
        bio_turn = plan.intent.value.startswith("bio_ai")
        change_line = None if model_wrote or bio_turn else _change_summary(context)
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
        from app.pipeline.answer_shape import separate_answer_layout

        text = separate_answer_layout(text)
        if presentation.summary:
            presentation.summary = separate_answer_layout(presentation.summary)
        if presentation.overall_summary:
            presentation.overall_summary = separate_answer_layout(presentation.overall_summary)
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

        from app.pipeline.answer_shape import omit_duplicate_closing_offer

        offers = [item.text for item in combined if getattr(item, "text", None)]
        text = omit_duplicate_closing_offer(separate_answer_layout(text), offers)
        if presentation.summary:
            presentation.summary = omit_duplicate_closing_offer(separate_answer_layout(presentation.summary), offers)
        from app.pipeline.grounding import drop_unverified_claims

        text = drop_unverified_claims(text, context)
        from app.pipeline.answer_polish import polish_answer

        intent_value = getattr(context.intent, "value", None)
        text = polish_answer(text, context, intent=intent_value)
        # The app renders these fields rather than `text`, so they get the same fixes.
        for name in ("summary", "overall_summary", "interpretation"):
            value = getattr(presentation, name, None)
            if value:
                # The warning goes in the main text only, so it is never shown twice.
                setattr(presentation, name, polish_answer(
                    value, context, intent=intent_value, add_notes=name != "interpretation",
                ))
        # A reply to Cura's own question stays lean, and "show me my report" keeps its
        # concrete actions; every other personal answer gets grounded follow-ups.
        try:
            journey = None if answer_turn or response_plan.kind == "report_overview" else _journey_follow_ups(
                plan, context, llm_follow_ups=llm_follow_ups, history=history, shown=shown_follow_ups,
                # The clinical-context question is asked once per conversation, not after every answer.
                keep=[
                    item for item in combined
                    if item.expected_reply_type == "CLINICAL_CONTEXT" and item.text not in (shown_follow_ups or [])
                ][:1],
                member_findings=member_findings,
            )
        except Exception:  # noqa: BLE001 - suggestions must never break or delay the answer
            logger.warning("follow_up_generation_failed", exc_info=True)
            journey = None
        if journey is not None:
            combined = journey
            presentation.suggestion_chips = [item.text for item in journey]
            presentation.follow_up = None
        elif shown_follow_ups and not answer_turn:
            # Never offer a question this conversation already suggested.
            combined = [item for item in combined if item.text not in shown_follow_ups]
            presentation.suggestion_chips = [t for t in presentation.suggestion_chips if t not in shown_follow_ups]
        definition = bool(re.search(r"\bwhat is\b", plan.raw_message or "", re.I) and not re.search(r"\bmy\b", plan.raw_message or "", re.I))
        if not combined and not answer_turn and context.status != "ambiguous" and not definition:
            # Never an empty row: a few general, clinically safe questions.
            from app.pipeline.followup_generator import FollowUpBrief, fallback_questions, to_suggestions

            general = fallback_questions(
                FollowUpBrief(asked=list(history or []), shown=list(shown_follow_ups or [])),
                count=3, current=plan.raw_message,
            )
            combined = to_suggestions(general, personal=False)
            presentation.suggestion_chips = [item.text for item in combined]
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
