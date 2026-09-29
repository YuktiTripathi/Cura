from app.contracts.bio_ai import BioAIRisk
from app.contracts.health_context import HealthContext

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


class DeterministicRenderer:
    """Development/test renderer used when ENABLE_LLM=false."""

    def render(self, message: str, context: HealthContext) -> str:
        if context.intent.value == "personal_profile" and context.profile:
            missing = ", ".join(context.profile.missing) or "none noted"
            diet = ", ".join(str(f.value) for f in context.profile.dietary_preferences) or "not recorded"
            goals = ", ".join(str(f.value) for f in context.profile.health_goals) or "not recorded"
            return (
                f"Stored profile facts only. Dietary preference: {diet}. "
                f"Health goals: {goals}. Missing structured fields: {missing}. "
                "Conversation history is not used as a source of these facts."
            )
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
                f"Out-of-range markers: {findings}. "
                "This is measured data, not a diagnosis. A clinician can review whether follow-up is needed."
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
            scenario = context.scenario
            okay = ", ".join(item.title for item in scenario.going_well[:3]) or "none identified"
            attention = ", ".join(item.title for item in scenario.needs_attention[:3]) or "none identified"
            risks = ", ".join(item.title for item in scenario.risk_drivers[:3]) or "none available"
            missing = ", ".join(scenario.missing_information[:3]) or "none noted"
            return (
                f"Going well: {okay}. Needs attention: {attention}. "
                f"Bio-AI risk areas: {risks}. Missing information: {missing}. "
                "This summary is based only on your available records and is not a diagnosis."
            )
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
            ids = ", ".join(f"{c.report_id} ({c.report_date}, {c.source_line})" for c in context.disambiguation)
            return (
                "I found more than one Bio-AI report that matches this question, including two from the same date. "
                f"Candidates: {ids}. Which report should I use? I will not pick one at random."
            )
        if context.intent.value == "latest_result" and context.markers:
            if len(context.markers) > 1:
                lines = []
                for m in context.markers:
                    date = next((e.report_date for e in context.evidence if e.marker == m.name), None)
                    report_id = next((e.report_id for e in context.evidence if e.marker == m.name), None)
                    value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
                    date_bit = f" on {date}" if date else ""
                    report_bit = f" (report {report_id}{date_bit})" if report_id else ""
                    lines.append(f"• **{m.name}:** {value}{report_bit}. Flag: {m.flag.value}.")
                return (
                    "Your latest results:\n\n"
                    + "\n".join(lines)
                    + "\n\nThis is from your blood report, not a diagnosis."
                )
            m = context.markers[0]
            date = context.evidence[0].report_date if context.evidence else "unknown date"
            value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
            return (
                f"Your latest {m.name} (report {context.evidence[0].report_id} on {date}) is {value}. "
                f"Flag: {m.flag.value}. This is from your blood report, not a diagnosis."
            )
        if context.intent.value == "previous_result" and context.markers:
            m = context.markers[0]
            date = context.evidence[0].report_date if context.evidence else "unknown date"
            value = "unavailable" if m.value is None else f"{m.value} {m.unit or ''}".strip()
            return (
                f"Your previous {m.name} result was {value} on {date} "
                f"(report {context.evidence[0].report_id})."
            )
        if context.intent.value == "trend" and context.comparisons:
            c = context.comparisons[0]
            name = context.resolved_topic_name or c.topic
            return (
                f"{name} changed from {c.previous_value} ({c.previous_date}, {c.previous_report_id}) "
                f"to {c.current_value} ({c.current_date}, {c.current_report_id}). "
                f"Absolute change: {c.absolute_delta}. Percentage change: {c.percentage_change}%. "
                f"Direction: {c.direction}. Calculated by Cura, not the model."
            )
        if context.intent.value == "blood_marker_explanation" and context.markers:
            m = context.markers[0]
            ref = f"{m.reference_low}–{m.reference_high} {m.unit or ''}".strip()
            return (
                f"Your latest {m.name} is {m.value} {m.unit or ''} (flag {m.flag.value}). "
                f"Typical lab reference on this report is {ref}. "
                f"I cannot say this is 'normal' as a diagnosis; it is in-range or out-of-range vs that report's reference."
            )
        if context.intent.value == "bio_ai_comparison" and context.comparisons:
            lines = []
            for c in context.comparisons:
                name = context.resolved_topic_name if len(context.comparisons) == 1 else c.topic
                name = name or c.topic
                lines.append(
                    f"{name}: {c.previous_report_id} on {c.previous_date} = {c.previous_value}; "
                    f"{c.current_report_id} on {c.current_date} = {c.current_value}. "
                    f"Delta {c.absolute_delta} ({c.percentage_change}%), direction {c.direction}."
                )
            return (
                " ".join(lines)
                + " These are assessments/estimates, not diagnoses."
            )
        if context.intent.value == "bio_ai_score" and context.bio_ai_risks:
            return render_bio_ai_score_list(context.bio_ai_risks)
        if context.intent.value == "bio_ai_explanation" and context.bio_ai_risks:
            extra = ""
            if context.comparisons:
                c = context.comparisons[0]
                extra = (
                    f" Across reports {c.previous_report_id} and {c.current_report_id}, the score moved "
                    f"from {c.previous_value} to {c.current_value} ({c.direction}, {c.percentage_change}%)."
                )
            lines = [format_bio_ai_risk_line(r) for r in context.bio_ai_risks]
            return (
                "Your latest Bio-AI assessment shows:\n\n"
                + "\n".join(lines)
                + extra
                + f"\n\n{BIO_AI_DISCLAIMER}"
            )
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
            summary = context.in_range_summary
            out = [m for m in context.markers if m.flag.value in {"low", "high"}][:5]
            lines = ", ".join(f"{m.name} {m.value} ({m.flag.value})" for m in out)
            return (
                f"Prioritized findings from the latest blood report: {lines}. "
                f"In range {summary.in_range if summary else 0}, out of range {summary.out_of_range if summary else 0}."
            )
        if context.intent.value == "general_health_question":
            if context.medical_passages:
                excerpts = []
                for row in context.medical_passages:
                    excerpt = row.split("): ", 1)[-1] if "): " in row else row
                    if excerpt.strip():
                        excerpts.append(excerpt.strip())
                if excerpts:
                    topic = context.resolved_topic_name or "this topic"
                    return (
                        " ".join(excerpts)
                        + f" This is general educational information about {topic}, "
                        "not a personal result, diagnosis, or meal plan."
                    )
            topic = context.resolved_topic_name or "this topic"
            return (
                f"{topic} can be explained in general terms from medical knowledge. "
                "This is educational information, not a personal lab result."
            )
        return "I could not find matching personal health data for that question."
