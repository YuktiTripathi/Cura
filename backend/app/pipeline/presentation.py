"""Compose user-facing presentation. Does not change retrieval or medical reasoning."""

from __future__ import annotations

import re
from datetime import date, datetime

from app.contracts.common import IntentType, KnowledgeScope, MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.presentation import PresentedFinding, ResponseMode, StructuredResponse, SummaryStyle
from app.contracts.query import QueryPlan
from app.pipeline.health_domains import DOMAIN_CODES, domain_for_code
from app.pipeline.lab_parameters import FAMILY_QUERY_KEYS, display_name_for, is_lab_key
from app.pipeline.clinician_handoff import format_handoff
from app.pipeline.narrative import (
    build_narrative_summary,
    canonical_display_label,
    canonical_marker_key,
    dedupe_markers,
    dedupe_missing,
    flatten_narrative,
    format_unit,
    summary_style_for,
    usable_llm_overview,
    wants_narrative_summary,
    wants_raw_snapshot,
)

_MONTH_ABBR = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
_LIST_ONLY = re.compile(
    r"\b(list only|just list|only list|without (?:an |any )?(?:explanation|interpretation)|"
    r"just (?:the |my )?results|show (?:me )?(?:only )?(?:the )?values?)\b",
    re.I,
)
_SYNTHESIS = re.compile(
    r"\b(fit together|how (?:are|do) (?:they|these)|connected|pattern|overall|picture|"
    r"consistent|in common|cluster|together)\b",
    re.I,
)
_MEANING = re.compile(
    r"\b(what does (?:this|that|it|my .{0,32}) mean|explain|interpret|understand|"
    r"how should i read|why|are they consistent)\b",
    re.I,
)
_INTERNAL_ID = re.compile(
    r"\b(?:eval-blood-\d+|blood-j-\d+|blood-\d+|bioai-[a-z0-9]+|bio-9|doc-[a-z0-9]+)\b",
    re.I,
)
_REPORT_PAREN = re.compile(
    r"\s*\((?:report|assessment)\s+(?:id\s+)?(?:blood|bioai|bio-ai|eval-blood|doc)[-_][^)]+\)",
    re.I,
)
_REPORT_CLAUSE = re.compile(
    r"\b(?:report|assessment)\s+(?:id\s+)?(?:blood|bioai|bio-ai|eval-blood|doc)[-_][a-z0-9-]+\b",
    re.I,
)
_LOOKUP_DISCLAIMER = re.compile(
    r"\s*(?:This is from your blood report, not a diagnosis\.?|"
    r"This is measured data, not a diagnosis\.?(?: A clinician can review whether follow-up is needed\.?)?|"
    r"This is not a diagnosis\.?(?: Discuss results with a clinician)?\.?|"
    r"I cannot say this is 'normal' as a diagnosis;[^.]*\.)",
    re.I,
)
_FLAG_STATUS = {
    MarkerFlag.normal.value: "in_range",
    MarkerFlag.high.value: "high",
    MarkerFlag.low.value: "low",
    MarkerFlag.critical.value: "critical",
    MarkerFlag.missing.value: "missing",
    MarkerFlag.unknown.value: "unknown",
}
_SOURCE_KIND = {
    "blood_report": "blood report",
    "bio_ai_report": "Bio-AI assessment",
    "questionnaire": "health questionnaire",
    "user_uploaded": "uploaded document",
    "uploaded_document": "uploaded document",
}
_HEADLINES = {
    "glycemic_health": "Glycemic health",
    "metabolic_health": "Metabolic health",
    "lipid_health": "Lipid health",
    "cardiovascular_health": "Cardiovascular health",
    "blood_pressure_health": "Blood pressure",
    "kidney_health": "Kidney health",
    "liver_health": "Liver health",
    "thyroid_health": "Thyroid health",
    "red_cell_anaemia_health": "Red cell and anaemia context",
    "iron_status": "Iron status",
    "vitamin_b12_folate_status": "Vitamin B12 and folate",
    "vitamin_d_bone_mineral_health": "Vitamin D and bone minerals",
    "inflammation": "Inflammation",
    "white_cell_immune_profile": "White cell immune profile",
    "platelet_coagulation_health": "Platelet and coagulation health",
    "nutrition_micronutrient_health": "Nutrition and micronutrients",
    "weight_body_composition": "Weight and body composition",
    "lifestyle_recovery": "Lifestyle and recovery",
    "overall_health": "Health overview",
    "energy_fatigue_context": "Energy and fatigue context",
    "thyroid_function": "Thyroid health",
    "kidney_function": "Kidney health",
    "liver_function": "Liver health",
}
_PROFILE_CONTEXT = frozenset({"bmi", "waist", "weight", "height", "body_fat", "lean_mass", "activity", "sleep", "diet"})
_CONTEXT_LEAK = re.compile(
    r"(?:BMI|Body mass index|Waist circumference|Activity|Sleep|Diet) was not[^.]*\.\s*",
    re.I,
)


def format_user_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    if not isinstance(value, date):
        return str(value)
    return f"{value.day} {_MONTH_ABBR[value.month]} {value.year}"


def bio_ai_source_label(source_line: str | None) -> str:
    raw = (source_line or "").strip().lower().replace("-", "_")
    if raw in {"advanced_bio_ai", "advanced"}:
        return "Advanced Bio-AI assessment"
    if raw in {"bio_ai", "bioai", ""}:
        return "Bio-AI assessment"
    return re.sub(r"[_-]+", " ", source_line or "Bio-AI assessment").strip().title()


def user_source_caption(
    source_type: str | None,
    when=None,
    *,
    latest: bool = True,
    source_line: str | None = None,
) -> str:
    if source_type in {"bio_ai_report", "bio_ai"} and source_line:
        kind = bio_ai_source_label(source_line)
        prefix = ""
    else:
        kind = _SOURCE_KIND.get(source_type or "", "health record")
        prefix = "Latest " if latest and kind in {"blood report", "Bio-AI assessment", "health questionnaire"} else (
            "Previous " if not latest and kind == "blood report" else ""
        )
        kind = f"{prefix}{kind}".strip()
        kind = kind[:1].upper() + kind[1:] if kind else kind
    dated = format_user_date(when)
    if dated:
        return f"{kind} · {dated}"
    return kind


def uploaded_source_caption(*, page: int | None = None, section: str | None = None) -> str:
    parts = ["Uploaded report"]
    if section:
        parts.append(section)
    if page:
        parts.append(f"page {page}")
    return " · ".join(parts)


def is_list_only(message: str | None) -> bool:
    return bool(_LIST_ONLY.search(message or ""))


def infer_response_mode(plan: QueryPlan, context: HealthContext, message: str | None = None) -> ResponseMode:
    text = message or plan.raw_message or ""
    if context.status == "safety_block":
        return ResponseMode.safety
    if is_list_only(text):
        return ResponseMode.result_list
    if wants_raw_snapshot(text, plan):
        return ResponseMode.result_list
    if wants_narrative_summary(text, plan):
        return ResponseMode.health_overview
    if context.quiet and context.quiet.active and re.search(r"\b(change anything|need to change|stable)\b", text, re.I):
        return ResponseMode.quiet_update
    ops = {str(item).upper() for item in (plan.operations or [])}
    if plan.operation:
        ops.add(plan.operation.upper())
    if "PREPARE_CLINICIAN_DISCUSSION" in ops or re.search(
        r"\b(summarize (?:this |it )?for my doctor|what should i ask my doctor)\b", text, re.I
    ):
        return ResponseMode.clinician_handoff
    if "ASSESS_GOAL_PROGRESS" in ops or plan.intent == IntentType.health_goal_progress:
        return ResponseMode.goal_progress
    semantic_mode = _semantic_mode(context)
    if semantic_mode is not None:
        return semantic_mode
    domains = list(plan.domains or context.domains or [])
    selectors = {str(item).upper() for item in (plan.selectors or [])}
    wants_meaning = bool(_MEANING.search(text) or _SYNTHESIS.search(text))
    if ops & {"TREND", "VERIFY_PREMISE"}:
        return ResponseMode.trend
    if "COMPARE" in ops:
        return ResponseMode.comparison
    specific = [code for code in domains if code not in {"overall_health", "energy_fatigue_context"}]
    if "overall_health" in domains or (
        plan.intent in {IntentType.broad_health_summary, IntentType.health_scenario} and not specific
    ):
        if not wants_raw_snapshot(text, plan):
            return ResponseMode.health_overview
    if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and not wants_meaning:
        return ResponseMode.result_list
    bio_intent = plan.intent == IntentType.bio_ai_score or context.intent == IntentType.bio_ai_score
    risks = list(context.bio_ai_risks or [])
    if bio_intent and not wants_meaning:
        if len(risks) > 1:
            return ResponseMode.result_list
        if len(risks) == 1 and not domains:
            return ResponseMode.single_value
    if wants_meaning:
        return ResponseMode.interpretation
    if domains:
        return ResponseMode.domain_summary
    display = list(plan.display_entities or [])
    markers = list(context.markers or [])
    if len(display) > 1 or len(markers) > 1 or len(risks) > 1:
        return ResponseMode.result_list
    return ResponseMode.single_value


_FOCUSED_SHAPES = {
    "EXPLANATION",
    "POSSIBLE_EXPLANATIONS",
    "PERSONALIZED_ASSESSMENT",
    "ACTION_PLAN",
    "RISK_EXPLANATION",
    "PRIORITIZATION",
}


def _semantic_mode(context: HealthContext) -> ResponseMode | None:
    """Response shape follows the user's reasoning goal, not the routed intent label.

    Only focused personal answers are decided here; lookups, comparisons, overviews and
    every special mode keep the existing rules.
    """
    semantic = getattr(context, "semantic_plan", None) or {}
    shape = semantic.get("response_shape")
    if shape not in _FOCUSED_SHAPES or semantic.get("personalization") != "REQUIRED":
        return None
    if "overall_health" in (semantic.get("health_topics") or []):
        return None
    if context.knowledge_scope != KnowledgeScope.personal:
        return None
    return ResponseMode.interpretation


def display_entity_codes(plan: QueryPlan, context: HealthContext) -> list[str]:
    codes = [key for key in (plan.display_entities or []) if key]
    if codes:
        return list(dict.fromkeys(codes))
    requested = [
        key
        for key in (plan.requested_metrics or [])
        if is_lab_key(key) and key not in (plan.reasoning_context or [])
    ]
    if requested:
        return list(dict.fromkeys(requested))
    return list(dict.fromkeys(m.key for m in context.markers if m.key))


def reasoning_context_codes(plan: QueryPlan) -> list[str]:
    return list(dict.fromkeys(plan.reasoning_context or []))


def _status_for(flag) -> str:
    value = getattr(flag, "value", flag)
    return _FLAG_STATUS.get(str(value), str(value) if value else "unknown")


def _has_measured_value(marker) -> bool:
    """A report row is showable only when a number was actually retrieved."""
    if getattr(marker, "value", None) is None:
        return False
    return _status_for(getattr(marker, "flag", None)) != "missing"


def _finding_from_marker(marker, *, latest: bool = True) -> PresentedFinding:
    when = marker.measured_at
    value = None if marker.value is None else f"{marker.value}"
    stored_name = (getattr(marker, "name", None) or "").strip()
    canonical = canonical_display_label(marker)
    return PresentedFinding(
        label=stored_name or canonical,
        value=value,
        unit=format_unit(marker.unit),
        status=_status_for(marker.flag),
        source_type="blood_report",
        source_date=str(when)[:10] if when else None,
        source_id=marker.report_id,
        source_label=user_source_caption("blood_report", when, latest=latest),
        canonical_key=canonical_marker_key(marker),
        numeric_value=marker.value,
        reference_low=marker.reference_low,
        reference_high=marker.reference_high,
    )


def _headline(plan: QueryPlan, context: HealthContext, mode: ResponseMode) -> str:
    for code in list(plan.domains or []) + [plan.topic]:
        if code and code in _HEADLINES:
            return _HEADLINES[code]
        domain = domain_for_code(code) if code else None
        if domain:
            return _HEADLINES.get(domain.code, domain.code.replace("_", " ").title())
    if mode == ResponseMode.health_overview:
        return "Health overview"
    if mode == ResponseMode.result_list and {str(s).upper() for s in (plan.selectors or [])} & {"HIGH"}:
        return "High markers"
    if mode == ResponseMode.result_list and {str(s).upper() for s in (plan.selectors or [])} & {"ABNORMAL"}:
        return "Results outside range"
    if context.resolved_topic_name:
        return context.resolved_topic_name
    if context.markers:
        return context.markers[0].name
    return "Results"


def _include_interpretation(mode: ResponseMode, message: str | None) -> bool:
    if is_list_only(message):
        return False
    if mode in {ResponseMode.single_value, ResponseMode.result_list}:
        return False
    if mode == ResponseMode.domain_summary:
        return bool(_MEANING.search(message or "") or _SYNTHESIS.search(message or ""))
    return mode in {
        ResponseMode.interpretation,
        ResponseMode.comparison,
        ResponseMode.trend,
        ResponseMode.health_overview,
        ResponseMode.safety,
        ResponseMode.goal_progress,
        ResponseMode.clinician_handoff,
        ResponseMode.quiet_update,
        ResponseMode.personal_interpretation,
    }


def _visible_markers(plan: QueryPlan, context: HealthContext) -> list:
    wanted = set(display_entity_codes(plan, context))
    reasoning = set(reasoning_context_codes(plan)) | _PROFILE_CONTEXT
    markers = list(context.markers or [])
    stamps = {(marker.key, str(getattr(marker, "measured_at", "") or "")) for marker in markers if marker.key}
    if len(stamps) <= len({marker.key for marker in markers if marker.key}):
        markers = dedupe_markers(markers)
    spec = plan.task_contract or {}
    card_keys = set(spec.get("card_keys") or [])
    if not spec.get("broad_summary") and spec.get("goal") in {"advise", "explain", "interpret", "lookup"}:
        if card_keys:
            scoped = [m for m in markers if m.key in card_keys or canonical_marker_key(m) in card_keys]
            return (scoped[:3] if spec.get("personal_context") == "optional" else scoped[:6])
        if len(markers) > 6:
            return []
    if plan.intent == IntentType.report_explanation and spec.get("goal") == "interpret":
        abnormal = [
            marker
            for marker in markers
            if getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", "")) in {"low", "high", "critical"}
        ]
        if abnormal:
            from app.pipeline.health_domains import domain_for_entity

            grouped: dict[str, list] = {}
            for marker in abnormal:
                domain = domain_for_entity(marker.key)
                grouped.setdefault(domain.code if domain else "other", []).append(marker)
            chosen = []
            for group in grouped.values():
                chosen.append(group[0])
                if len(chosen) >= 6:
                    break
            return chosen[:6]
    if not wanted:
        return [m for m in markers if canonical_marker_key(m) not in reasoning]
    matched = [m for m in markers if m.key in wanted or canonical_marker_key(m) in wanted]
    if matched:
        return matched
    return [m for m in markers if m.key not in reasoning]


def preview_findings(plan: QueryPlan, context: HealthContext, *, limit: int = 6) -> list[PresentedFinding]:
    """The values the user explicitly asked about, ready to show before the explanation exists.

    Broad questions ("summarize my health") get no preview: a wall of values is not an answer.
    """
    explicit = [key for key in (plan.display_entities or []) if key] or [
        key for key in (plan.requested_metrics or []) if is_lab_key(key) and key not in (plan.reasoning_context or [])
    ]
    if not explicit or not context.markers:
        return []
    return [_finding_from_marker(marker) for marker in _visible_markers(plan, context)[:limit]]


def _uncertainties(plan: QueryPlan, context: HealthContext) -> list[str]:
    display = set(display_entity_codes(plan, context))
    present = {canonical_marker_key(marker) for marker in context.markers or []}
    rows: list[str] = []
    # A gap is announced only for a marker the question actually asked to see.
    # An empty display list must not turn every unretrieved marker into "unavailable".
    if not display:
        return []
    for item in dedupe_missing(list(context.missing or []), present):
        if item.key not in display or item.scope == "optional":
            continue
        if item.key in (plan.reasoning_context or []) or item.key in DOMAIN_CODES or item.key in FAMILY_QUERY_KEYS:
            continue
        if item.reason in {"not_in_reports", "not_present", "no_reports"}:
            label = item.name or display_name_for(item.key)
            if item.key == "cholesterol" and present & {"ldl", "hdl", "triglycerides"}:
                label = "Total cholesterol"
            rows.append(f"{label} isn't included in this report.")
    return list(dict.fromkeys(rows))[:4]


_DIAGNOSIS_OF_SCORE = re.compile(
    r"establish a diagnosis|is (?:this|that) a diagnosis|does (?:this|that) (?:mean|show) i have|"
    r"diagnose me|diagnosis hai",
    re.I,
)
_NOT_CONCLUDE = re.compile(r"\bnot conclude\b|\bwhat (?:can|should) i conclude\b", re.I)
_SCORE_NOT_DIAGNOSIS = (
    "A Bio-AI score is a risk assessment, not a diagnosis. "
    "It does not show that you have or do not have this condition."
)
_ONE_RESULT_LIMIT = (
    "One stored result is not a diagnosis and does not show the cause. "
    "Only the stored value, unit, date, and reference range can be used."
)


def _answer_limits(message: str | None, findings: list) -> list[str]:
    notes: list[str] = []
    text = message or ""
    bio = any(getattr(item, "source_type", None) == "bio_ai_report" for item in findings)
    if _DIAGNOSIS_OF_SCORE.search(text):
        if bio:
            notes.append(_SCORE_NOT_DIAGNOSIS)
        elif findings:
            notes.append(
                "A laboratory result is not a diagnosis. It does not show that you have or do not have a condition."
            )
    if _NOT_CONCLUDE.search(text):
        notes.append(_ONE_RESULT_LIMIT)
        if findings and all(item.reference_low is None and item.reference_high is None for item in findings):
            notes.append("No reference range is stored, so this result cannot be called high or low.")
    return notes


def _score_dump(text: str | None) -> bool:
    value = text or ""
    return "Bio-AI assessment shows" in value or "• **" in value


def _extract_interpretation(answer: str, mode: ResponseMode, message: str | None) -> str | None:
    if not _include_interpretation(mode, message):
        return None
    text = sanitize_internal_ids(answer or "").strip()
    if not text:
        return None
    return strip_lookup_disclaimers(text, mode)


def build_structured_response(
    answer: str,
    *,
    plan: QueryPlan,
    context: HealthContext,
    follow_up: str | None = None,
    llm_themes: list[dict] | None = None,
    llm_overall: str | None = None,
) -> StructuredResponse:
    message = plan.raw_message
    mode = infer_response_mode(plan, context, message)
    if context.status == "ambiguous":
        cleaned = sanitize_internal_ids(answer or "")
        return StructuredResponse(
            mode=ResponseMode.result_list,
            headline=None,
            summary=cleaned,
            follow_up=follow_up,
            display_entities=display_entity_codes(plan, context),
            reasoning_context=reasoning_context_codes(plan),
        )
    style = summary_style_for(message, plan)
    if style == SummaryStyle.narrative_health_summary:
        overall, themes, raw, next_action = build_narrative_summary(
            context,
            plan=plan,
            message=message,
            llm_overall=usable_llm_overview(llm_overall) or usable_llm_overview(answer),
            llm_themes=llm_themes,
        )
        panel = list(getattr(context, "panel_markers", None) or [])
        if panel:
            raw = [_finding_from_marker(marker, latest=True) for marker in dedupe_markers(panel)]
        labeled = {
            canonical_marker_key(marker): _finding_from_marker(marker)
            for marker in dedupe_markers(list(context.markers or []))
        }
        raw = [labeled.get(item.canonical_key or "", item) for item in raw]
        for theme in themes:
            theme.related_findings = [labeled.get(item.canonical_key or "", item) for item in theme.related_findings]
        card_findings = []
        if not themes and (plan.task_contract or {}).get("primary_source") in {"blood_report", "bio_ai"}:
            card_findings = [
                _finding_from_marker(marker, latest=True)
                for marker in _visible_markers(plan, context)
                if _has_measured_value(marker)
            ]
            for risk in context.bio_ai_risks or []:
                if getattr(risk, "score", None) is None:
                    continue
                card_findings.append(PresentedFinding(
                    label=getattr(risk, "name", None) or risk.code,
                    value=f"{risk.score:g}",
                    status=str(getattr(risk, "status", None) or ""),
                    source_type="bio_ai_report",
                ))
        return StructuredResponse(
            mode=ResponseMode.health_overview,
            headline=None,
            summary=overall,
            overall_summary=overall,
            findings=card_findings,
            interpretation=None,
            uncertainties=[],
            next_steps=[],
            follow_up=follow_up,
            display_entities=list(
                dict.fromkeys(
                    item.canonical_key
                    for theme in themes
                    for item in theme.related_findings
                    if item.canonical_key
                )
            ),
            reasoning_context=reasoning_context_codes(plan),
            summary_style=style,
            themes=themes,
            raw_findings=raw,
        )
    if style == SummaryStyle.raw_health_snapshot:
        raw = [
            _finding_from_marker(marker, latest=plan.intent != IntentType.previous_result)
            for marker in dedupe_markers(list(context.markers or []))
            if _has_measured_value(marker)
        ]
        return StructuredResponse(
            mode=ResponseMode.result_list,
            headline="All retrieved results",
            summary="Here are the measurements from the retrieved report.",
            findings=raw,
            interpretation=None,
            uncertainties=_uncertainties(plan, context),
            next_steps=[],
            follow_up=follow_up,
            display_entities=display_entity_codes(plan, context),
            reasoning_context=reasoning_context_codes(plan),
            summary_style=style,
            raw_findings=raw,
        )
    findings = [
        _finding_from_marker(marker, latest=plan.intent != IntentType.previous_result)
        for marker in _visible_markers(plan, context)
        if _has_measured_value(marker)
    ]
    allowed_bioai: set[str] = set()
    for code in list(plan.domains or []) + list(context.domains or []):
        domain = domain_for_code(code)
        if domain:
            allowed_bioai.update(domain.bioai_domains)
    for risk in context.bio_ai_risks or []:
        if plan.intent not in {
            IntentType.bio_ai_score,
            IntentType.bio_ai_explanation,
            IntentType.bio_ai_comparison,
            IntentType.health_scenario,
            IntentType.broad_health_summary,
            IntentType.report_explanation,
        } and context.intent not in {
            IntentType.bio_ai_score,
            IntentType.bio_ai_explanation,
            IntentType.bio_ai_comparison,
            IntentType.health_scenario,
        }:
            break
        if mode == ResponseMode.domain_summary and allowed_bioai and (risk.code or "").lower() not in allowed_bioai:
            continue
        if mode in {
            ResponseMode.single_value,
            ResponseMode.result_list,
            ResponseMode.comparison,
            ResponseMode.trend,
            ResponseMode.health_overview,
            ResponseMode.interpretation,
            ResponseMode.domain_summary,
        }:
            score = None if risk.score is None else f"{risk.score:g}" if isinstance(risk.score, float) else str(risk.score)
            findings.append(
                PresentedFinding(
                    label=risk.name or risk.code or "Assessment",
                    value=score,
                    status=risk.status or None,
                    source_type="bio_ai_report",
                    source_date=str(risk.measured_at)[:10] if getattr(risk, "measured_at", None) else None,
                    source_id=risk.report_id,
                    source_label=user_source_caption("bio_ai_report", getattr(risk, "measured_at", None), source_line=getattr(risk, "source_line", None)),
                )
            )
    def _attention(status: str | None) -> int:
        value = (status or "").lower()
        if value in {"critical", "very high", "high"}:
            return 0
        if value in {"moderate", "elevated", "medium"}:
            return 1
        return 2

    risks = [item for item in findings if item.source_type == "bio_ai_report"]
    others = [item for item in findings if item.source_type != "bio_ai_report"]
    if risks:
        findings = sorted(risks, key=lambda item: _attention(item.status)) + others
    explicit_dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", message or "")
    if (
        mode == ResponseMode.single_value
        and len(findings) > 1
        and not explicit_dates
        and not (plan.domains or [])
        and context.intent != IntentType.bio_ai_score
    ):
        findings = findings[:1]
    if not findings and answer and not _include_interpretation(mode, message):
        return StructuredResponse(
            mode=mode if mode != ResponseMode.domain_summary else ResponseMode.single_value,
            headline=None,
            summary=sanitize_internal_ids(answer),
            follow_up=follow_up,
            display_entities=display_entity_codes(plan, context),
            reasoning_context=reasoning_context_codes(plan),
        )
    headline = _headline(plan, context, mode)
    if (context.intent == IntentType.bio_ai_score or plan.intent == IntentType.bio_ai_score) and context.bio_ai_risks:
        headline = "Your Bio-AI Report"
    asks_explanation = bool(_MEANING.search(message or "") or re.search(r"\bwhat should i know\b", message or "", re.I))
    if asks_explanation and plan.intent not in {IntentType.bio_ai_score, IntentType.bio_ai_explanation}:
        findings = [
            item
            for item in findings
            if item.source_type != "bio_ai_report" and (item.status or "") in {"high", "low", "critical"}
        ][:5]
    interpretation = _extract_interpretation(answer, mode, message)
    bio_report = (plan.intent == IntentType.bio_ai_score or context.intent == IntentType.bio_ai_score) and bool(
        context.bio_ai_risks
    )
    if bio_report:
        interpretation = None
    summary = None
    goal = (plan.task_contract or {}).get("goal") or ""
    keep_explanation = goal not in {"", "lookup"}
    if mode in {ResponseMode.single_value, ResponseMode.result_list, ResponseMode.domain_summary} and findings:
        if explicit_dates and findings:
            parts = []
            for item in findings:
                unit = f" {item.unit}" if item.unit else ""
                when = f" on {item.source_date}" if item.source_date else ""
                status = f" ({item.status})" if item.status in {"high", "low", "critical", "normal"} else ""
                parts.append(f"{item.label} {item.value}{unit}{status}{when}".strip())
            summary = "Stored results for the requested dates: " + "; ".join(parts)
            q_bits = []
            lowered = (message or "").lower()
            for q in context.questionnaire or []:
                question = (q.question or "").strip().lower()
                key_phrase = (q.question_key or "").replace("_", " ")
                if q.value in (None, ""):
                    continue
                if not ((question and question[:48] in lowered) or (key_phrase and key_phrase in lowered)):
                    continue
                recorded = getattr(q, "recorded_at", None)
                dated = "" if recorded else " Completion date is not stored."
                q_bits.append(f"Questionnaire answer: {q.value}.{dated}")
            if q_bits:
                summary += " " + " ".join(q_bits[:2])
                summary += " The questionnaire answer is separate from the laboratory result."
            if re.search(r"reference range|not conclude", message or "", re.I) and all(
                item.reference_low is None and item.reference_high is None for item in findings
            ):
                summary += " No reference range is stored for that result."
            interpretation = None
        elif re.search(r"reference range", message or "", re.I) and findings and all(
            item.reference_low is None and item.reference_high is None for item in findings
        ):
            item = findings[0]
            when = f" on {item.source_date}" if item.source_date else ""
            unit = f" {item.unit}" if item.unit else ""
            summary = f"{item.label} {item.value}{unit}{when}. No reference range is stored for that result."
            interpretation = None
        elif mode == ResponseMode.single_value and findings and keep_explanation:
            summary = sanitize_internal_ids(answer or "") or None
            interpretation = None
        elif mode == ResponseMode.single_value and findings:
            item = findings[0]
            unit = f" {item.unit}" if item.unit else ""
            status = f" ({item.status.replace('_', ' ')})" if item.status and item.status not in {"unknown"} else ""
            prefix = "Your previous" if plan.intent == IntentType.previous_result else "Your latest"
            summary = f"{prefix} {item.label} is {item.value}{unit}{status}.".replace("  ", " ")
            interpretation = None
        elif context.intent == IntentType.bio_ai_score or plan.intent == IntentType.bio_ai_score:
            prose = sanitize_internal_ids(answer or "")
            summary = None if _score_dump(prose) else prose or None
            interpretation = None
            if summary and "\n\n" in summary:
                # A written explanation (report_explainer): show it as prose; the scores
                # stay on the cards instead of being repeated as raw lines.
                mode = ResponseMode.interpretation
        elif mode == ResponseMode.result_list:
            prose = sanitize_internal_ids(answer or "")
            if (asks_explanation or keep_explanation) and prose and not _score_dump(prose):
                summary = prose
            else:
                summary = f"{headline} from your retrieved records."
            interpretation = None
        else:
            prose = sanitize_internal_ids(answer or "")
            if (asks_explanation or keep_explanation) and prose and not _score_dump(prose):
                summary = prose
                interpretation = None
            else:
                summary = f"{headline} using the measurements available in your latest records."
    elif answer and mode in {ResponseMode.interpretation, ResponseMode.comparison, ResponseMode.trend, ResponseMode.health_overview}:
        prose = sanitize_internal_ids(answer)
        if bio_report:
            summary = None if _score_dump(prose) else prose or None
            interpretation = None
        else:
            summary = prose or None
            interpretation = None
    uncertainties = _uncertainties(plan, context)
    if plan.intent in {IntentType.bio_ai_score, IntentType.bio_ai_explanation} or context.intent in {
        IntentType.bio_ai_score,
        IntentType.bio_ai_explanation,
    }:
        # A missing thyroid blood test is not a missing Bio-AI thyroid assessment.
        uncertainties = []
    uncertainties.extend(_answer_limits(message, findings))
    next_steps: list[str] = []
    return StructuredResponse(
        mode=mode,
        headline=headline,
        summary=summary,
        findings=findings,
        interpretation=interpretation if mode not in {ResponseMode.single_value, ResponseMode.result_list} else None,
        uncertainties=uncertainties,
        next_steps=next_steps,
        follow_up=follow_up,
        display_entities=display_entity_codes(plan, context),
        reasoning_context=reasoning_context_codes(plan),
    )


def attach_presentation_personalization(
    presentation: StructuredResponse,
    context: HealthContext,
    plan: QueryPlan,
) -> StructuredResponse:
    perso = context.personalization
    if context.quiet and context.quiet.active:
        presentation.quiet_mode = True
        if presentation.mode == ResponseMode.quiet_update:
            pass
        elif re.search(r"\b(change anything|need to change|everything looks stable)\b", plan.raw_message or "", re.I):
            presentation.mode = ResponseMode.quiet_update
    if context.clinician_handoff:
        presentation.clinician_handoff = context.clinician_handoff.model_dump(mode="json")
        if presentation.mode == ResponseMode.clinician_handoff:
            presentation.summary = format_handoff(context.clinician_handoff)
            presentation.headline = "Discussion notes for your clinician"
    report_overview_request = bool(re.search(
        r"\b(?:show|open|view|see|display|give me|pull up|review)\b.{0,36}\b(?:my )?(?:latest|current|most recent|last)?\s*(?:blood|lab)\s+(?:report|results?|tests?)\b",
        plan.raw_message or "",
        re.I,
    ))
    if context.proactive_insights and not report_overview_request:
        insights = list(context.proactive_insights)
        if (plan.task_contract or {}).get("goal") == "interpret":
            insights = [
                item
                for item in insights
                if "missing" not in str(getattr(getattr(item, "trigger", None), "value", getattr(item, "trigger", ""))).lower()
            ]
        presentation.proactive_insights = [item.model_dump(mode="json") for item in insights[:3]]
    if context.health_journey:
        presentation.health_journey = context.health_journey.model_dump(mode="json")
    if perso and perso.primary_health_goal:
        label = perso.primary_health_goal.replace("_", " ")
        presentation.personal_relevance = (
            f"Findings are prioritized for your {label} goal where the available data supports that."
        )
    if context.quiet and context.quiet.active:
        presentation.structured_next_steps = []
        if not presentation.next_steps:
            presentation.next_steps = []
    return presentation


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w%./ ]+", " ", (text or "").lower())).strip()


def _repeats(candidate: str, parts: list[str]) -> bool:
    """True when ``candidate`` says what an earlier part already says (no duplicate paragraphs)."""
    cand = _norm_text(candidate)
    if not cand:
        return True
    for part in parts:
        existing = _norm_text(part)
        if not existing:
            continue
        if cand in existing or existing in cand or cand[:80] == existing[:80]:
            return True
    return False


_RANGE_CONTRADICTION = re.compile(
    r"within (?:this |the )?(?:standard |typical |normal )?reference range|"
    r"comfortably within|commonly normal|often start at 0|frequently begin at 0|"
    r"is a frequent and commonly norm",
    re.I,
)


def prefer_report_range(answer: str, context: HealthContext) -> str:
    """If the prose treats an out-of-range result as normal, lead with the report range."""
    text = answer or ""
    if not _RANGE_CONTRADICTION.search(text):
        return text
    notes = []
    for marker in context.markers or []:
        flag = getattr(marker.flag, "value", str(marker.flag or ""))
        if flag not in {"high", "low", "critical"}:
            continue
        if marker.reference_low is None and marker.reference_high is None:
            continue
        name = marker.name or marker.key
        if not name or name.lower() not in text.lower():
            continue
        note = (
            f"Your report marks {name} as {flag} "
            f"(report range {marker.reference_low}–{marker.reference_high} {marker.unit or ''}).".replace("  ", " ")
        )
        if note.lower() not in text.lower():
            notes.append(note.strip())
    if not notes:
        return text
    return f"{' '.join(notes[:2])} {text}".strip()


def _explained(text: str | None) -> bool:
    from app.pipeline.report_explainer import is_explained

    return is_explained(text)


def _unstated_flagged_facts(presentation: StructuredResponse, text: str) -> list[str]:
    """Out-of-range findings whose value the prose never states (cards show the rest)."""
    missing = []
    from app.pipeline.report_explainer import is_explained

    if is_explained(text):
        return missing
    for item in presentation.findings or []:
        if item.value is None or (item.status or "") not in {"high", "low", "critical"}:
            continue
        if item.source_type == "bio_ai_report":
            continue  # a Bio-AI "low" is a good result, not an out-of-range value
        tokens = {str(item.value)}
        try:
            tokens.add(f"{float(item.value):g}")
        except (TypeError, ValueError):
            pass
        if not any(re.search(rf"(?<![\d.]){re.escape(token)}(?![\d])", text) for token in tokens):
            unit = f" {item.unit}" if item.unit else ""
            missing.append(f"{item.label} {item.value}{unit}".strip())
    return missing


def flatten_structured_response(presentation: StructuredResponse, *, raw_answer: str = "") -> str:
    if presentation.mode == ResponseMode.clinician_handoff and presentation.summary:
        return sanitize_internal_ids(presentation.summary)
    if presentation.quiet_mode and presentation.summary:
        return sanitize_internal_ids(presentation.summary)
    if (presentation.summary_style == SummaryStyle.narrative_health_summary or presentation.themes) and _explained(raw_answer):
        # A sectioned explanation (report_explainer) is the chat text; theme cards stay as cards.
        return sanitize_internal_ids(_CONTEXT_LEAK.sub("", raw_answer)).strip()
    if presentation.summary_style == SummaryStyle.narrative_health_summary or presentation.themes:
        text = flatten_narrative(
            presentation.overall_summary or presentation.summary or "",
            presentation.themes,
            presentation.next_steps[0] if presentation.next_steps else None,
        )
        missing_facts = _unstated_flagged_facts(presentation, text)
        if missing_facts:
            text = "Stored records: " + "; ".join(missing_facts) + ".\n\n" + text
        return sanitize_internal_ids(_CONTEXT_LEAK.sub("", text)).strip()
    if not presentation.findings:
        text = (raw_answer or presentation.summary or presentation.interpretation or "").strip()
        extras = []
        if presentation.uncertainties:
            note = " ".join(presentation.uncertainties)
            if note.lower() not in text.lower():
                extras.append(note)
        if presentation.next_steps:
            extras.append(" ".join(presentation.next_steps))
        return sanitize_internal_ids(_CONTEXT_LEAK.sub("", "\n\n".join([text, *extras] if text else extras))).strip()
    parts: list[str] = []
    prose_modes = {
        ResponseMode.interpretation,
        ResponseMode.comparison,
        ResponseMode.trend,
        ResponseMode.health_overview,
        ResponseMode.safety,
        ResponseMode.personal_interpretation,
    }
    prose = (presentation.summary or "").strip()
    if prose and presentation.mode in prose_modes:
        # A written explanation exists: the chat text is that explanation. The values are
        # already on the finding cards, so they are not repeated as raw lines in between.
        parts.append(prose)
        for extra in (presentation.interpretation, raw_answer):
            if extra and not _repeats(extra, parts):
                parts.append(extra.strip())
    else:
        explained = presentation.headline == "Your Bio-AI Report" and ("\n\n" in prose or len(prose) > 200)
        if presentation.headline and presentation.mode not in {ResponseMode.single_value} and not explained:
            parts.append(presentation.headline)
        if prose:
            parts.append(prose)
        if presentation.mode != ResponseMode.single_value and not explained:
            lines = []
            for item in presentation.findings:
                unit = f" {item.unit}" if item.unit else ""
                status = f" · {item.status.replace('_', ' ')}" if item.status else ""
                value = item.value if item.value is not None else "not available"
                lines.append(f"{item.label}: {value}{unit}{status}".strip())
            parts.append("\n".join(lines))
        if presentation.interpretation and not _repeats(presentation.interpretation, parts):
            parts.append(presentation.interpretation.strip())
        elif raw_answer and presentation.mode in prose_modes and not _repeats(raw_answer, parts):
            parts.append(raw_answer.strip())
    if presentation.uncertainties:
        note = " ".join(presentation.uncertainties)
        blob = " ".join(parts).lower()
        if note.lower() not in blob:
            parts.append(note)
    if presentation.next_steps and not _repeats(" ".join(presentation.next_steps), parts):
        parts.append(" ".join(presentation.next_steps))
    captions = list(dict.fromkeys(item.source_label for item in presentation.findings if item.source_label))
    if captions and presentation.mode in {ResponseMode.single_value, ResponseMode.result_list, ResponseMode.domain_summary}:
        parts.append(captions[0])
    text = "\n\n".join(part for part in parts if part and part.strip())
    missing_facts = _unstated_flagged_facts(presentation, text)
    if missing_facts:
        text = "Stored records: " + "; ".join(missing_facts) + ".\n\n" + text
    return sanitize_internal_ids(_CONTEXT_LEAK.sub("", text)).strip()


def strip_lookup_disclaimers(text: str, mode: ResponseMode) -> str:
    if mode in {ResponseMode.safety, ResponseMode.interpretation, ResponseMode.health_overview}:
        out = text
    else:
        out = _LOOKUP_DISCLAIMER.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def sanitize_internal_ids(text: str) -> str:
    out = _REPORT_PAREN.sub("", text or "")
    out = re.sub(r"(?i)^\s*general information:\s*", "", out)
    out = _REPORT_CLAUSE.sub("the retrieved report", out)
    out = _INTERNAL_ID.sub("", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out)
    out = re.sub(r"\bfrom\s+·", "·", out)
    return out.strip()
