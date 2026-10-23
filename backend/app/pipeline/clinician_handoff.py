"""Clinician discussion notes. Not a diagnosis or referral letter."""

from __future__ import annotations

from app.contracts.common import MarkerFlag
from app.contracts.health_context import HealthContext
from app.contracts.personalization import ClinicianHandoff, LongitudinalClass
from app.pipeline.lab_parameters import display_name_for

_ABNORMAL = {MarkerFlag.low, MarkerFlag.high, MarkerFlag.critical, "low", "high", "critical"}


def build_clinician_handoff(context: HealthContext) -> ClinicianHandoff:
    findings: list[str] = []
    latest_day = _latest_report_day(context)
    for marker in context.markers or []:
        flag = getattr(getattr(marker, "flag", None), "value", getattr(marker, "flag", None))
        if flag not in _ABNORMAL or marker.value is None:
            continue
        when_day = _as_day(getattr(marker, "measured_at", None))
        if latest_day is not None and when_day is not None and when_day != latest_day:
            continue
        unit = f" {marker.unit}" if marker.unit else ""
        findings.append(f"{display_name_for(marker.key)} {marker.value}{unit} ({flag})")
    changes: list[str] = []
    for item in context.baselines or []:
        if item.previous is None or int(getattr(item, "observations", 0) or 0) < 2:
            continue
        if item.classification in {
            LongitudinalClass.newly_abnormal,
            LongitudinalClass.persistently_abnormal,
            LongitudinalClass.improved_but_still_abnormal,
            LongitudinalClass.returned_to_range,
            LongitudinalClass.worsened,
            LongitudinalClass.improved,
        }:
            changes.append(f"{display_name_for(item.entity)}: {item.classification.value.lower().replace('_', ' ')}")
    context_notes: list[str] = []
    perso = context.personalization
    if perso:
        if perso.primary_health_goal:
            context_notes.append(f"Active goal: {perso.primary_health_goal.replace('_', ' ')}")
        if perso.known_lifestyle.already_supportive:
            context_notes.append(
                "Reported lifestyle already looks supportive for: "
                + ", ".join(perso.known_lifestyle.already_supportive)
            )
        context_notes.extend(perso.recent_user_context.notes[:3])
    missing = []
    if context.health_story:
        missing.extend(context.health_story.important_missing)
    for item in context.missing or []:
        name = getattr(item, "name", None) or getattr(item, "key", None)
        if name:
            missing.append(str(name))
    questions: list[str] = []
    if any("ferritin" in str(item).lower() for item in missing):
        questions.append("Would ferritin and full iron studies help clarify iron stores?")
    if perso and any("supplement" in note.lower() for note in perso.recent_user_context.notes):
        questions.append("Could supplement use explain the current B12 or related vitamin findings?")
    if findings and not questions:
        questions.append("Which of these persistent or new findings warrant follow-up first?")
    if missing and "Would" not in " ".join(questions):
        questions.append("Which missing measurements would change management?")
    return ClinicianHandoff(
        key_findings=findings[:8],
        longitudinal_changes=changes[:8],
        relevant_context=context_notes[:6],
        missing_information=list(dict.fromkeys(missing))[:6],
        questions_for_clinician=questions[:4],
    )


def _as_day(value):
    from datetime import date, datetime

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _latest_report_day(context: HealthContext):
    days = [
        _as_day(getattr(marker, "measured_at", None))
        for marker in list(context.panel_markers or []) + list(context.markers or [])
    ]
    days = [day for day in days if day]
    return max(days) if days else None


def format_handoff(handoff: ClinicianHandoff) -> str:
    parts = ["Key points to discuss:"]
    for item in handoff.key_findings[:6]:
        parts.append(f"- {item}")
    if handoff.longitudinal_changes:
        parts.append("Changes:")
        for item in handoff.longitudinal_changes[:4]:
            parts.append(f"- {item}")
    if handoff.missing_information:
        parts.append("Missing information:")
        for item in handoff.missing_information[:4]:
            parts.append(f"- {item}")
    if handoff.questions_for_clinician:
        parts.append("Questions:")
        for item in handoff.questions_for_clinician:
            parts.append(f"- {item}")
    return "\n".join(parts)
