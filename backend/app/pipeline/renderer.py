from app.contracts.bio_ai import BioAIRisk
from app.contracts.health_context import HealthContext, SourceConflict
from app.pipeline.presentation import (
    bio_ai_source_label,
    format_user_date,
    sanitize_internal_ids,
    user_source_caption,
)

BIO_AI_DISCLAIMER = "These scores are from your Bio-AI assessment and are not a medical diagnosis."


def format_bio_ai_score_value(score: float) -> str:
    if float(score).is_integer():
        return str(int(score))
    return str(score)


def format_bio_ai_risk_line(risk: BioAIRisk) -> str:
    name = (risk.name or risk.code or "Assessment").strip()
    if risk.score is None:
        return f"• **{name}:** No score reported"
    score = format_bio_ai_score_value(risk.score)
    status = (risk.status or "").strip()
    if status:
        return f"• **{name}:** {score} ({status})"
    return f"• **{name}:** {score}"


def render_bio_ai_score_list(risks: list[BioAIRisk]) -> str:
    lines = [format_bio_ai_risk_line(risk) for risk in risks]
    return (
        "Your Bio-AI Report\n\n"
        "Your latest Bio-AI assessment shows:\n\n"
        + "\n".join(lines)
        + f"\n\n{BIO_AI_DISCLAIMER}"
    )


def _format_report_day(value) -> str:
    return format_user_date(value) or str(value)


def render_missing_blood_marker(context: HealthContext) -> str:
    item = next(
        (row for row in context.missing if row.reason in {"no_reports", "not_in_reports"}),
        context.missing[0] if context.missing else None,
    )
    label = (item.name if item else None) or context.resolved_topic_name
    if label and label.strip().lower() in {"blood", "blood report"}:
        label = context.resolved_topic_name
    if item and item.reason == "not_in_reports":
        scope = item.scope or "the reports checked"
        if scope in {"latest blood report", "the reports checked"}:
            caption = user_source_caption("blood_report", item.report_date, latest=True)
            scope = caption or scope
        if label and item.related_available:
            return (
                f"I don't see {label} in {scope}. It does list {item.related_available}, which is a "
                "related kidney marker but a different measurement, so I won't treat one as the other."
            )
        if label:
            return (
                f"I don't see {label} in {scope}, so that value is not available to me and I won't guess it."
            )
        return f"That biomarker is not available in {scope}. I will not invent a value."
    if label:
        return f"No matching blood result is available for {label}."
    return "No matching blood result is available."


def render_bio_ai_ambiguity(context: HealthContext) -> str:
    candidates = list(context.disambiguation or [])
    count = len(candidates)
    count_word = {2: "two", 3: "three"}.get(count, str(count) if count else "multiple")
    dates = {item.report_date for item in candidates if item.report_date}
    date_bit = f" from {_format_report_day(next(iter(dates)))}" if len(dates) == 1 else ""
    labels = []
    for item in candidates:
        labels.append(bio_ai_source_label(item.label or item.source_line))
    labels = list(dict.fromkeys(labels))
    if len(labels) >= 2:
        label_bit = f" One is a {labels[0]} and the other is an {labels[1]}." if len(labels) == 2 else " " + " ".join(labels) + "."
    else:
        label_bit = ""
    return (
        f"I found {count_word} Bio-AI reports{date_bit}.{label_bit} "
        "Which report would you like me to use?"
    )


def render_source_conflicts(conflicts: list[SourceConflict]) -> str:
    lines = ["These records contain different values. I will not combine them into one number."]
    for conflict in conflicts:
        for item in conflict.values:
            unit = f" {item.unit}" if item.unit else ""
            value = f"{item.value}{unit}" if item.value is not None else "not found"
            source = (item.source or "").lower()
            if "upload" in source:
                label = "uploaded report"
            elif "bio" in source:
                label = "SuperShyft Bio-AI report"
            else:
                label = "SuperShyft report"
            dated = item.measured_at.isoformat() if item.measured_at else "date not shown"
            page = f" (page {item.page})" if item.page else ""
            lines.append(f"Your {label} dated {dated}{page} shows {conflict.name} {value}.")
    return " ".join(lines)


def render_mixed_retrieved_sources(context: HealthContext) -> str:
    if context.source_conflicts:
        return render_source_conflicts(context.source_conflicts)
    parts: list[str] = ["I used more than one of your health sources. Values are kept separate by source."]
    for fact in context.facts or []:
        if fact.source_type == "medical_knowledge":
            continue
        if fact.value is None:
            continue
        unit = f" {fact.unit}" if fact.unit else ""
        source = fact.source_type or fact.source
        dated = ""
        if fact.measured_at:
            dated = f" dated {fact.measured_at}"
        page = f" page {fact.page}" if fact.page else ""
        parts.append(f"{fact.fact} {fact.value}{unit} from {source}{dated}{page}.")
    if context.metabolic_age is not None and not any(
        (fact.fact or "").lower() == "metabolic_age" for fact in (context.facts or [])
    ):
        parts.append(f"metabolic age {context.metabolic_age} from supershyft_bio_ai.")
    return " ".join(parts)


def render_questionnaire_answers(context: HealthContext) -> str:
    answers = list(context.questionnaire or [])
    if not answers:
        return "No matching questionnaire answers are stored for that question."
    lines = []
    for answer in answers:
        label = (answer.question or answer.question_key or "Answer").strip()
        value = "not recorded" if answer.value in (None, "") else str(answer.value)
        if answer.unit:
            value = f"{value} {answer.unit}".strip()
        lines.append(f"• **{label}:** {value}")
    return (
        "From your latest health questionnaire:\n\n"
        + "\n".join(lines)
        + "\n\nThese are your questionnaire answers, not laboratory measurements."
    )


def _derived_and_stated(context: HealthContext) -> str:
    parts: list[str] = []
    for row in context.derived or []:
        unit = f" {row.unit}" if row.unit else ""
        note = f" ({'; '.join(row.notes)})" if row.notes else ""
        parts.append(f" Derived {row.fact}: {row.value}{unit}{note}.")
    for row in context.user_stated or []:
        parts.append(
            f" You stated {row.fact} {row.value}; that is user-stated health information, not a laboratory measurement."
        )
    for item in context.missing or []:
        # A marker left out of this answer is not the same as a marker absent from the record.
        if item.reason == "not_computable" and item.key in {"mentzer", "bmi", "waist"}:
            parts.append(f" {item.name} was not computable from the values on this report.")
    return "".join(parts)


class DeterministicRenderer:
    """Development/test renderer used when ENABLE_LLM=false."""

    def render(self, message: str, context: HealthContext) -> str:
        return sanitize_internal_ids(self._render(message, context))

    def _render(self, message: str, context: HealthContext) -> str:
        mixed_types = {fact.source_type for fact in (context.facts or []) if fact.source_type}
        uploaded_and_ss = "uploaded_document" in mixed_types and any(
            (item or "").startswith("supershyft_") for item in mixed_types
        )
        if context.source_conflicts or uploaded_and_ss:
            return render_mixed_retrieved_sources(context)
        if context.intent.value == "personal_profile" and context.profile:
            missing = ", ".join(context.profile.missing) or "none noted"
            diet = ", ".join(str(f.value) for f in context.profile.dietary_preferences) or "not recorded"
            goals = ", ".join(str(f.value) for f in context.profile.health_goals) or "not recorded"
            return (
                f"Stored profile facts only. Dietary preference: {diet}. "
                f"Health goals: {goals}. Missing structured fields: {missing}. "
                "Conversation history is not used as a source of these facts."
            )
        if context.intent.value == "questionnaire_lookup":
            return render_questionnaire_answers(context)
        if context.intent.value == "report_explanation":
            out = [m.name for m in context.markers if m.flag.value in {"low", "high", "critical"}]
            summary = context.in_range_summary
            counts = ""
            if summary:
                counts = (
                    f" In range: {summary.in_range}. Out of range: {summary.out_of_range}. "
                    f"Missing: {summary.missing}."
                )
            findings = ", ".join(out) or "no out-of-range markers in the latest retrieved report"
            return (
                f"Measured findings from your latest retrieved report:{counts} "
                f"Out-of-range markers: {findings}."
            )
        if context.intent.value == "health_goal_progress":
            if not context.goal_progress:
                return (
                    "No structured health goals are stored yet, so progress cannot be calculated "
                    "from historical records."
                )
            parts = [item.summary for item in context.goal_progress]
            return " ".join(parts) + " Progress is calculated only from stored reports."
        if context.intent.value == "health_scenario" and context.scenario:
            from app.pipeline.narrative import build_narrative_summary, flatten_narrative

            overall, themes, _raw, next_action = build_narrative_summary(context, message=message)
            return flatten_narrative(overall, themes, next_action)
        if context.intent.value == "nutrition_guidance":
            if not context.recommendations:
                return (
                    "I don't have enough supported health and dietary context to provide personalized food guidance. "
                    "I can still explain general healthy eating principles."
                )
            items = " ".join(r.text for r in context.recommendations[:5])
            return (
                f"{items} These are general food and lifestyle suggestions, not clinical dietary treatment."
            )
        if context.status == "ambiguous":
            return render_bio_ai_ambiguity(context)
        if context.intent.value == "latest_result" and context.markers:
            named_gap = next(
                (
                    row for row in context.missing or []
                    if row.reason == "not_in_reports" and row.key and row.key != "requested_marker"
                ),
                None,
            )
            if named_gap and not any(getattr(m, "key", None) == named_gap.key for m in context.markers):
                return render_missing_blood_marker(context)
            extra = _derived_and_stated(context)
            if len(context.markers) > 1:
                lines = []
                for m in context.markers:
                    date = next((e.report_date for e in context.evidence if e.marker == m.name), m.measured_at)
                    value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
                    caption = user_source_caption("blood_report", date, latest=True)
                    lines.append(f"• **{m.name}:** {value} · {m.flag.value.replace('_', ' ')}. {caption}")
                return "Your latest results:\n\n" + "\n".join(lines) + extra
            m = context.markers[0]
            date = context.evidence[0].report_date if context.evidence else m.measured_at
            value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
            caption = user_source_caption("blood_report", date, latest=True)
            return (
                f"Your latest {m.name} is {value}. "
                f"{caption}."
                + extra
            )
        if context.intent.value == "previous_result" and context.markers:
            m = context.markers[0]
            date = context.evidence[0].report_date if context.evidence else "unknown date"
            value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
            return (
                f"Your previous {m.name} result was {value}. "
                f"{user_source_caption('blood_report', date, latest=False)}."
            )
        if context.intent.value == "trend" and context.comparisons:
            if context.premise_verified is False and context.premise and context.premise.note:
                return (
                    context.premise.note
                    + " I will not explain a change that is not present in the retrieved reports."
                )
            return render_trend_sentence(context, context.comparisons[0])
        if context.intent.value == "blood_marker_explanation" and context.markers:
            extra = _derived_and_stated(context) + _iron_pattern_note(context)
            if len(context.markers) > 1:
                lines = []
                for m in context.markers:
                    ref = f"{m.reference_low}–{m.reference_high} {m.unit or ''}".strip()
                    lines.append(
                        f"• **{m.name}:** {m.value} {m.unit or ''} (flag {m.flag.value}). "
                        f"Typical lab reference on this report is {ref}."
                    )
                return (
                    "Your latest results:\n\n"
                    + "\n".join(lines)
                    + extra
                )
            m = context.markers[0]
            ref = f"{m.reference_low}–{m.reference_high} {m.unit or ''}".strip()
            range_note = (
                "This falls within the reference range reported by your laboratory."
                if m.flag.value == "normal"
                else f"Typical lab reference on this report is {ref}."
            )
            return (
                f"Your latest {m.name} is {m.value} {m.unit or ''} "
                f"({m.flag.value.replace('_', ' ')}). {range_note}"
                + extra
            )
        if context.intent.value == "bio_ai_comparison" and context.comparisons:
            lines = []
            for c in context.comparisons:
                name = context.resolved_topic_name if len(context.comparisons) == 1 else c.topic
                name = name or c.topic
                prev_label = user_source_caption("bio_ai_report", c.previous_date, latest=False)
                curr_label = user_source_caption("bio_ai_report", c.current_date, latest=True)
                lines.append(
                    f"{name}: {prev_label} = {c.previous_value}; "
                    f"{curr_label} = {c.current_value}. "
                    f"Delta {c.absolute_delta} ({c.percentage_change}%), direction {c.direction}."
                )
            return " ".join(lines) + " These are assessments, not diagnoses."
        if context.intent.value == "bio_ai_score" and context.bio_ai_risks:
            return render_bio_ai_score_list(context.bio_ai_risks)
        if context.intent.value == "bio_ai_explanation" and context.bio_ai_risks:
            extra = ""
            if context.comparisons:
                c = context.comparisons[0]
                extra = (
                    f" Across the previous and latest Bio-AI assessments, the score moved "
                    f"from {c.previous_value} to {c.current_value} ({c.direction}, {c.percentage_change}%)."
                )
            lines = [format_bio_ai_risk_line(r) for r in context.bio_ai_risks]
            return (
                "Your latest Bio-AI assessment shows:\n\n"
                + "\n".join(lines)
                + extra
                + f"\n\n{BIO_AI_DISCLAIMER}"
            )
        if context.intent.value in {"latest_result", "previous_result", "blood_marker_explanation"}:
            if context.missing and not context.markers:
                blood_missing = next(
                    (row for row in context.missing if row.reason in {"no_reports", "not_in_reports"}),
                    None,
                )
                if blood_missing:
                    return render_missing_blood_marker(context)
        if context.missing and not context.markers and not context.bio_ai_risks:
            item = context.missing[0]
            if item.reason == "no_goals":
                return (
                    "No structured health goals are stored yet, so I cannot calculate progress "
                    "from historical records."
                )
            if item.reason == "score_not_available":
                return "Score not available in this report."
            if item.reason == "insufficient_history":
                label = context.resolved_topic_name or item.name
                return (
                    f"I only have one {label} result available, so I can't determine a trend yet. "
                    "I will not invent a previous value."
                )
            if item.reason == "no_previous":
                label = context.resolved_topic_name or item.name
                return (
                    f"I only have one {label} result available, so I can't show a previous result yet."
                )
            label = item.name or context.resolved_topic_name or "that"
            return (
                f"I couldn't find a {label} result in the health data currently available to me. "
                "I will not invent it."
            )
        if context.intent.value == "broad_health_summary" and context.markers:
            from app.pipeline.narrative import build_narrative_summary, flatten_narrative

            overall, themes, _raw, next_action = build_narrative_summary(context, message=message)
            return flatten_narrative(overall, themes, next_action)
        if context.intent.value == "general_health_question":
            from app.core.copy import GENERAL_KNOWLEDGE_UNAVAILABLE

            return GENERAL_KNOWLEDGE_UNAVAILABLE
        return "I could not find matching personal health data for that question."


def _iron_pattern_note(context: HealthContext) -> str:
    keys = {m.key: m for m in context.markers}
    low = []
    for key in ("hemoglobin", "mcv", "mch", "iron"):
        marker = keys.get(key)
        if marker and marker.flag.value == "low":
            low.append(f"{marker.name} {marker.value} {marker.unit or ''}".strip())
    if len(low) < 2:
        return ""
    return (
        " Together, low haemoglobin with low MCV/MCH and/or low serum iron can be discussed with a clinician "
        "as a possible iron-related pattern; this is not a diagnosis of iron deficiency or anaemia."
    )


def _source_gap_sentence(context: HealthContext) -> str:
    gaps = []
    for row in context.source_outcomes or []:
        status = getattr(row.status, "value", row.status)
        if status in {"empty", "unavailable"}:
            gaps.append(f"{row.source.replace('_', ' ')} was {status}")
    if not gaps:
        return ""
    return "Unavailable sources: " + "; ".join(gaps) + "."


def render_diagnosis_restraint(context: HealthContext) -> str:
    parts = [
        "I can't diagnose a condition from reports or symptoms. Diagnosis is a clinician's decision."
    ]
    hba1c = next((m for m in context.markers if m.key == "hba1c"), None)
    if hba1c and hba1c.value is not None:
        evid = next((e for e in context.evidence if (e.marker or "").lower() in {"hba1c", "hba1c"}), context.evidence[0] if context.evidence else None)
        caption = user_source_caption("blood_report", evid.report_date if evid else None, latest=True)
        flag = getattr(hba1c.flag, "value", hba1c.flag) or "unspecified"
        parts.append(
            f"Your latest HbA1c is {hba1c.value} {hba1c.unit or ''} ({flag}). {caption}."
        )
    diabetes = next((r for r in context.bio_ai_risks if (r.code or "") in {"type_2_diabetes", "diabetes"}), None)
    if diabetes and diabetes.score is not None:
        parts.append(
            f"Your Bio-AI type 2 diabetes assessment is {format_bio_ai_score_value(diabetes.score)}"
            + (f" ({diabetes.status})" if diabetes.status else "")
            + ". That score is an assessment, not a disease diagnosis."
        )
    parts.append("Please discuss these results with a clinician if you have diagnostic questions.")
    return " ".join(parts)


def render_provenance(context: HealthContext) -> str:
    family = {"cholesterol", "ldl", "hdl", "triglycerides"}
    topic = (context.resolved_topic or "").lower()
    markers = list(context.markers)
    if topic in family or topic == "cholesterol":
        lipid = [m for m in markers if m.key in family]
        if len(lipid) > 1:
            bits = []
            for m in lipid:
                evid = next((e for e in context.evidence if e.marker == m.name or e.report_id == m.report_id), None)
                bits.append(
                    f"{m.name} {m.value} {m.unit or ''} from {user_source_caption('blood_report', m.measured_at or (evid.report_date if evid else None))}"
                )
            return (
                "I used these labelled lipid values from your blood report, not a single unnamed cholesterol number: "
                + "; ".join(bits)
                + "."
            )
    if markers:
        m = markers[0]
        evid = context.evidence[0] if context.evidence else None
        caption = user_source_caption("blood_report", m.measured_at or (evid.report_date if evid else None))
        return (
            f"That {m.name} value is {m.value} {m.unit or ''} from {caption}. "
            "It is a measured lab result, not general medical knowledge."
        )
    if context.bio_ai_risks:
        risk = context.bio_ai_risks[0]
        evid = context.evidence[0] if context.evidence else None
        caption = user_source_caption("bio_ai_report", evid.report_date if evid else None)
        return (
            f"That figure is the Bio-AI {risk.name or risk.code} assessment "
            f"{format_bio_ai_score_value(risk.score) if risk.score is not None else ''} "
            f"from {caption}. "
            "It is an assessment, not a diagnosis."
        )
    return "I do not have a stored personal value for that follow-up, so I cannot name a source."


def _fmt(value) -> str:
    """Stored values exactly as stored (18.0 stays 18.0)."""
    return str(value)


def _fmt_delta(value: float) -> str:
    """A computed difference: rounded only to remove float noise (6.1 - 6.2 = 0.1)."""
    return f"{round(abs(value), 4):g}"


def render_trend_sentence(context: HealthContext, c) -> str:
    """Previous -> latest with dates, the exact change, and where it sits against the report range.

    Direction words come from the report's own range (closer to / further from / back within),
    never from a guess about whether higher or lower is better for that marker.
    """
    name = context.resolved_topic_name or c.topic
    marker = next((m for m in context.markers or [] if m.key == c.topic), None)
    unit = (marker.unit or "") if marker else ""
    pct_unit = unit.strip() == "%"
    unit_text = "%" if pct_unit else (f" {unit}" if unit else "")
    prev = f"{_fmt(c.previous_value)}{unit_text}"
    latest = f"{_fmt(c.current_value)}{unit_text}"
    delta = c.absolute_delta if c.absolute_delta is not None else round(c.current_value - c.previous_value, 4)
    if delta == 0:
        return (
            f"Your {name} was {latest} on {format_user_date(c.current_date)}, the same as on "
            f"{format_user_date(c.previous_date)}."
        )
    verb = "decreased" if delta < 0 else "increased"
    size = f"{_fmt_delta(delta)} percentage points" if pct_unit else f"{_fmt_delta(delta)}{(' ' + unit) if unit else ''}"
    pct = f" (about {abs(c.percentage_change):.1f}%)" if c.percentage_change is not None and not pct_unit else ""
    text = (
        f"Your {name} {verb} from {prev} on {format_user_date(c.previous_date)} to {latest} on "
        f"{format_user_date(c.current_date)}, a change of {size}{pct}."
    )
    if marker is None or (marker.reference_low is None and marker.reference_high is None):
        return text

    def outside(value: float) -> float:
        if marker.reference_high is not None and value > marker.reference_high:
            return value - marker.reference_high
        if marker.reference_low is not None and value < marker.reference_low:
            return marker.reference_low - value
        return 0.0

    before, after = outside(c.previous_value), outside(c.current_value)
    ref = f"{_fmt(marker.reference_low)}–{_fmt(marker.reference_high)}{unit_text}"
    if after == 0 and before > 0:
        text += f" That brings it back within your report's range ({ref})."
    elif after == 0:
        text += f" Both readings sit within your report's range ({ref})."
    elif after < before:
        text += (
            f" That is movement toward your report's range ({ref}), although the latest result is still "
            f"flagged {getattr(marker.flag, 'value', marker.flag)}."
        )
    else:
        text += f" That moves it further from your report's range ({ref}), so it is worth keeping an eye on."
    return text
