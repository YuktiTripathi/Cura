"""Plain-language explanations of a whole blood report or Bio-AI report.

Used when no model writes the answer (for example while personal-health prompts
stay local). Results are grouped by body system, each group says what its tests
measure and what the member's pattern means, the most important group comes
first, and Bio-AI scores are linked to the blood results behind them. Wording
stays educational: it describes ranges and patterns and points to a doctor,
never diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.blood import BloodMarker
from app.pipeline.clinical_thresholds import clinical_notes


def _norm(text: str | None) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


@dataclass(frozen=True)
class _Theme:
    code: str
    title: str
    about: str
    words: tuple[str, ...]


# Order is the reading order when no result is urgent.
_THEMES = (
    _Theme("sugar", "Blood sugar",
           "These tests show how your body is handling sugar.",
           ("hba1c", "glycated", "glucose", "bloodsugar", "insulin")),
    _Theme("lipids", "Cholesterol and blood fats",
           "These tests measure the fats carried in your blood. Over years, high LDL, VLDL and triglycerides are linked to a higher risk of heart and blood-vessel disease, and they usually respond well to changes in diet, activity and weight.",
           ("cholesterol", "cholestrol", "ldl", "hdl", "vldl", "triglyceride", "lipoprotein", "apob")),
    _Theme("iron", "Iron and red blood cells",
           "These tests show how much iron your body has stored and how well your red blood cells are formed. Red blood cells carry oxygen, so low iron can show up as tiredness or low energy.",
           ("ferritin", "iron", "tibc", "transferrin", "haemoglobin", "hemoglobin", "mcv", "mchc", "mch",
            "rdw", "redbloodcell", "rbc", "haematocrit", "hematocrit", "pcv")),
    _Theme("liver", "Liver",
           "These enzymes and proteins show how your liver is working.",
           ("sgot", "sgpt", "alt", "ast", "ggt", "alkalinephosphatase", "bilirubin", "albumin", "globulin")),
    _Theme("kidney", "Kidneys and body salts",
           "These tests show how well your kidneys are filtering and how your body is balancing salts and water. Small differences just outside the range are common and often not significant on their own.",
           ("creatinine", "urea", "bun", "uricacid", "egfr", "sodium", "potassium", "chloride", "calcium", "phosph")),
    _Theme("thyroid", "Thyroid",
           "Thyroid hormones help set your body's energy use and metabolism.",
           ("tsh", "t3", "t4", "thyro")),
    _Theme("vitamins", "Vitamins",
           "Vitamins such as D and B12 support bones, muscles, nerves and energy.",
           ("vitamin", "b12", "cobalamin", "folate", "folic")),
    _Theme("cells", "Platelets and white blood cells",
           "Platelets help your blood clot and white blood cells fight infection. Small changes in platelet size (MPV) are common and usually not significant on their own.",
           ("platelet", "mpv", "pdw", "plcr", "wbc", "whitebloodcell", "neutrophil", "lymphocyte",
            "monocyte", "eosinophil", "basophil", "leucocyte", "leukocyte")),
)
_SHORT = {"sugar": "blood sugar", "lipids": "cholesterol", "iron": "iron", "liver": "liver health",
          "kidney": "kidney and salt balance", "vitamins": "vitamins", "cells": "platelets"}
_OTHER = _Theme("other", "Other results", "", ())


def _theme(marker: BloodMarker) -> _Theme:
    text = _norm(marker.key) + " " + _norm(marker.name)
    for theme in _THEMES:
        if any(word in text for word in theme.words):
            return theme
    return _OTHER


def _flag(marker: BloodMarker) -> str:
    return getattr(marker.flag, "value", str(marker.flag or "")).lower()


def _out_of_range(marker: BloodMarker) -> bool:
    return marker.value is not None and _flag(marker) in {"low", "high", "critical", "critical_low", "critical_high"}


def _dedupe(markers: list[BloodMarker]) -> list[BloodMarker]:
    """Labs often repeat a test under two names (MPV / "MPV Mean Platelet Volume")."""
    seen: set[tuple[str, float | None, str]] = set()
    out = []
    for marker in markers:
        identity = (_norm(marker.name)[:3], marker.value, _norm(marker.unit))
        if identity in seen:
            continue
        seen.add(identity)
        out.append(marker)
    return out


def _value(marker: BloodMarker) -> str:
    from app.pipeline.narrative import format_marker_name, format_unit

    unit = format_unit(marker.unit) or ""
    sep = "" if unit in {"%", ""} else " "
    direction = "high" if "high" in _flag(marker) else "low"
    return f"{_display_name(format_marker_name(marker.name))} {marker.value:g}{sep}{unit} ({direction})"


_SPELLING = {"Cholestrol": "Cholesterol", "cholestrol": "cholesterol", "Platelate": "Platelet",
             "platelate": "platelet", "HBA1C": "HbA1c", "Hba1c": "HbA1c", "HBA1c": "HbA1c"}


def _display_name(name: str) -> str:
    """Fix lab-feed spellings members would otherwise see verbatim."""
    for wrong, right in _SPELLING.items():
        name = name.replace(wrong, right)
    return name


def _test_notes(markers: list[BloodMarker]) -> list[str]:
    """Per-test background, only for tests the member actually has."""
    names = " ".join(_norm(m.name) + " " + _norm(m.key) for m in markers)
    notes = []
    if "hba1c" in names or "glycated" in names:
        notes.append("HbA1c shows your average blood sugar over the last two to three months.")
    if "glucose" in names or "bloodsugar" in names:
        notes.append("A glucose test shows the sugar level at the moment the sample was taken.")
    return notes


def _has(markers: list[BloodMarker], *words: str, direction: str) -> bool:
    return any(
        any(word in _norm(m.name) or word == _norm(m.key) for word in words) and direction in _flag(m)
        for m in markers
    )


def _pattern(theme: str, markers: list[BloodMarker]) -> str | None:
    """A sentence on what the results mean together, only for well-known patterns."""
    if theme == "iron":
        low_stores = _has(markers, "ferritin", direction="low")
        small_cells = _has(markers, "mcv", "mch", direction="low")
        high_tibc = _has(markers, "tibc", "transferrin", direction="high")
        if low_stores and (small_cells or high_tibc):
            return (
                "Taken together, low ferritin with smaller red blood cells"
                + (" and a high TIBC" if high_tibc else "")
                + " is a pattern often seen when the body's iron stores are running low."
                " A doctor can confirm this and check the cause."
            )
        if low_stores:
            return "Low ferritin usually means your iron stores are on the low side."
        low_hb = _has(markers, "haemoglobin", "hemoglobin", "hb", direction="low")
        low_iron = _has(markers, "iron", direction="low")
        if low_hb and small_cells and low_iron:
            return (
                "Taken together, low haemoglobin with smaller red blood cells and low iron is a pattern "
                "often seen with iron-deficiency anaemia. A doctor can confirm this and check the cause."
            )
    if theme == "lipids":
        high = [m for m in markers if "high" in _flag(m)]
        if len(high) >= 2:
            return (
                "Several of your blood-fat results are high at the same time, so this is worth "
                "looking at as one area rather than test by test."
            )
    if theme == "sugar" and _has(markers, "hba1c", direction="high"):
        return None  # the clinical note says it more precisely
    return None


def explain_blood_report(markers: list[BloodMarker], *, in_range: int | None = None,
                         out_of_range: int | None = None) -> str:
    flagged = _dedupe([m for m in markers if _out_of_range(m)])
    total = (in_range or 0) + (out_of_range or 0)
    if not flagged:
        return (
            "Good news: all the results in your latest report are within the lab's reference ranges. "
            "Keep up your current habits, and ask about any specific test you'd like explained."
        )

    groups: dict[str, list[BloodMarker]] = {}
    for marker in flagged:
        groups.setdefault(_theme(marker).code, []).append(marker)
    notes = clinical_notes(flagged)
    urgent = {(_theme(n.marker).code) for n in notes if n.urgent}
    noted = {(_theme(n.marker).code) for n in notes}
    order = [t for t in (*_THEMES, _OTHER) if t.code in groups]
    order.sort(key=lambda t: (t.code not in urgent, t.code not in noted))

    titles = [_SHORT.get(t.code, t.title.lower()) for t in order[:2]]
    focus = " and ".join(titles)
    stands = f"The area that stands out is {focus}." if len(titles) == 1 else f"The areas that stand out are {focus}."
    if total:
        opening = f"Most of your results look fine: {in_range} of {total} are within range. {stands}"
    else:
        opening = stands

    parts = [opening]
    for theme in order:
        items = groups[theme.code]
        section = [f"**{theme.title}**"]
        if theme.about:
            section.append(theme.about)
        section.extend(_test_notes(items))
        section.append("Your results: " + ", ".join(_value(m) for m in items) + ".")
        pattern = _pattern(theme.code, items)
        if pattern:
            section.append(pattern)
        for note in notes:
            if _theme(note.marker).code == theme.code:
                section.append(note.text)
        parts.append(section[0] + "\n" + " ".join(section[1:]))

    if urgent:
        close = (
            "**What to do next:** book a visit with your doctor soon and take this report with you, "
            f"starting with your {_SHORT.get(order[0].code, order[0].title.lower())} results."
        )
    else:
        close = (
            "**What to do next:** go through these results with your doctor at your next visit, "
            f"starting with your {_SHORT.get(order[0].code, order[0].title.lower())} results."
        )
    parts.append(close)
    return "\n\n".join(parts)


# Bio-AI ---------------------------------------------------------------------

_RISK_INFO = (
    (("dyslipid", "cholesterol", "lipid"), "how likely you are to have unhealthy levels of blood fats such as cholesterol and triglycerides", "lipids"),
    (("diabet", "glyc", "sugar", "insulin"), "your risk of developing type 2 diabetes", "sugar"),
    (("hypertension", "bloodpressure"), "your risk of high blood pressure", None),
    (("oxidative",), "how much oxidative stress (wear on your cells) your body may be under, which is influenced by sleep, diet, activity and stress", None),
    (("nafld", "fattyliver", "liver"), "your risk of fat building up in the liver", "liver"),
    (("cardiac", "heart", "cardio"), "your risk related to heart health", "lipids"),
    (("obesity", "weight"), "your risk related to body weight", None),
    (("thyroid",), "your risk related to thyroid function", "thyroid"),
    (("anaemia", "anemia"), "your risk of anaemia (low red blood cells or iron)", "iron"),
)
_CONCERN = ("veryhigh", "high", "increased", "elevated", "moderate")


def _risk_info(code: str, name: str) -> tuple[str, str | None]:
    text = _norm(code) + _norm(name)
    for words, meaning, theme in _RISK_INFO:
        if any(word in text for word in words):
            return meaning, theme
    return f"your risk related to {name.lower()}", None


def _concern(status: str | None) -> int:
    s = _norm(status)
    for rank, word in enumerate(_CONCERN):
        if word in s:
            return rank
    return len(_CONCERN)


def explain_bio_ai(risks: list, markers: list[BloodMarker] | None = None) -> str:
    scored = [r for r in risks if getattr(r, "score", None) is not None]
    if not scored:
        return "Your Bio-AI report doesn't have scores I can explain yet."
    scored.sort(key=lambda r: (_concern(r.status), -(r.score or 0)))
    attention = [r for r in scored if _concern(r.status) < len(_CONCERN)]
    fine = [r for r in scored if r not in attention]
    flagged = [m for m in (markers or []) if _out_of_range(m)]

    parts = [
        "Bio-AI scores estimate your risk for common health conditions from your data. "
        "They are risk estimates, not diagnoses, and a higher score means a higher estimated risk."
    ]
    if attention:
        names = ", ".join(r.name for r in attention[:3])
        parts.append(f"The scores that deserve the most attention are **{names}**.")
    for risk in attention:
        meaning, theme = _risk_info(risk.code, risk.name)
        line = f"**{risk.name}: {risk.score:g} ({risk.status or 'no level given'})**\nThis score reflects {meaning}."
        linked = [m for m in flagged if theme and _theme(m).code == theme]
        if linked:
            line += (
                " It lines up with your blood report, where "
                + ", ".join(_value(m) for m in _dedupe(linked)[:4])
                + (" are" if len(linked) > 1 else " is")
                + " outside the range."
            )
        if (risk.lifestyle_contribution or 0) >= 40:
            line += " A large part of this score is linked to lifestyle, so it can come down with changes to diet, activity and sleep."
        parts.append(line)
    if not attention:
        parts.append("Good news: none of your Bio-AI scores is in a raised range right now.")
    if fine:
        names = ", ".join(f"{r.name} ({r.score:g}, {r.status or 'no level given'})" for r in fine)
        parts.append(f"**Looking good:** {names}.")
    if attention:
        parts.append(
            "**What to do next:** share these scores with your doctor, starting with "
            f"{attention[0].name.lower()}, and ask which tests or changes would help most."
        )
    return "\n\n".join(parts)
