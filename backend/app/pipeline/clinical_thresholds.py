"""Guideline thresholds that make a stored result worth raising with a doctor.

Report reference ranges only say "outside normal". These cut-offs come from
published guidelines (ADA for HbA1c and fasting glucose, NCEP ATP III for
triglycerides, ACC/AHA for LDL, Endocrine Society for vitamin D) and say how far
outside. They never diagnose: the wording names the guideline range and points
the member to their doctor. A threshold only applies when the unit matches, so a
mmol/L value is never read against a mg/dL cut-off.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.blood import BloodMarker


@dataclass(frozen=True)
class ClinicalNote:
    marker: BloodMarker
    text: str
    urgent: bool  # True: "soon"; False: "at your next visit"


def _norm(text: str | None) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


_KEYS = {
    "hba1c": "hba1c",
    "glycatedhaemoglobin": "hba1c",
    "glycatedhemoglobin": "hba1c",
    "fastingglucose": "fasting_glucose",
    "fastingbloodsugar": "fasting_glucose",
    "glucosefasting": "fasting_glucose",
    "triglycerides": "triglycerides",
    "ldl": "ldl",
    "ldlcholesterol": "ldl",
    "ldlcholestrolcalculated": "ldl",
    "ldlcholesterolcalculated": "ldl",
    "ldlcholestrol": "ldl",
    "vitamind": "vitamin_d",
    "vitamind25hydroxy": "vitamin_d",
    "vitamindtotal25hydroxy": "vitamin_d",
}


def _kind(marker: BloodMarker) -> str | None:
    return _KEYS.get(_norm(marker.key)) or _KEYS.get(_norm(marker.name))


def _unit_ok(marker: BloodMarker, *accepted: str) -> bool:
    return _norm(marker.unit) in accepted


def _fmt(value: float) -> str:
    return f"{value:g}"


def clinical_note(marker: BloodMarker) -> ClinicalNote | None:
    value = marker.value
    if value is None:
        return None
    kind = _kind(marker)
    soon = "Please discuss this result with your doctor soon."
    next_visit = "It is worth discussing with your doctor at your next visit."
    if kind == "hba1c" and _unit_ok(marker, "", "%"):
        if value >= 6.5:
            return ClinicalNote(marker, (
                f"An HbA1c of {_fmt(value)}% is in the range used to diagnose diabetes "
                f"(6.5% or higher). {soon}"
            ), True)
        if value >= 5.7:
            return ClinicalNote(marker, (
                f"An HbA1c of {_fmt(value)}% is in the prediabetes range (5.7% to 6.4%). {next_visit}"
            ), False)
    if kind == "fasting_glucose" and _unit_ok(marker, "mgdl"):
        if value >= 126:
            return ClinicalNote(marker, (
                f"A fasting glucose of {_fmt(value)} mg/dL is in the range used to diagnose diabetes "
                f"(126 mg/dL or higher). {soon}"
            ), True)
        if value >= 100:
            return ClinicalNote(marker, (
                f"A fasting glucose of {_fmt(value)} mg/dL is in the prediabetes range "
                f"(100 to 125 mg/dL). {next_visit}"
            ), False)
    if kind == "triglycerides" and _unit_ok(marker, "mgdl"):
        if value >= 500:
            return ClinicalNote(marker, (
                f"Triglycerides of {_fmt(value)} mg/dL are in the very high range (500 mg/dL or higher). {soon}"
            ), True)
        if value >= 200:
            return ClinicalNote(marker, (
                f"Triglycerides of {_fmt(value)} mg/dL are in the high range (200 to 499 mg/dL). {next_visit}"
            ), False)
    if kind == "ldl" and _unit_ok(marker, "mgdl") and value >= 190:
        return ClinicalNote(marker, (
            f"An LDL of {_fmt(value)} mg/dL is in the very high range (190 mg/dL or higher). {soon}"
        ), True)
    if kind == "vitamin_d" and _unit_ok(marker, "ngml") and value < 20:
        return ClinicalNote(marker, (
            f"A vitamin D level of {_fmt(value)} ng/mL is in the deficient range (below 20 ng/mL). {next_visit}"
        ), False)
    return None


def clinical_notes(markers: list[BloodMarker]) -> list[ClinicalNote]:
    """Notes for the given markers, urgent first, one per marker kind."""
    seen: set[str] = set()
    notes: list[ClinicalNote] = []
    for marker in markers:
        note = clinical_note(marker)
        kind = _kind(marker)
        if note and kind not in seen:
            seen.add(kind or marker.key)
            notes.append(note)
    return sorted(notes, key=lambda note: not note.urgent)
